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
		],
		order_by="creation desc",
		limit=limit,
	)

	now = now_datetime()
	results = []
	for row in rows:
		try:
			row["scope"] = json.loads(row.get("scope") or "[]")
		except (ValueError, TypeError):
			row["scope"] = []
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
	skipped = []
	for name in names:
		try:
			doc = frappe.get_doc("Press MCP Token", name)
			if doc.revoked:
				skipped.append(name)
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
			skipped.append({"name": name, "error": str(e)})
	# Also write a single Bulk Revoke roll-up entry
	try:
		frappe.get_doc({
			"doctype": "Press MCP Admin Action",
			"action_type": "Bulk Revoke",
			"actor": actor,
			"reason": str(reason).strip(),
			"context_json": json.dumps({"revoked": revoked, "skipped": skipped}),
		}).insert(ignore_permissions=True)
	except Exception:
		pass
	return {"revoked": revoked, "skipped": skipped, "count": len(revoked)}


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
	if filters is None:
		return {}
	if isinstance(filters, dict):
		return filters
	if isinstance(filters, str):
		try:
			parsed = json.loads(filters)
			return parsed if isinstance(parsed, dict) else {}
		except (ValueError, TypeError):
			return {}
	return {}


def _normalize_names(token_names) -> list[str]:
	if isinstance(token_names, str):
		try:
			parsed = json.loads(token_names)
			if isinstance(parsed, list):
				return [str(n) for n in parsed]
		except (ValueError, TypeError):
			pass
		return [token_names]
	if isinstance(token_names, list):
		return [str(n) for n in token_names]
	return []
