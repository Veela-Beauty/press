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
		flipped              site is now on a bench produced by target_candidate
		pending              site is on older bench AND Update Site Migrate
		                     job is in-flight — keep polling
		no_build             target_candidate has no Deploy Candidate Build —
		                     the build was never triggered. STOP polling.
		flip_not_triggered   build succeeded but no Update Site Migrate job
		                     exists in the last 30 min — site_update was
		                     never called. STOP polling, call
		                     site_update_and_wait instead.

	Safety gates (server-enforced, can't be bypassed by agent):
		Gate B (no_build)            return early with hint instead of looping
		Gate C (flip_not_triggered)  detect missing site_update trigger
		Gate D (scheduler auto-kick) if Undelivered jobs >2min old exist for
		                             this site, run poll_pending_jobs ONCE
		                             before returning. Idempotent.
	"""
	current_bench = frappe.db.get_value("Site", site_name, "bench")
	if not current_bench:
		frappe.throw(
			f"Site {site_name!r} does not exist or has no bench",
			frappe.DoesNotExistError,
		)
	bench_candidate = frappe.db.get_value("Bench", current_bench, "candidate")
	flipped = bench_candidate == target_candidate

	# Already flipped — short-circuit. No gate checks needed.
	if flipped:
		return {
			"status": "flipped",
			"site": site_name,
			"current_bench": current_bench,
			"current_candidate": bench_candidate,
			"target_candidate": target_candidate,
		}

	# Gate B: does the target candidate even have a Build?
	# If no Deploy Candidate Build row exists, the agent is waiting on a
	# phantom — the build was never triggered. Return early with the fix.
	build_exists = frappe.db.exists("Deploy Candidate Build", {"deploy_candidate": target_candidate})
	if not build_exists:
		# Could be: candidate doesn't exist OR exists but no build scheduled
		cand_exists = frappe.db.exists("Deploy Candidate", target_candidate)
		return {
			"status": "no_build",
			"site": site_name,
			"current_bench": current_bench,
			"current_candidate": bench_candidate,
			"target_candidate": target_candidate,
			"hint": (
				f"No Deploy Candidate Build exists for {target_candidate!r}. "
				+ (
					"The candidate exists but no build was scheduled — call "
					"deploy_candidate_schedule_build(candidate_name=...) or "
					"bench_deploy_and_wait(...)."
					if cand_exists
					else "The Deploy Candidate itself does not exist — check "
					"the target_candidate name."
				)
			),
		}

	# Gate D (auto-kick): if Undelivered jobs older than 2min exist for this
	# site, the poll_pending_jobs scheduler likely stalled. Fire ONE manual
	# poll to sync the backlog. Idempotent — Press's own scheduler does this
	# every 60s, so we're just helping it catch up.
	stale_undelivered = frappe.db.count(
		"Agent Job",
		filters={
			"site": site_name,
			"status": "Undelivered",
			"creation": ("<", add_to_date(None, minutes=-2)),
		},
	)
	if stale_undelivered > 0:
		try:
			from press.press.doctype.agent_job.agent_job import poll_pending_jobs as _ppj
			_ppj()
			frappe.db.commit()
		except Exception as e:  # noqa: BLE001 — best-effort, never fail the poll
			frappe.log_error(
				title="wait_for_bench_flip: Gate D poll_pending_jobs kick failed",
				message=str(e),
			)
		# Re-read in case the kick already flipped the site
		current_bench = frappe.db.get_value("Site", site_name, "bench")
		bench_candidate = frappe.db.get_value("Bench", current_bench, "candidate")
		if bench_candidate == target_candidate:
			return {
				"status": "flipped",
				"site": site_name,
				"current_bench": current_bench,
				"current_candidate": bench_candidate,
				"target_candidate": target_candidate,
				"gate_d_triggered": True,
				"hint": "Gate D auto-kicked poll_pending_jobs and the flip resolved.",
			}

	# Gate C/E: inspect site_update history for this site
	# C: build Success but no migrate job → flip_not_triggered
	# E: migrate FAILED and Recover rolled back → flip_failed (don't poll)
	build_row = frappe.db.get_value(
		"Deploy Candidate Build",
		{"deploy_candidate": target_candidate},
		["name", "status"],
		order_by="creation desc",
		as_dict=True,
	)
	if build_row and build_row.status == "Success":
		recent_migrate_jobs = frappe.get_all(
			"Agent Job",
			filters={
				"site": site_name,
				"job_type": ("in", ["Update Site Migrate", "Update Site Recover", "Update Site Migrate Steps"]),
				"creation": (">", add_to_date(None, minutes=-30)),
			},
			fields=["name", "job_type", "status", "creation"],
			order_by="creation desc",
			limit=20,
		)
		# Gate C: no migrate job exists for this site
		if not recent_migrate_jobs:
			return {
				"status": "flip_not_triggered",
				"site": site_name,
				"current_bench": current_bench,
				"current_candidate": bench_candidate,
				"target_candidate": target_candidate,
				"build_status": build_row.status,
				"hint": (
					f"Build {build_row.name} for {target_candidate} is Success but "
					f"no Update Site Migrate job exists for {site_name} in the "
					f"last 30 min. On standalone Press, sites don't auto-flip — "
					f"call site_update_and_wait(site_name={site_name!r}, "
					f"target_candidate={target_candidate!r}) to trigger the flip."
				),
			}
		# Gate E: most recent migrate run finished (Failure or Recover Success)
		# and site is STILL on old bench → flip failed and rolled back.
		# Look for the most recent Update Site Migrate result.
		migrate_results = [j for j in recent_migrate_jobs if j.job_type == "Update Site Migrate"]
		if migrate_results:
			last_migrate = migrate_results[0]
			recover_after = [
				j for j in recent_migrate_jobs
				if j.job_type == "Recover Failed Site Migrate" and j.creation > last_migrate.creation
			]
			if last_migrate.status == "Failure" and recover_after:
				return {
					"status": "flip_failed",
					"site": site_name,
					"current_bench": current_bench,
					"current_candidate": bench_candidate,
					"target_candidate": target_candidate,
					"build_status": build_row.status,
					"failed_migrate_job": last_migrate.name,
					"recover_job": recover_after[0].name,
					"hint": (
						f"Most recent Update Site Migrate for {site_name} "
						f"({last_migrate.name}) FAILED at "
						f"{last_migrate.creation.isoformat()}. Site was rolled "
						f"back to old bench by Recover job {recover_after[0].name}. "
						f"Call agent_job_traceback(job_name={last_migrate.name!r}) "
						f"to see the migrate error before retrying."
					),
				}
			if last_migrate.status == "Failure" and not recover_after:
				return {
					"status": "flip_failed",
					"site": site_name,
					"current_bench": current_bench,
					"current_candidate": bench_candidate,
					"target_candidate": target_candidate,
					"build_status": build_row.status,
					"failed_migrate_job": last_migrate.name,
					"hint": (
						f"Update Site Migrate {last_migrate.name} for {site_name} "
						f"FAILED. No Recover job has run yet — site may be in a "
						f"half-migrated state. Call agent_job_traceback("
						f"job_name={last_migrate.name!r}) to see the error."
					),
				}

	# Normal pending — flip is in-flight or scheduled
	return {
		"status": "pending",
		"site": site_name,
		"current_bench": current_bench,
		"current_candidate": bench_candidate,
		"target_candidate": target_candidate,
	}


@frappe.whitelist()
def list_sites_on_release_group(release_group: str, status: str | None = None) -> list[dict[str, Any]]:
	"""List sites whose bench belongs to the given Release Group, team-scoped.

	`press.api.site.all()` doesn't accept a `release_group` filter — it filters
	by status/tag/team. This shim does the cluster->bench->site join for you.
	Useful for agents wanting "show me every site that'd be touched by a bench
	rebuild of RG X" without manually iterating press.api.site.all().

	Returns list of {name, status, bench, team, host_name}. Team-scoped:
	non-System users only see sites owned by their team.
	"""
	from press.utils import get_current_team

	filters: dict[str, Any] = {"group": release_group}
	if status:
		filters["status"] = status
	if frappe.session.data.user_type != "System User":
		filters["team"] = get_current_team()
	return frappe.get_all(
		"Site",
		filters=filters,
		fields=["name", "status", "bench", "team", "host_name", "group"],
		order_by="creation desc",
		limit=200,
	)


@frappe.whitelist()
def bench_set_app_branch(
	release_group: str,
	app: str,
	branch: str,
) -> dict[str, Any]:
	"""Change the Git branch the App Source uses for a Release Group.

	This is what an operator does in the Desk to point an app at a feature
	branch before triggering a new Deploy Candidate. Without this tool an
	agent has to either (a) merge the feature branch into whatever branch
	Press is configured for, or (b) ask a human to change the branch in
	the Desk UI.

	Args:
		release_group: Release Group docname, e.g. 'bench-0006'
		app: app name, e.g. 'erp_selfstorage'
		branch: target git branch name, e.g. 'refactor/usage-type-as-license'

	Returns:
		{release_group, app, source, old_branch, new_branch}.

	Notes:
		- The branch must exist on the configured repository — if it doesn't,
		  the next Deploy Candidate Build will fail at git-fetch time. We don't
		  pre-validate against GitHub here (no token plumbing in MCP context).
		- After calling this, trigger release_group_create_deploy_candidate +
		  deploy_candidate_schedule_build to actually deploy the new branch.
		  Or use bench_deploy_and_wait once you have the candidate.
	"""
	# Find the App Source for this (RG, app) pair. RG → ReleaseGroupApp child
	# → source. We use the source's `branch` field; changing it affects every
	# RG that shares this source. If you want per-RG branch isolation, create
	# a new App Source first (out of scope for this tool).
	source = frappe.db.get_value(
		"Release Group App",
		{"parent": release_group, "app": app},
		"source",
	)
	if not source:
		frappe.throw(
			f"App {app!r} is not in Release Group {release_group!r}",
			frappe.DoesNotExistError,
		)
	src_doc = frappe.get_doc("App Source", source)
	old_branch = src_doc.branch
	if old_branch == branch:
		return {
			"release_group": release_group,
			"app": app,
			"source": source,
			"old_branch": old_branch,
			"new_branch": branch,
			"unchanged": True,
		}
	src_doc.branch = branch
	src_doc.save(ignore_permissions=False)  # respects user's permissions on App Source
	frappe.db.commit()
	return {
		"release_group": release_group,
		"app": app,
		"source": source,
		"old_branch": old_branch,
		"new_branch": branch,
		"unchanged": False,
	}


@frappe.whitelist()
def agent_health(server: str, lookback_minutes: int = 10) -> dict[str, Any]:
	"""Diagnose whether an app server's agent is healthy, slow, or stuck.

	Derived from Press-side Agent Job records (no agent-side polling needed).
	Stops the "every job is Pending so agent must be dead" misdiagnosis that
	led to multiple unnecessary agent restarts in May 2026.

	Args:
		server: App server docname, e.g. 'press-f1.sandbox.mvpstorm.com'.
		lookback_minutes: Window to consider for activity (default 10, max 60).

	Returns:
		{
			"server": <server>,
			"verdict": "healthy" | "slow" | "stuck" | "no_activity",
			"reason": <human-readable>,
			"recent_jobs": {
				"total": N,
				"by_status": {"Pending": X, "Running": Y, "Success": Z, "Failure": W, "Undelivered": V},
			},
			"last_success_seconds_ago": <int or null>,
			"last_modified_seconds_ago": <int or null>,
			"running_jobs": [{name, job_type, site, age_seconds}, ...],
			"undelivered_jobs": [{name, job_type, site, age_seconds}, ...],
		}

	Verdict rules:
		healthy        — at least one Success in lookback window
		slow           — Running jobs exist + their modified is fresh (<2min ago)
		                 OR last Success >lookback but a Running job's modified
		                 is fresh — agent IS working, just on a long task
		stuck          — Undelivered jobs >2min old AND no recent modified
		                 activity — Press queued but agent isn't pulling
		no_activity    — lookback window is empty (agent may be idle, or this
		                 server has nothing scheduled — don't assume broken)

	Don't restart the agent on a "slow" verdict — restarting a busy worker
	mid-migrate corrupts the live DB. Wait on "slow"; investigate on "stuck".
	"""
	from frappe.utils import add_to_date, now_datetime

	lookback_minutes = max(1, min(60, int(lookback_minutes)))
	cutoff = add_to_date(None, minutes=-lookback_minutes)
	now = now_datetime()

	jobs = frappe.get_all(
		"Agent Job",
		filters={"server": server, "creation": (">", cutoff)},
		fields=["name", "job_type", "site", "status", "creation", "modified"],
		order_by="modified desc",
		limit=200,
	)

	by_status: dict[str, int] = {}
	last_success: Any = None
	last_modified: Any = None
	running_jobs: list[dict] = []
	undelivered_jobs: list[dict] = []

	for j in jobs:
		by_status[j.status] = by_status.get(j.status, 0) + 1
		if j.status == "Success" and (last_success is None or j.modified > last_success):
			last_success = j.modified
		if last_modified is None or j.modified > last_modified:
			last_modified = j.modified
		if j.status == "Running":
			running_jobs.append({
				"name": j.name,
				"job_type": j.job_type,
				"site": j.site,
				"age_seconds": int((now - j.modified).total_seconds()),
			})
		elif j.status == "Undelivered":
			undelivered_jobs.append({
				"name": j.name,
				"job_type": j.job_type,
				"site": j.site,
				"age_seconds": int((now - j.creation).total_seconds()),
			})

	# Derive verdict
	verdict: str
	reason: str
	last_success_age = int((now - last_success).total_seconds()) if last_success else None
	last_modified_age = int((now - last_modified).total_seconds()) if last_modified else None

	if not jobs:
		verdict = "no_activity"
		reason = (
			f"No Agent Job rows in the last {lookback_minutes} min for {server!r}. "
			f"Could mean idle server (no scheduled work) — NOT necessarily broken. "
			f"Try a longer lookback or check Press scheduler."
		)
	elif last_success_age is not None and last_success_age < lookback_minutes * 60:
		verdict = "healthy"
		reason = (
			f"Last Success was {last_success_age}s ago. Agent is processing jobs."
		)
	elif running_jobs and min(j["age_seconds"] for j in running_jobs) < 120:
		verdict = "slow"
		reason = (
			f"Agent has {len(running_jobs)} Running job(s) with fresh modified "
			f"(youngest {min(j['age_seconds'] for j in running_jobs)}s). "
			f"It's working — likely a long-running task (migrate, large backup, build). "
			f"DO NOT restart — wait for current job to finish."
		)
	elif undelivered_jobs and min(j["age_seconds"] for j in undelivered_jobs) > 120:
		verdict = "stuck"
		reason = (
			f"{len(undelivered_jobs)} Undelivered job(s) older than 2min and no "
			f"recent Success/Running activity. Press queued these but the agent "
			f"isn't pulling them. Check agent process: "
			f"`ssh root@<server> supervisorctl status agent:`"
		)
	else:
		verdict = "slow"
		reason = (
			f"No Success in window, no obvious stuck pattern. Last modified "
			f"{last_modified_age}s ago. Probably mid-job — wait before restarting."
		)

	return {
		"server": server,
		"verdict": verdict,
		"reason": reason,
		"recent_jobs": {"total": len(jobs), "by_status": by_status},
		"last_success_seconds_ago": last_success_age,
		"last_modified_seconds_ago": last_modified_age,
		"running_jobs": running_jobs,
		"undelivered_jobs": undelivered_jobs[:10],  # cap noise
		"lookback_minutes": lookback_minutes,
	}


@frappe.whitelist()
def bench_deploy_and_wait(
	name: str,
	apps: list[dict] | str,
	site_name: str,
	max_wait_seconds: int = 1500,
	poll_interval_seconds: int = 30,
) -> dict[str, Any]:
	"""Trigger a deploy + block until the site's bench flips to the new
	Deploy Candidate, or timeout. Single MCP call covers the entire wait.

	Args:
		name: Release Group docname, e.g. 'bench-0005'
		apps: list of {app, release, hash} dicts (same shape as bench_deploy).
			Get from bench_deploy_information(name).apps[*].releases[0].
			Accepts a JSON string too — MCP HTTP layer sometimes stringifies lists.
		site_name: Site FQDN to watch. The deploy may affect multiple sites
			on the same RG; this method only waits for the named one to flip.
		max_wait_seconds: hard cap (default 1500 = 25 min; leaves 5 min headroom
			under Press's 1800s gunicorn timeout). Returns status='timeout'
			beyond this — agent can re-call to keep waiting.
		poll_interval_seconds: how often to re-check (default 30s). Min 5s.

	Returns:
		{
			"candidate": <Deploy Candidate docname>,   # always set
			"status": "flipped" | "timeout",
			"elapsed_seconds": <int>,
			"site": <site_name>,
			"current_bench": <bench docname after flip / when polled last>,
			"current_candidate": <its candidate>,
			"target_candidate": <the new candidate we waited for>,
		}

	Use this INSTEAD of bench_deploy + a manual loop on wait_for_bench_flip.
	The single-call shape means the agent doesn't have to manage its own
	timer + re-poll. Long-running HTTP request (up to max_wait_seconds) — safe
	within Press's gunicorn 1800s timeout.
	"""
	import json
	import time

	from press.api.bench import deploy as _bench_deploy

	# Accept apps as JSON string (some MCP HTTP layers stringify lists)
	if isinstance(apps, str):
		apps = json.loads(apps)
	if not isinstance(apps, list) or not all(isinstance(a, dict) for a in apps):
		frappe.throw(
			"apps must be a list of dicts with {app, release, hash} keys; "
			f"got {type(apps).__name__}",
			frappe.ValidationError,
		)

	poll_interval = max(5, int(poll_interval_seconds))
	max_wait = max(poll_interval, int(max_wait_seconds))

	# Step 1 — trigger the deploy. Returns the Deploy Candidate docname.
	candidate = _bench_deploy(name=name, apps=apps)
	if isinstance(candidate, dict):
		# defensive — _bench_deploy normally returns a string but in case
		candidate = candidate.get("name") or candidate.get("candidate") or str(candidate)

	# Step 2 — poll until flip or timeout. Frappe HTTP requests are blocked
	# from sleeping inside a transaction; commit each iteration so reads
	# pick up the agent's writes when the bench flips.
	start = time.monotonic()
	deadline = start + max_wait
	last_poll: dict[str, Any] = {}
	while time.monotonic() < deadline:
		frappe.db.commit()
		last_poll = wait_for_bench_flip(site_name=site_name, target_candidate=candidate)
		if last_poll["status"] == "flipped":
			elapsed = int(time.monotonic() - start)
			return {
				"candidate": candidate,
				"status": "flipped",
				"elapsed_seconds": elapsed,
				**{k: v for k, v in last_poll.items() if k != "status"},
			}
		time.sleep(poll_interval)

	elapsed = int(time.monotonic() - start)
	return {
		"candidate": candidate,
		"status": "timeout",
		"elapsed_seconds": elapsed,
		**{k: v for k, v in last_poll.items() if k != "status"},
	}


@frappe.whitelist()
def agent_job_traceback(job_name: str, output_chars: int = 4000) -> dict[str, Any]:
	"""One-shot diagnostic for a stuck/failed Agent Job.

	Returns status + tail of output + tail of traceback in a single call —
	replaces the 4-roundtrip "ssh press-ctrl, bench console, get_doc, print"
	dance an agent otherwise has to do. Use whenever an Agent Job lands in
	Failure / Pending / Undelivered for more than a couple of minutes and the
	agent needs to see the actual error before deciding to restart anything.
	"""
	output_chars = max(500, min(20000, int(output_chars)))
	if not frappe.db.exists("Agent Job", job_name):
		frappe.throw(
			f"Agent Job {job_name!r} does not exist",
			frappe.DoesNotExistError,
		)
	doc = frappe.get_doc("Agent Job", job_name)
	output = doc.output or ""
	traceback = doc.traceback or ""
	now = now_datetime()
	return {
		"name": doc.name,
		"status": doc.status,
		"job_type": doc.job_type,
		"site": doc.site,
		"server": doc.server,
		"creation": doc.creation.isoformat() if doc.creation else None,
		"modified": doc.modified.isoformat() if doc.modified else None,
		"age_seconds": int((now - doc.creation).total_seconds()) if doc.creation else None,
		"output_tail": output[-output_chars:],
		"traceback_tail": traceback[-output_chars:],
		"output_truncated": len(output) > output_chars,
		"traceback_truncated": len(traceback) > output_chars,
	}


@frappe.whitelist()
def site_update_and_wait(
	site_name: str,
	target_candidate: str,
	skip_failing_patches: bool = False,
	skip_backups: bool = False,
	max_wait_seconds: int = 1500,
	poll_interval_seconds: int = 30,
) -> dict[str, Any]:
	"""Trigger a Site Update (migrate to latest bench) + block until flipped.

	On standalone Press setups, a successful Deploy Candidate Build does NOT
	auto-flip sites onto the new bench — each site needs an explicit
	site_update call. This wraps schedule_update + poll into one blocking
	call so an agent doesn't have to manage the two-step dance manually.
	Companion to bench_deploy_and_wait: build → then call this per site.
	"""
	import time

	poll_interval = max(5, int(poll_interval_seconds))
	max_wait = max(poll_interval, int(max_wait_seconds))

	site = frappe.get_doc("Site", site_name)
	job_name = site.schedule_update(
		skip_failing_patches=skip_failing_patches,
		skip_backups=skip_backups,
	)
	frappe.db.commit()

	start = time.monotonic()
	deadline = start + max_wait
	last_poll: dict[str, Any] = {}
	while time.monotonic() < deadline:
		frappe.db.commit()
		last_poll = wait_for_bench_flip(site_name=site_name, target_candidate=target_candidate)
		if last_poll["status"] == "flipped":
			elapsed = int(time.monotonic() - start)
			return {
				"site": site_name,
				"status": "flipped",
				"site_update_job": job_name,
				"elapsed_seconds": elapsed,
				**{k: v for k, v in last_poll.items() if k not in ("status", "site")},
			}
		time.sleep(poll_interval)

	elapsed = int(time.monotonic() - start)
	return {
		"site": site_name,
		"status": "timeout",
		"site_update_job": job_name,
		"elapsed_seconds": elapsed,
		**{k: v for k, v in last_poll.items() if k not in ("status", "site")},
	}
