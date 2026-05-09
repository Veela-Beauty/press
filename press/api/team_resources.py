# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Team-scoped resource lists used by Vue dialogs (token issuance, site move,
bench picker). Returns minimal fields, respects standard Frappe permissions.
"""
from __future__ import annotations

from typing import Any

import frappe

# Caps prevent runaway responses on huge teams. Picker UIs filter client-side
# below the cap; for sites we also accept a `q` param to filter server-side.
MAX_PICKER_RESULTS = 200


@frappe.whitelist()
def list_my_release_groups() -> list[dict[str, Any]]:
	"""Return Release Groups visible to the calling user.

	Uses standard Frappe permissions — System Users see all, regular users
	see only RGs in their team(s).
	"""
	return frappe.get_list(
		"Release Group",
		fields=["name", "title"],
		order_by="title asc",
		limit=MAX_PICKER_RESULTS,
	)


@frappe.whitelist()
def list_my_sites(q: str | None = None) -> list[dict[str, Any]]:
	"""Return Sites visible to the calling user.

	Args:
		q: optional substring filter applied server-side to the site name.
			Lets the picker handle teams with hundreds of sites without
			shipping the entire list to the browser.

	Excludes archived/broken sites; includes the bench (RG name) for grouping.
	"""
	filters: dict[str, Any] = {"status": ("in", ("Active", "Inactive", "Suspended"))}
	if q:
		filters["name"] = ("like", f"%{q}%")
	return frappe.get_list(
		"Site",
		fields=["name", "group"],
		filters=filters,
		order_by="name asc",
		limit=MAX_PICKER_RESULTS,
	)
