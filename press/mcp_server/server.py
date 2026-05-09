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

from press.mcp_server.auth import _authenticate_token, verify_token
from press.mcp_server.help import BUILTIN_TOOLS, DISCOVERABILITY_HINT, get_tool_help
from press.mcp_server.rate_limit import RateLimitError, check_rate_limit
from press.mcp_server.tools import get_tool_spec, get_tool_risk, list_tool_names

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
		# Built-in discoverability tools (help / list_tools) — handled inline.
		# Still require a valid token (so anonymous callers can't enumerate),
		# but bypass the per-tool scope check and rate limit.
		if tool in BUILTIN_TOOLS:
			if not token:
				raise frappe.PermissionError("token is required")
			user, token_doc_name, caller_scope = _resolve_for_builtin(token)
			help_args = args if isinstance(args, dict) else {}
			response = get_tool_help(
				tool=help_args.get("tool"),
				category=help_args.get("category"),
				scope_only=bool(help_args.get("scope_only", True)),
				caller_scope=caller_scope,
			)
			_log_call(
				tool=tool, user=user, token_name=token_doc_name,
				args=args, response=response, status="Success",
				duration_ms=int((time.perf_counter() - start) * 1000),
			)
			return _wrap_success(response, args)

		spec = get_tool_spec(tool)
		if not spec:
			raise frappe.ValidationError(
				f"unknown tool {tool!r}; available: {list_tool_names()}. "
				f"Call {{tool: 'help'}} to see what your token can use."
			)

		if not token:
			raise frappe.PermissionError("token is required")

		target_doctype, target_name = _extract_target(tool, args)
		user = verify_token(token, tool_name=tool, target_doctype=target_doctype, target_name=target_name)
		token_doc_name = _resolve_token_docname(token)

		# Rate limit per token (Obj 7)
		check_rate_limit(token_doc_name)

		# Validate required args present
		missing = [a for a in spec["required_args"] if a not in args]
		if missing:
			raise frappe.ValidationError(f"missing required args: {missing}")

		# Dry-run support for high-risk tools
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
			return _wrap_success(response, args)

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
		# Destructive-op notification (Obj 7)
		if get_tool_risk(tool) == "high":
			_notify_destructive_op(tool=tool, user=user, args=args, token_name=token_doc_name)
		# Deploy-failure follow-up (Obj-10 polish item 8): tools that schedule a
		# Press build return a build name; enqueue a delayed status check so an
		# operator/agent gets notified if the build later transitions to Failure.
		_maybe_schedule_deploy_failure_check(tool, response, user)
		return _wrap_success(response, args)
	except RateLimitError as e:
		error_type = "RateLimitError"
		error_msg = str(e)
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


def _wrap_success(response: Any, args: Any) -> dict[str, Any]:
	"""Build the success envelope and conditionally append the discoverability hint.

	Agents that already know the catalog can pass {suppress_hints: true} to
	skip the hint and shave a few tokens off each response.
	"""
	# Defensive guard: callers should pass a dict (after _parse_args), but
	# treat any non-dict as empty so we never crash on `args.get`.
	if not isinstance(args, dict):
		args = {}
	envelope: dict[str, Any] = {"ok": True, "data": response}
	if not args.get("suppress_hints"):
		envelope["_hint"] = DISCOVERABILITY_HINT
	return envelope


def _resolve_for_builtin(token_plaintext: str) -> tuple[str, str | None, list[str]]:
	"""Verify token + return (user, token_docname, scope_list) for built-in tools.

	Built-ins (help/list_tools) skip the per-tool scope check, but we still
	authenticate the token so anonymous callers can't enumerate the catalog.
	Uses the shared `_authenticate_token` helper so token-auth lives in
	one place — see auth.py.

	Raises frappe.PermissionError on invalid/expired/revoked token.
	"""
	from press.mcp_server._util import safe_parse_list

	doc = _authenticate_token(token_plaintext)
	return doc.user, doc.name, safe_parse_list(doc.scope)


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
		"site_domains_list",
		"site_add_domain",
		"site_remove_domain",
		"site_set_host_name",
		"site_update_config_bulk",
		# Obj 10
		"site_schedule_update",
		"site_status",
		"wait_for_bench_flip",
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
		"bench_update_config",
		"bench_update_dependencies",
		# Obj 10
		"release_group_create_deploy_candidate",
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
		# Obj 10
		"bench_run_repo_script",
	}:
		parent_rg = frappe.db.get_value("Bench", bench_name, "group")
		if parent_rg:
			return "Release Group", parent_rg

	# Deploy Candidate / Build → resolve to parent Release Group (Obj 10)
	if tool in {"deploy_candidate_schedule_build", "deploy_candidate_status"}:
		candidate_or_build = args.get("candidate_name") or args.get("name")
		if candidate_or_build:
			rg = _candidate_to_release_group(candidate_or_build)
			if rg:
				return "Release Group", rg

	return None, None


def _candidate_to_release_group(name: str) -> str | None:
	"""Resolve a Deploy Candidate Build or Deploy Candidate name to its RG.

	Fail-closed: if the name resolves to a Build whose `deploy_candidate` is
	null (orphaned mid-create), raise rather than returning None — silent None
	would skip the resource-scope check at the dispatch layer.
	"""
	build_row = frappe.db.get_value(
		"Deploy Candidate Build",
		name,
		["name", "deploy_candidate"],
		as_dict=True,
	)
	if build_row is not None:
		if not build_row.deploy_candidate:
			frappe.throw(
				f"Deploy Candidate Build {name!r} has no linked candidate; "
				"cannot enforce resource scope.",
				frappe.ValidationError,
			)
		return frappe.db.get_value(
			"Deploy Candidate", build_row.deploy_candidate, "group"
		)
	# Maybe the name IS a Deploy Candidate
	return frappe.db.get_value("Deploy Candidate", name, "group")


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
	"""Background-job target invoked by _log_call. Computes hash chain."""
	import hashlib

	try:
		# Walk back to the latest row's row_hash for chain linkage
		latest = frappe.get_all(
			"Press MCP Call Log",
			fields=["row_hash"],
			order_by="creation desc",
			limit=1,
		)
		prev_hash = latest[0].row_hash if latest else "GENESIS"

		# Compute this row's hash. Use a stable serialization.
		creation_iso = now_datetime().isoformat()
		hash_input = "||".join([
			prev_hash or "",
			tool,
			user or "",
			token_name or "",
			status,
			creation_iso,
		])
		row_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

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
			"prev_hash": prev_hash,
			"row_hash": row_hash,
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			title=f"MCP audit log write failed for tool {tool}",
			message=frappe.get_traceback(),
		)


def _notify_destructive_op(
	tool: str, user: str, args: dict, token_name: str | None
) -> None:
	"""Best-effort notification when a high-risk MCP tool runs successfully.

	Writes to Error Log with a distinctive title so operators can grep / hook
	external alerting on it (e.g., a periodic scheduler scan + Slack post).
	"""
	try:
		summary = (
			f"MCP destructive op: {tool} by {user} "
			f"via token {token_name or 'unknown'}"
		)
		# Use error_log so it shows up in Frappe's Error Log list — operators
		# can build an alerting hook on this title prefix.
		frappe.log_error(
			title=f"[MCP-DESTRUCTIVE] {tool}",
			message=f"{summary}\n\nargs: {json.dumps(args, default=str)[:2000]}",
		)
	except Exception:
		pass


# Tools whose response includes a build job that may fail asynchronously.
# Each entry maps tool name → key in response dict that holds the build name.
_DEPLOY_FOLLOWUP_TOOLS = {
	"bench_deploy": "name",  # press.api.bench.deploy returns the build name as 'name'
	"deploy_candidate_schedule_build": "build",
}
_DEPLOY_FOLLOWUP_DELAY_SECONDS = 300  # 5 min


def _maybe_schedule_deploy_failure_check(
	tool: str, response: Any, user: str | None
) -> None:
	"""If the tool kicks off a Press build, enqueue a check 5 min later that
	emits a notification if the build is in Failure state.

	No-op for tools that don't produce a build name.
	"""
	if tool not in _DEPLOY_FOLLOWUP_TOOLS:
		return
	if not isinstance(response, dict):
		return
	build_name = response.get(_DEPLOY_FOLLOWUP_TOOLS[tool])
	if not build_name:
		return
	try:
		frappe.enqueue(
			"press.mcp_server.server._check_deploy_followup",
			queue="long",
			enqueue_after_commit=True,
			now=False,
			# Frappe's enqueue doesn't have a built-in delay; we re-enqueue if
			# the build is still in-flight when the worker picks this up.
			tool=tool,
			build_name=build_name,
			triggered_by=user or "",
			deadline_seconds=_DEPLOY_FOLLOWUP_DELAY_SECONDS,
		)
	except Exception:
		# Notification is best-effort; never break the MCP response path.
		pass


def _check_deploy_followup(
	tool: str, build_name: str, triggered_by: str, deadline_seconds: int
) -> None:
	"""Background task: poll the build's status, notify on Failure.

	If the build is still Running/Pending, re-enqueue once for another check.
	After 2 re-enqueues we stop polling — terminal-state notification not
	guaranteed for 30+ minute builds. Operators can use audit_verify_chain
	+ deploy_candidate_status for those.
	"""
	try:
		row = frappe.db.get_value(
			"Deploy Candidate Build",
			build_name,
			["name", "status", "deploy_candidate"],
			as_dict=True,
		)
		if not row:
			return
		status = row.status or ""
		if status in ("Failure", "Cancelled"):
			frappe.log_error(
				title=f"[MCP-DEPLOY-FAILED] {tool}",
				message=(
					f"Build {build_name} (candidate {row.deploy_candidate}) "
					f"transitioned to {status} after {deadline_seconds}s.\n"
					f"Triggered by: {triggered_by or 'unknown'}\n"
					f"Tool: {tool}"
				),
			)
		# Success / no further action; Running/Pending → fire and forget
		# (operators can poll deploy_candidate_status directly).
	except Exception:
		pass
