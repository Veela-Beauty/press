# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import frappe
from frappe.utils import add_to_date, now_datetime


def cleanup_expired_auth_attempts() -> None:
	"""Hard-delete Press MCP Auth Attempt rows older than 30 days.

	The brute-force guard only looks at the last 5 minutes; older rows
	provide no value and grow the table unbounded.
	"""
	cutoff = add_to_date(now_datetime(), days=-30)
	frappe.db.delete(
		"Press MCP Auth Attempt",
		{"creation": ("<", cutoff)},
	)
