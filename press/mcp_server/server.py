# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""MCP HTTP entry point. Single whitelisted method dispatches to tool wrappers.

Auth flow per call:
	1. Caller passes {tool, args, token}.
	2. verify_token(token, tool_name) -> User docname OR raises PermissionError.
	3. frappe.set_user(user) — underlying tool method runs as the human user,
	   so all team/role permission checks work transparently.
	4. Dispatch via the tool catalog. Log call to Press MCP Call Log.
"""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Any

import frappe
from frappe.utils import now_datetime

from press.mcp_server.auth import TOKEN_PREFIX_LEN, verify_token
from press.mcp_server.tools import get_tool_spec, list_tool_names

MAX_ARGS_LOG_LEN = 5000  # truncate long arg payloads in audit log


@contextmanager
def _as_user(user: str):
	"""Run a block as `user`, then restore the previous session user.

	Guarantees restoration even on exception, mid-edit, or future refactor.
	"""
	original = frappe.session.user
	frappe.set_user(user)
	try:
		yield
	finally:
		frappe.set_user(original)


@frappe.whitelist(allow_guest=True)
def handle(tool: str, args: dict | str | None = None, token: str | None = None) -> dict[str, Any]:
	"""Single MCP entry point. Returns structured result.

	Returns:
		{ok: bool, data: any, error?: str, error_type?: str}
	"""
	args = _parse_args(args)
	start = time.perf_counter()
	user = None
	token_doc_name = None
	error_type = None
	error_msg = None
	response = None

	try:
		spec = get_tool_spec(tool)
		if not spec:
			raise frappe.ValidationError(
				f"unknown tool {tool!r}; available: {list_tool_names()}"
			)

		if not token:
			raise frappe.PermissionError("token is required")

		target_doctype, target_name = _extract_target(tool, args)
		user = verify_token(token, tool_name=tool, target_doctype=target_doctype, target_name=target_name)
		token_doc_name = _resolve_token_docname(token)

		# Validate required args present
		missing = [a for a in spec["required_args"] if a not in args]
		if missing:
			raise frappe.ValidationError(f"missing required args: {missing}")

		# Dry-run support for high-risk tools
		from press.mcp_server.tools import get_tool_risk
		if args.get("dry_run") and get_tool_risk(tool) == "high":
			response = {
				"dry_run": True,
				"tool": tool,
				"would_execute_with_args": {k: v for k, v in args.items() if k != "dry_run"},
				"risk": "high",
				"warning": "this is a dry-run; no action was taken",
			}
			_log_call(
				tool=tool, user=user, token_name=token_doc_name,
				args=args, response=response, status="Success",
				duration_ms=int((time.perf_counter() - start) * 1000),
			)
			return {"ok": True, "data": response}

		# Strip dry_run from dispatch args (it's a meta-arg, not a tool arg)
		dispatch_args = {k: v for k, v in args.items() if k != "dry_run"}

		# Run tool as the resolved user
		with _as_user(user):
			method = frappe.get_attr(spec["method"])
			response = method(**dispatch_args)

		_log_call(
			tool=tool, user=user, token_name=token_doc_name,
			args=args, response=response, status="Success",
			duration_ms=int((time.perf_counter() - start) * 1000),
		)
		return {"ok": True, "data": response}
	except frappe.PermissionError as e:
		error_type = "PermissionError"
		error_msg = str(e)
	except frappe.ValidationError as e:
		error_type = "ValidationError"
		error_msg = str(e)
	except Exception as e:
		error_type = "Error"
		error_msg = str(e)

	_log_call(
		tool=tool, user=user, token_name=token_doc_name,
		args=args, response=None, status=error_type,
		duration_ms=int((time.perf_counter() - start) * 1000),
		error_message=error_msg,
	)
	return {"ok": False, "error": error_msg, "error_type": error_type}


def _parse_args(args) -> dict:
	if args is None:
		return {}
	if isinstance(args, dict):
		return args
	if isinstance(args, str):
		try:
			parsed = json.loads(args)
			return parsed if isinstance(parsed, dict) else {}
		except (ValueError, TypeError):
			return {}
	return {}


def _resolve_token_docname(token_plaintext: str) -> str | None:
	prefix = token_plaintext[:TOKEN_PREFIX_LEN]
	rows = frappe.get_all(
		"Press MCP Token",
		filters={"token_prefix": prefix},
		pluck="name",
		limit=1,
	)
	return rows[0] if rows else None


def _extract_target(tool: str, args: dict) -> tuple[str | None, str | None]:
	"""Map tool args → (target_doctype, target_name) for resource-scope checks.

	Returns (None, None) for tools that don't operate on a single resource.
	"""
	# Lock-style tools have explicit target_doctype/target_name args
	if "target_doctype" in args and "target_name" in args:
		td = args.get("target_doctype")
		if td in ("Site", "Release Group"):
			return td, args.get("target_name")

	# Site-targeted tools — arg name varies between site, name, site_name
	site = args.get("site") or args.get("site_name")
	if tool in {
		"clone_site",
		"move_site_to_release_group",
		"site_migrate",
		"site_backup",
		"site_install_app",
		"site_uninstall_app",
		"site_activate",
		"site_deactivate",
		"site_update",
		"site_run_python",
		"site_run_sql",
		"site_db_processlist",
		"site_config_get",
		"site_config_set",
		"site_file_read",
		"site_file_write",
	}:
		# api/site.py methods take 'name'; bench_dev_overview methods take 'site_name'
		site = site or args.get("name")
		if site:
			return "Site", site

	# Release-Group-targeted tools — arg name varies
	rg = args.get("release_group") or args.get("name")
	if tool in {
		"clone_bench",
		"bench_deploy",
		"bench_deploy_information",
		"bench_restart",
		"bench_update",
	}:
		if rg:
			return "Release Group", rg

	# Bench-targeted tools: bench_name → parent Release Group via DB lookup.
	# Token RG allowlist applies to the parent RG of the bench.
	bench_name = args.get("bench_name")
	if bench_name and tool in {
		"app_git_status",
		"app_git_push",
		"app_create_locally",
		"app_init_github",
		"bench_recent_logs",
		"bench_ssh_cert_get",
		"bench_ssh_cert_generate",
		"bench_dev_info",
	}:
		parent_rg = frappe.db.get_value("Bench", bench_name, "group")
		if parent_rg:
			return "Release Group", parent_rg

	return None, None


def _log_call(
	tool: str,
	user: str | None,
	token_name: str | None,
	args: dict,
	response: Any,
	status: str,
	duration_ms: int,
	error_message: str | None = None,
) -> None:
	"""Best-effort async log of MCP call. Never blocks the response path."""
	try:
		args_json = json.dumps(args, default=str)[:MAX_ARGS_LOG_LEN]
		response_json = (
			json.dumps(response, default=str)[:MAX_ARGS_LOG_LEN]
			if response is not None
			else None
		)
		frappe.enqueue(
			"press.mcp_server.server._write_call_log",
			queue="short",
			tool=tool,
			user=user or "",
			token_name=token_name,
			status=status,
			duration_ms=duration_ms,
			args_json=args_json,
			response_json=response_json,
			error_message=error_message,
		)
	except Exception:
		pass


def _write_call_log(
	tool: str,
	user: str,
	token_name: str | None,
	status: str,
	duration_ms: int,
	args_json: str,
	response_json: str | None,
	error_message: str | None,
) -> None:
	"""Background-job target invoked by _log_call."""
	try:
		frappe.get_doc({
			"doctype": "Press MCP Call Log",
			"tool": tool,
			"user": user,
			"token": token_name,
			"status": status,
			"duration_ms": duration_ms,
			"args_json": args_json,
			"response_json": response_json,
			"error_message": error_message,
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			title=f"MCP audit log write failed for tool {tool}",
			message=frappe.get_traceback(),
		)
