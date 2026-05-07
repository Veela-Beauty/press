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
from typing import Any

import frappe
from frappe.utils import now_datetime

from press.mcp_server.auth import verify_token
from press.mcp_server.tools import get_tool_spec, list_tool_names

MAX_ARGS_LOG_LEN = 5000  # truncate long arg payloads in audit log


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

		user = verify_token(token, tool_name=tool)
		token_doc_name = _resolve_token_docname(token)

		# Validate required args present
		missing = [a for a in spec["required_args"] if a not in args]
		if missing:
			raise frappe.ValidationError(f"missing required args: {missing}")

		# Run tool as the resolved user
		original_user = frappe.session.user
		frappe.set_user(user)
		try:
			method = frappe.get_attr(spec["method"])
			response = method(**args)
		finally:
			frappe.set_user(original_user)

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
	prefix = token_plaintext[:8]
	rows = frappe.get_all(
		"Press MCP Token",
		filters={"token_prefix": prefix},
		pluck="name",
		limit=1,
	)
	return rows[0] if rows else None


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
	try:
		args_json = json.dumps(args, default=str)[:MAX_ARGS_LOG_LEN]
		response_json = (
			json.dumps(response, default=str)[:MAX_ARGS_LOG_LEN]
			if response is not None
			else None
		)
		frappe.get_doc({
			"doctype": "Press MCP Call Log",
			"tool": tool,
			"user": user or "",
			"token": token_name,
			"status": status,
			"duration_ms": duration_ms,
			"args_json": args_json,
			"response_json": response_json,
			"error_message": error_message,
		}).insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		# Never break MCP path because of logging
		pass
