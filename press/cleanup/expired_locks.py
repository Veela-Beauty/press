# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import frappe
from frappe.utils import add_to_date, now_datetime


def cleanup_expired_locks() -> None:
	"""Hard-delete Press Lock rows that expired more than 7 days ago.

	Active locks are filtered by `revoked=0 AND expires_at > now()` at query time
	in the API, so expired ones don't BLOCK anything — but they accumulate in
	the table. Delete them after a 7-day grace window so the audit trail
	stays queryable for a week.
	"""
	cutoff = add_to_date(now_datetime(), days=-7)
	stale = frappe.get_all(
		"Press Lock",
		filters={"expires_at": ("<", cutoff)},
		pluck="name",
	)
	for name in stale:
		try:
			frappe.delete_doc("Press Lock", name, ignore_permissions=True)
		except Exception:
			frappe.log_error(
				title=f"Lock cleanup failed for {name}",
				message=frappe.get_traceback(),
			)
