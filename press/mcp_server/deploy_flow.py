# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Deploy / release / site-update workflow tools for MCP agents.

These wrap existing Press whitelisted methods so an agent can drive a full
build → deploy → migrate workflow without press-ctrl SSH access.

All resource scoping is enforced by the MCP server at dispatch time
(server._extract_target). This module just exposes thin wrappers.
"""
from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import add_to_date, now_datetime


@frappe.whitelist()
def app_release_approve(release_name: str) -> dict[str, Any]:
	"""Flip an App Release from Draft to Approved.

	Mirrors what an operator does in the Frappe Desk to mark an App Release
	for inclusion in the next Deploy Candidate.
	"""
	doc = frappe.get_doc("App Release", release_name)
	if doc.status == "Approved":
		return {"name": release_name, "status": "Approved", "already_approved": True}
	doc.status = "Approved"
	doc.save(ignore_permissions=True)
	return {"name": release_name, "status": "Approved"}


@frappe.whitelist()
def release_group_create_deploy_candidate(
	name: str,
	apps_to_update: list | str | None = None,
) -> dict[str, Any]:
	"""Create a new Deploy Candidate for the Release Group.

	Returns the new candidate's docname (or None if the RG is disabled).
	"""
	rg = frappe.get_doc("Release Group", name)
	candidate = rg.create_deploy_candidate(apps_to_update=apps_to_update)
	if candidate is None:
		frappe.throw(
			f"Release Group {name!r} is disabled; cannot create Deploy Candidate",
			frappe.ValidationError,
		)
	return {"candidate": candidate.name, "release_group": name}


@frappe.whitelist()
def deploy_candidate_schedule_build(
	candidate_name: str,
	run_now: bool = True,
) -> dict[str, Any]:
	"""Schedule build + deploy for a Deploy Candidate. Returns the build job name."""
	doc = frappe.get_doc("Deploy Candidate", candidate_name)
	result = doc.schedule_build_and_deploy(run_now=run_now)
	# result shape: {"error": False, "name": "<build-name>"}
	return {
		"build": result.get("name"),
		"candidate": candidate_name,
		"error": result.get("error", False),
	}


@frappe.whitelist()
def deploy_candidate_status(name: str) -> dict[str, Any]:
	"""Status of a Deploy Candidate Build OR a Deploy Candidate.

	Tries Deploy Candidate Build first (the runtime entity), falls back to
	Deploy Candidate. Returns a stable shape regardless of which it found.
	"""
	if frappe.db.exists("Deploy Candidate Build", name):
		row = frappe.db.get_value(
			"Deploy Candidate Build",
			name,
			["name", "status", "build_start", "build_end", "deploy_candidate"],
			as_dict=True,
		)
		return {
			"kind": "build",
			"name": row.name,
			"candidate": row.deploy_candidate,
			"status": row.status,
			"build_start": row.build_start.isoformat() if row.build_start else None,
			"build_end": row.build_end.isoformat() if row.build_end else None,
		}
	if frappe.db.exists("Deploy Candidate", name):
		row = frappe.db.get_value(
			"Deploy Candidate",
			name,
			["name", "status", "group"],
			as_dict=True,
		)
		return {
			"kind": "candidate",
			"name": row.name,
			"release_group": row.group,
			"status": row.status,
		}
	frappe.throw(
		f"No Deploy Candidate or Deploy Candidate Build found with name {name!r}",
		frappe.DoesNotExistError,
	)


@frappe.whitelist()
def site_schedule_update(
	site_name: str,
	skip_failing_patches: bool = False,
	skip_backups: bool = False,
) -> dict[str, Any]:
	"""Schedule a Site Update (migrate to latest bench in same Release Group)."""
	site = frappe.get_doc("Site", site_name)
	job_name = site.schedule_update(
		skip_failing_patches=skip_failing_patches,
		skip_backups=skip_backups,
	)
	return {"site": site_name, "site_update": job_name}


@frappe.whitelist()
def site_status(
	site_name: str,
	jobs_window_minutes: int = 120,
	jobs_limit: int = 10,
) -> dict[str, Any]:
	"""Current site bench + status + recent agent jobs.

	The recent_agent_jobs list is the polling primitive — agents can call
	this repeatedly until the desired job lands in Success or the bench flips.
	Window defaults to 120 minutes so that long-running deploys (build + push +
	migrate cycle commonly takes 10-30 min) stay visible across the full poll
	loop. Use `agent_job_list` for finer control.
	"""
	row = frappe.db.get_value(
		"Site",
		site_name,
		["name", "bench", "status", "modified"],
		as_dict=True,
	)
	if not row:
		frappe.throw(f"Site {site_name!r} does not exist", frappe.DoesNotExistError)
	jobs_window_minutes = max(1, min(1440, int(jobs_window_minutes)))
	jobs_limit = max(1, min(100, int(jobs_limit)))
	since = add_to_date(now_datetime(), minutes=-jobs_window_minutes)
	jobs = frappe.get_all(
		"Agent Job",
		filters={"site": site_name, "creation": (">=", since)},
		fields=["name", "job_type", "status", "creation"],
		order_by="creation desc",
		limit=jobs_limit,
	)
	for j in jobs:
		if j.get("creation"):
			j["creation"] = j["creation"].isoformat()
	return {
		"name": row.name,
		"bench": row.bench,
		"status": row.status,
		"last_modified": row.modified.isoformat() if row.modified else None,
		"recent_agent_jobs": jobs,
	}


@frappe.whitelist()
def agent_job_list(
	site: str | None = None,
	status: str | None = None,
	since_minutes: int = 60,
	limit: int = 50,
) -> list[dict[str, Any]]:
	"""List recent Agent Jobs filtered by site/status/window."""
	since_minutes = max(1, min(1440, int(since_minutes)))
	limit = max(1, min(500, int(limit)))
	since = add_to_date(now_datetime(), minutes=-since_minutes)
	filters: dict[str, Any] = {"creation": (">=", since)}
	if site:
		filters["site"] = site
	if status:
		filters["status"] = status
	rows = frappe.get_all(
		"Agent Job",
		filters=filters,
		fields=["name", "site", "job_type", "status", "creation", "bench"],
		order_by="creation desc",
		limit=limit,
	)
	for r in rows:
		if r.get("creation"):
			r["creation"] = r["creation"].isoformat()
	return rows


@frappe.whitelist()
def wait_for_bench_flip(
	site_name: str,
	target_candidate: str,
) -> dict[str, Any]:
	"""Async-style poll: check whether the site's current bench was built from
	the target Deploy Candidate. Returns immediately. Caller re-polls.

	Status values:
		flipped: site is now on a bench produced by target_candidate
		pending: site is still on an older bench
	"""
	current_bench = frappe.db.get_value("Site", site_name, "bench")
	if not current_bench:
		frappe.throw(
			f"Site {site_name!r} does not exist or has no bench",
			frappe.DoesNotExistError,
		)
	bench_candidate = frappe.db.get_value("Bench", current_bench, "candidate")
	flipped = bench_candidate == target_candidate
	return {
		"status": "flipped" if flipped else "pending",
		"site": site_name,
		"current_bench": current_bench,
		"current_candidate": bench_candidate,
		"target_candidate": target_candidate,
	}
