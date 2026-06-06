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
	# Durability (R5): commit the audit row in its own right so a later rollback
	# of the control request cannot erase the record of the attempt. Control
	# actions are external (Docker API / SSH), so there is no pending DB write
	# this would wrongly commit.
	frappe.db.commit()
