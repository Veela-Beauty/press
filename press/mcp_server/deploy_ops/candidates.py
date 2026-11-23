# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Deploy candidates over MCP: create one, schedule its build, read its status, and follow a new bench's provisioning (moved from deploy_flow.py in 0.7.54)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import now_datetime


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
		# Deploy Candidate doctype has no `status` column — derive it from the
		# most recent Deploy Candidate Build (which IS the runtime entity).
		# If no build has been scheduled, the candidate sits in 'Draft'.
		row = frappe.db.get_value(
			"Deploy Candidate",
			name,
			["name", "group"],
			as_dict=True,
		)
		latest_build = frappe.db.get_value(
			"Deploy Candidate Build",
			{"deploy_candidate": name},
			["name", "status", "build_start", "build_end"],
			order_by="creation desc",
			as_dict=True,
		)
		return {
			"kind": "candidate",
			"name": row.name,
			"release_group": row.group,
			"status": latest_build.status if latest_build else "Draft",
			"latest_build": latest_build.name if latest_build else None,
			"build_start": latest_build.build_start.isoformat()
			if latest_build and latest_build.build_start
			else None,
			"build_end": latest_build.build_end.isoformat()
			if latest_build and latest_build.build_end
			else None,
		}
	frappe.throw(
		f"No Deploy Candidate or Deploy Candidate Build found with name {name!r}",
		frappe.DoesNotExistError,
	)


# ---------------------------------------------------------------------------
# Bench provisioning progress — aggregate stage view
# ---------------------------------------------------------------------------

_BENCH_PROVISION_JOB_TYPES = (
	"New Bench",
	"Setup Bench",
	"Archive Bench",
	"Update Bench Configuration",
)


@frappe.whitelist()
def bench_provision_progress(bench_name: str) -> dict[str, Any]:
	"""Aggregate progress for a bench going through the provision chain.

	Replaces the 'is the filesystem populated yet?' polling pattern. Returns a
	single dict the caller can render as a progress UI:

	    {
	      "bench": "bench-0028-000005-press-f1",
	      "release_group": "bench-0028",
	      "candidate": "deploy-0028-000005",
	      "bench_status": "Active" | "Pending" | "Broken" | "Archived",
	      "stage": "build" | "new_bench" | "setup_bench" | "ready" | "failed",
	      "stage_label": "Cloning apps into bench (this takes 5-10 min)",
	      "elapsed_seconds": 387,
	      "chain": [
	         {step, status, job_name?, duration_seconds?, started_at?, ended_at?},
	         ...
	      ],
	      "dashboard_url": "https://.../dashboard/groups/<RG>/jobs",
	    }

	Args:
	- bench_name: Bench docname (e.g. 'bench-0028-000005-press-f1')
	"""
	if not frappe.db.exists("Bench", bench_name):
		frappe.throw(f"Bench {bench_name!r} not found", frappe.DoesNotExistError)

	bench = frappe.db.get_value(
		"Bench",
		bench_name,
		["name", "status", "candidate", "group", "creation", "server"],
		as_dict=True,
	)

	now = now_datetime()
	elapsed = int((now - bench.creation).total_seconds()) if bench.creation else 0

	chain: list[dict[str, Any]] = []

	# 1. Build phase — Deploy Candidate Build
	if bench.candidate:
		build = frappe.db.sql(
			"""
			SELECT name, status, build_start, build_end
			FROM `tabDeploy Candidate Build`
			WHERE deploy_candidate = %s
			ORDER BY creation DESC LIMIT 1
			""",
			(bench.candidate,),
			as_dict=True,
		)
		if build:
			b = build[0]
			chain.append({
				"step": "build",
				"label": "Docker image build",
				"status": b.status,
				"job_name": b.name,
				"started_at": b.build_start,
				"ended_at": b.build_end,
				"duration_seconds": (
					int((b.build_end - b.build_start).total_seconds())
					if b.build_start and b.build_end
					else None
				),
			})

	# 2-N. Provision Agent Jobs for this bench, in creation order
	agent_jobs = frappe.db.sql(
		"""
		SELECT name, job_type, status, creation, end, start
		FROM `tabAgent Job`
		WHERE bench = %s
		ORDER BY creation ASC
		""",
		(bench_name,),
		as_dict=True,
	)
	for j in agent_jobs:
		chain.append({
			"step": j.job_type.lower().replace(" ", "_"),
			"label": j.job_type,
			"status": j.status,
			"job_name": j.name,
			"started_at": j.start or j.creation,
			"ended_at": j.end,
			"duration_seconds": (
				int((j.end - (j.start or j.creation)).total_seconds())
				if j.end
				else None
			),
		})

	# Last. Update Site Migrate jobs whose Site Update.destination_bench == this bench
	site_updates = frappe.db.sql(
		"""
		SELECT su.name AS update_name, su.site, su.status AS update_status,
		       su.update_start, su.update_end, su.update_job
		FROM `tabSite Update` su
		WHERE su.destination_bench = %s
		ORDER BY su.creation DESC LIMIT 3
		""",
		(bench_name,),
		as_dict=True,
	)
	for u in site_updates:
		chain.append({
			"step": "site_migrate",
			"label": f"Site migrate: {u.site}",
			"status": u.update_status,
			"job_name": u.update_job,
			"site": u.site,
			"update_name": u.update_name,
			"started_at": u.update_start,
			"ended_at": u.update_end,
		})

	# Derive overall stage from the chain + Bench.status
	stage, stage_label = _derive_provision_stage(bench, chain)

	dashboard_url = (
		f"{frappe.utils.get_url().rstrip('/')}/dashboard/groups/{bench.group}/jobs"
	)

	return {
		"bench": bench.name,
		"release_group": bench.group,
		"candidate": bench.candidate,
		"server": bench.server,
		"bench_status": bench.status,
		"stage": stage,
		"stage_label": stage_label,
		"elapsed_seconds": elapsed,
		"chain": chain,
		"dashboard_url": dashboard_url,
	}


def _derive_provision_stage(bench, chain: list[dict]) -> tuple[str, str]:
	"""Boil the chain down to one (stage, label) tuple for the UI."""
	if bench.status == "Archived":
		return "archived", "Bench has been archived"
	if bench.status == "Broken":
		return "failed", "Bench failed to provision — inspect failed step"

	by_step = {step["step"]: step for step in chain}

	# Build phase — only present when candidate has a Deploy Candidate Build row
	build = by_step.get("build")
	if build:
		if build["status"] in ("Pending", "Running", "Preparing", "Scheduled"):
			return "build", "Building Docker image (~3 min)"
		if build["status"] == "Failure":
			return "failed", "Docker build failed — see Deploy Candidate Build"

	new_bench = by_step.get("new_bench")
	if new_bench:
		if new_bench["status"] in ("Pending", "Running"):
			return "new_bench", "Starting bench container on app server"
		if new_bench["status"] == "Failure":
			return "failed", "New Bench job failed — agent could not start container"

	setup_bench = by_step.get("setup_bench")
	if setup_bench:
		if setup_bench["status"] in ("Pending", "Running"):
			return "setup_bench", "Cloning apps into bench (this takes 5-10 min)"
		if setup_bench["status"] == "Failure":
			return "failed", "Setup Bench job failed — app clone or install error"

	# If the bench is Active and any site migrate has flipped, we're done
	migrates = [s for s in chain if s["step"] == "site_migrate"]
	if migrates:
		latest = migrates[0]  # most recent first
		if latest["status"] == "Running":
			return "site_migrate", f"Migrating site: {latest.get('site')}"
		if latest["status"] == "Success":
			return "ready", "Bench is ready; site has flipped to new bench"
		if latest["status"] in ("Failure", "Recovered"):
			return "failed", f"Site migrate ended {latest['status']!s} — check traceback"

	# Active bench with no failed migrate = ready (sites may not have flipped yet)
	if bench.status == "Active":
		return "ready", "Bench is Active and ready to receive sites"

	# Default: still in early provisioning, no agent jobs yet
	return "queued", "Provisioning queued — waiting for first agent job"
