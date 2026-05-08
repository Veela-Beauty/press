# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Dashboard-facing helpers for the Vue MCP panel (Obj 4c uses these too)."""
from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import now_datetime

from press.mcp_server._util import safe_parse_list


@frappe.whitelist()
def list_my_tokens() -> list[dict[str, Any]]:
	"""List active + recently revoked tokens for the calling user."""
	user = frappe.session.user
	rows = frappe.get_all(
		"Press MCP Token",
		filters={"user": user},
		fields=[
			"name", "label", "scope", "expires_at", "last_used_at",
			"revoked", "revoked_at", "creation", "token_prefix",
			"allowed_release_groups", "allowed_sites",
			"risky_tools_enabled", "approval_status",
		],
		order_by="creation desc",
		limit=100,
	)
	for row in rows:
		row["scope"] = safe_parse_list(row.get("scope"))
		for k in ("allowed_release_groups", "allowed_sites"):
			row[k] = safe_parse_list(row.get(k))
		row["status"] = _status_for(row)
	return rows


@frappe.whitelist()
def list_my_calls(limit: int = 200) -> list[dict[str, Any]]:
	"""List recent MCP Call Log entries for the calling user (cap at 500)."""
	user = frappe.session.user
	limit = max(1, min(500, int(limit)))
	rows = frappe.get_all(
		"Press MCP Call Log",
		filters={"user": user},
		fields=[
			"name", "tool", "status", "duration_ms",
			"args_json", "response_json", "error_message",
			"creation", "token",
		],
		order_by="creation desc",
		limit=limit,
	)
	return rows


def _status_for(row: dict) -> str:
	if row.get("revoked"):
		return "revoked"
	expires = row.get("expires_at")
	if expires and expires < now_datetime():
		return "expired"
	return "active"
