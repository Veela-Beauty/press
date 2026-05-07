# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import frappe
from frappe.utils import now_datetime


def expire_sandbox_release_groups() -> None:
	"""Drop Release Groups whose clone_lifetime=sandbox and clone_expires_at has passed."""
	expired = frappe.get_all(
		"Release Group",
		filters={
			"clone_lifetime": "sandbox",
			"clone_expires_at": ("<", now_datetime()),
		},
		pluck="name",
	)
	for name in expired:
		try:
			_archive_release_group(name)
		except Exception:
			frappe.log_error(
				title=f"Sandbox cleanup failed for RG {name}",
				message=frappe.get_traceback(),
			)


def _archive_release_group(name: str) -> None:
	"""Archive sites on the RG, then mark RG disabled.

	Note: real site archive triggers agent jobs. The test suite mocks
	this function entirely; this body is the production code path.
	"""
	sites = frappe.get_all(
		"Site",
		filters={"group": name, "status": ("not in", ("Archived", "Suspended"))},
		pluck="name",
	)
	for site_name in sites:
		site = frappe.get_doc("Site", site_name)
		site.archive(reason="Sandbox clone TTL expired")

	rg = frappe.get_doc("Release Group", name)
	rg.enabled = 0
	rg.save(ignore_permissions=True)
