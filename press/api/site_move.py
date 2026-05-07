# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from typing import Any

import frappe


@frappe.whitelist()
def move_to_release_group(
	site: str,
	target_release_group: str,
	deactivate: bool = True,
	skip_failing_patches: bool = False,
) -> dict[str, Any]:
	"""Move a Site from its current Release Group to another by resolving
	the latest Active Bench of the target RG.

	Validates:
		- Target RG is not the site's current group.
		- Target RG's apps include all apps the site currently has.
		- Target RG has at least one Active Bench.
	"""
	site_doc = frappe.get_doc("Site", site)
	target_rg_doc = frappe.get_doc("Release Group", target_release_group)

	if site_doc.group == target_release_group:
		frappe.throw(
			"Site is already on this Release Group.",
			frappe.ValidationError,
		)

	site_apps = {a.app for a in site_doc.apps}
	target_apps = {a.app for a in target_rg_doc.apps}
	missing = site_apps - target_apps
	if missing:
		frappe.throw(
			f"Target Release Group is missing apps: {sorted(missing)}",
			frappe.ValidationError,
		)

	target_bench = frappe.db.get_value(
		"Bench",
		{"group": target_release_group, "status": "Active"},
		"name",
		order_by="creation desc",
	)
	if not target_bench:
		frappe.throw(
			f"Release Group {target_release_group!r} has no Active Bench. "
			"Wait for a deploy to complete or trigger one.",
			frappe.ValidationError,
		)

	job = site_doc.move_to_bench(
		bench=target_bench,
		deactivate=deactivate,
		skip_failing_patches=skip_failing_patches,
	)

	return {
		"job": getattr(job, "name", None),
		"target_bench": target_bench,
		"target_release_group": target_release_group,
	}
