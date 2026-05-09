# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from typing import Any

import frappe


@frappe.whitelist()
def get_site_move_context(site: str) -> dict[str, Any]:
	"""Return everything the Move-Site dialog needs in one round-trip.

	Includes the site's current RG (so the empty-state CTA can offer to
	clone the current bench) and the eligible target list. Designed so
	the dialog never has to fetch more than once.
	"""
	site_doc = frappe.get_doc("Site", site)
	current_bench = frappe.db.get_value("Bench", site_doc.bench, ["server"], as_dict=True)
	current_rg_title = frappe.db.get_value("Release Group", site_doc.group, "title")
	eligible = list_eligible_target_release_groups(site) if current_bench else []
	return {
		"site": site_doc.name,
		"current_release_group": site_doc.group,
		"current_release_group_title": current_rg_title or site_doc.group,
		"current_bench": site_doc.bench,
		"server": current_bench.server if current_bench else None,
		"eligible": eligible,
	}


@frappe.whitelist()
def list_eligible_target_release_groups(site: str) -> list[dict[str, Any]]:
	"""Return Release Groups this site CAN be moved to.

	Filters:
		- Not the site's current RG
		- On the same server (Press only supports same-server moves)
		- Has every app the site currently uses
		- Has at least one Active Bench

	Returns minimal fields for the picker: name, title, server, app_count.
	"""
	site_doc = frappe.get_doc("Site", site)
	site_apps = {a.app for a in site_doc.apps}
	current_bench = frappe.db.get_value("Bench", site_doc.bench, ["server"], as_dict=True)
	if not current_bench:
		return []

	candidates = frappe.get_all(
		"Release Group",
		filters={"name": ("!=", site_doc.group), "enabled": 1},
		fields=["name", "title"],
		order_by="title asc",
		limit=500,
	)

	out = []
	for rg in candidates:
		rg_apps = {
			a.app for a in frappe.get_all(
				"Release Group App",
				filters={"parent": rg.name},
				fields=["app"],
			)
		}
		if not site_apps.issubset(rg_apps):
			continue

		active_bench = frappe.db.get_value(
			"Bench",
			{"group": rg.name, "status": "Active", "server": current_bench.server},
			["name", "server"],
			as_dict=True,
		)
		if not active_bench:
			continue

		out.append({
			"name": rg.name,
			"title": rg.title,
			"server": active_bench.server,
			"app_count": len(rg_apps),
		})
	return out


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
