# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Dashboard-facing helpers for the Vue MCP panel (Obj 4c uses these too)."""
from __future__ import annotations

import json
from typing import Any

import frappe
from frappe.utils import now_datetime


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
		],
		order_by="creation desc",
		limit=100,
	)
	for row in rows:
		try:
			row["scope"] = json.loads(row.get("scope") or "[]")
		except (ValueError, TypeError):
			row["scope"] = []
		row["status"] = _status_for(row)
	return rows


def _status_for(row: dict) -> str:
	if row.get("revoked"):
		return "revoked"
	expires = row.get("expires_at")
	if expires and expires < now_datetime():
		return "expired"
	return "active"
