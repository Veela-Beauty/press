# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import frappe


def log_infra_action(host: str, unit: str, action: str, outcome: str, detail: str = "") -> None:
	"""Append an immutable audit row for every control action (R5)."""
	frappe.get_doc(
		{
			"doctype": "Infra Action Log",
			"actor": frappe.session.user,
			"host": host,
			"unit": unit,
			"action": action,
			"outcome": outcome,
			"detail": detail,
		}
	).insert(ignore_permissions=True)
