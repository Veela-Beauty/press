# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Admin Panel MCP helpers — System User only.

Lists tokens across ALL teams + bulk revoke with audit log.
"""
from __future__ import annotations

import json
from typing import Any

import frappe
from frappe.utils import now_datetime

from press.mcp_server._util import safe_parse_dict, safe_parse_list


@frappe.whitelist()
def list_all_tokens(filters: dict | str | None = None, limit: int = 500) -> list[dict[str, Any]]:
	"""System-User-only listing of all MCP tokens. Optional filters keys:
	team, user, status (active|expired|revoked), label_substring."""
	_require_system_user()
	filter_dict = _parse_filters(filters)
	limit = max(1, min(2000, int(limit)))

	q_filters: dict[str, Any] = {}
	if filter_dict.get("team"):
		q_filters["team"] = filter_dict["team"]
	if filter_dict.get("user"):
		q_filters["user"] = filter_dict["user"]
	# Note: status is computed in Python because it depends on now() and revoked

	rows = frappe.get_all(
		"Press MCP Token",
		filters=q_filters or None,
		fields=[
			"name", "user", "team", "label", "scope",
			"expires_at", "last_used_at",
			"revoked", "revoked_at", "creation", "token_prefix",
			"allowed_release_groups", "allowed_sites",
			"risky_tools_enabled", "approval_status",
		],
		order_by="creation desc",
		limit=limit,
	)

	now = now_datetime()
	results = []
	for row in rows:
		row["scope"] = safe_parse_list(row.get("scope"))
		for k in ("allowed_release_groups", "allowed_sites"):
			row[k] = safe_parse_list(row.get(k))
		row["status"] = _compute_status(row, now)
		# Apply status + label filters in Python
		want_status = filter_dict.get("status")
		if want_status and row["status"] != want_status:
			continue
		want_label = (filter_dict.get("label_substring") or "").lower()
		if want_label and want_label not in (row.get("label") or "").lower():
			continue
		results.append(row)
	return results


@frappe.whitelist()
def bulk_revoke(token_names: list | str, reason: str) -> dict[str, Any]:
	"""Revoke many tokens. Records one Press MCP Admin Action per revoke."""
	_require_system_user()
	if not reason or not str(reason).strip():
		raise frappe.ValidationError("reason is required")
	names = _normalize_names(token_names)
	if not names:
		raise frappe.ValidationError("token_names list is empty")

	actor = frappe.session.user
	revoked = []
	already_revoked = []
	errored = []
	for name in names:
		try:
			if not frappe.db.exists("Press MCP Token", name):
				errored.append({"name": name, "error": "not found"})
				continue
			is_revoked = frappe.db.get_value("Press MCP Token", name, "revoked")
			if is_revoked:
				already_revoked.append(name)
				continue
			frappe.db.set_value(
				"Press MCP Token",
				name,
				{"revoked": 1, "revoked_by": actor, "revoked_at": now_datetime()},
			)
			frappe.get_doc({
				"doctype": "Press MCP Admin Action",
				"action_type": "Revoke",
				"actor": actor,
				"target_token": name,
				"reason": str(reason).strip(),
			}).insert(ignore_permissions=True)
			revoked.append(name)
		except Exception as e:
			errored.append({"name": name, "error": str(e)})
			frappe.log_error(
				title=f"bulk_revoke failed for token {name}",
				message=frappe.get_traceback(),
			)
	# Also write a single Bulk Revoke roll-up entry
	try:
		frappe.get_doc({
			"doctype": "Press MCP Admin Action",
			"action_type": "Bulk Revoke",
			"actor": actor,
			"reason": str(reason).strip(),
			"context_json": json.dumps({
				"revoked": revoked,
				"already_revoked": already_revoked,
				"errored": errored,
			}),
		}).insert(ignore_permissions=True)
	except Exception:
		pass
	return {
		"revoked": revoked,
		"already_revoked": already_revoked,
		"errored": errored,
		"count": len(revoked),
	}


def _require_system_user() -> None:
	user_type = (
		(frappe.session.data.user_type if frappe.session.data else None)
		or frappe.get_cached_value("User", frappe.session.user, "user_type")
	)
	if user_type != "System User":
		raise frappe.PermissionError("System User access required for MCP admin actions")


def _compute_status(row: dict, now) -> str:
	if row.get("revoked"):
		return "revoked"
	expires = row.get("expires_at")
	if expires and expires < now:
		return "expired"
	return "active"


def _parse_filters(filters) -> dict:
	return safe_parse_dict(filters)


def _normalize_names(token_names) -> list[str]:
	# safe_parse_list handles list|JSON-list. For a bare non-JSON string,
	# treat it as a single-element list (e.g., a single token docname passed directly).
	if isinstance(token_names, str):
		result = safe_parse_list(token_names)
		if not result:
			# Non-JSON bare string → single element
			return [token_names]
		return result
	return safe_parse_list(token_names)


@frappe.whitelist()
def approve_risky_token(token_name: str) -> dict:
	"""System User approves a pending risky-tool token."""
	_require_system_user()
	doc = frappe.get_doc("Press MCP Token", token_name)
	if doc.approval_status != "pending":
		raise frappe.ValidationError(
			f"token is {doc.approval_status!r}, only `pending` tokens can be approved"
		)
	frappe.db.set_value(
		"Press MCP Token",
		token_name,
		{"approval_status": "approved", "approved_by": frappe.session.user, "approved_at": now_datetime()},
	)
	frappe.get_doc({
		"doctype": "Press MCP Admin Action",
		"action_type": "Approve Risky Token",
		"actor": frappe.session.user,
		"target_token": token_name,
		"reason": "approval",
	}).insert(ignore_permissions=True)
	return {"status": "approved", "name": token_name}


@frappe.whitelist()
def reject_risky_token(token_name: str, reason: str) -> dict:
	"""System User rejects and revokes a pending risky-tool token."""
	_require_system_user()
	if not reason or not str(reason).strip():
		raise frappe.ValidationError("reason is required")
	doc = frappe.get_doc("Press MCP Token", token_name)
	if doc.approval_status != "pending":
		raise frappe.ValidationError(
			f"token is {doc.approval_status!r}, only `pending` tokens can be rejected"
		)
	frappe.db.set_value(
		"Press MCP Token",
		token_name,
		{"approval_status": "rejected", "revoked": 1, "revoked_at": now_datetime(), "revoked_by": frappe.session.user},
	)
	frappe.get_doc({
		"doctype": "Press MCP Admin Action",
		"action_type": "Reject Risky Token",
		"actor": frappe.session.user,
		"target_token": token_name,
		"reason": str(reason).strip(),
	}).insert(ignore_permissions=True)
	return {"status": "rejected", "name": token_name}
