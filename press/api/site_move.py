# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe


def _get_site_basics(site: str) -> dict[str, Any] | None:
	"""Fetch the minimum site fields the Move-Site flow needs.

	Avoids loading the full Site doc (which carries domains, plans, marketplace
	data, etc.). Returns None if the site doesn't exist.
	"""
	row = frappe.db.get_value(
		"Site",
		site,
		["name", "group", "bench"],
		as_dict=True,
	)
	if not row:
		return None
	row["apps"] = {
		a.app for a in frappe.get_all(
			"Site App",
			filters={"parent": site},
			fields=["app"],
		)
	}
	return row


@frappe.whitelist()
def get_site_move_context(site: str) -> dict[str, Any]:
	"""Return everything the Move-Site dialog needs in one round-trip.

	Includes the site's current RG (so the empty-state CTA can offer to
	clone the current bench) and the eligible target list. Designed so
	the dialog never has to fetch more than once.
	"""
	site_basics = _get_site_basics(site)
	if not site_basics:
		frappe.throw(f"Site {site!r} not found", frappe.DoesNotExistError)

	current_bench = frappe.db.get_value(
		"Bench", site_basics["bench"], ["server"], as_dict=True
	)
	current_rg_title = frappe.db.get_value(
		"Release Group", site_basics["group"], "title"
	)
	eligible = (
		_compute_eligible_target_rgs(site_basics, current_bench.server)
		if current_bench else []
	)
	return {
		"site": site_basics["name"],
		"current_release_group": site_basics["group"],
		"current_release_group_title": current_rg_title or site_basics["group"],
		"current_bench": site_basics["bench"],
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
	site_basics = _get_site_basics(site)
	if not site_basics:
		return []
	current_bench = frappe.db.get_value(
		"Bench", site_basics["bench"], ["server"], as_dict=True
	)
	if not current_bench:
		return []
	return _compute_eligible_target_rgs(site_basics, current_bench.server)


def _compute_eligible_target_rgs(
	site_basics: dict[str, Any],
	current_server: str,
) -> list[dict[str, Any]]:
	"""Bulk-fetch implementation of the eligibility filter (3 queries total
	regardless of candidate count). Replaces the old per-candidate loop
	which ran 2*N queries (1 RG-App + 1 Bench per candidate).
	"""
	candidates = frappe.get_all(
		"Release Group",
		filters={"name": ("!=", site_basics["group"]), "enabled": 1},
		fields=["name", "title"],
		order_by="title asc",
		limit=500,
	)
	if not candidates:
		return []

	candidate_names = [rg["name"] for rg in candidates]

	# 1 query: all RG -> apps mapping
	rg_apps_rows = frappe.get_all(
		"Release Group App",
		filters={"parent": ("in", candidate_names)},
		fields=["parent", "app"],
	)
	apps_by_rg: dict[str, set[str]] = defaultdict(set)
	for r in rg_apps_rows:
		apps_by_rg[r.parent].add(r.app)

	# 1 query: all Active benches on the same server, indexed by RG
	bench_rows = frappe.get_all(
		"Bench",
		filters={
			"group": ("in", candidate_names),
			"status": "Active",
			"server": current_server,
		},
		fields=["group", "server"],
	)
	server_by_rg = {b.group: b.server for b in bench_rows}

	site_apps = site_basics["apps"]
	out = []
	for rg in candidates:
		rg_apps = apps_by_rg.get(rg["name"], set())
		if not site_apps.issubset(rg_apps):
			continue
		server = server_by_rg.get(rg["name"])
		if not server:
			continue
		out.append({
			"name": rg["name"],
			"title": rg["title"],
			"server": server,
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
