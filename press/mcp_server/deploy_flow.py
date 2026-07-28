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
		                     exists in the last 60 min — site_update was
		                     never called. STOP polling, call
		                     site_update_and_wait instead.
		flip_failed          most recent Update Site Migrate FAILED (and was
		                     rolled back by Recover Failed Site Migrate, if
		                     that ran). STOP polling, call agent_job_traceback
		                     on the failed_migrate_job to see the error.

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
				"job_type": (
					"in",
					[
						"Update Site Migrate",
						"Update Site Migrate Steps",
						"Recover Failed Site Migrate",
					],
				),
				"creation": (">", add_to_date(None, minutes=-60)),
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
					f"last 60 min. On standalone Press, sites don't auto-flip — "
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


_HOST_MEMORY_PRESSURE_CACHE_TTL = 60  # seconds


@frappe.whitelist()
def host_memory_pressure(server: str, force_refresh: bool = False) -> dict[str, Any]:
	"""Snapshot of memory pressure on an app server. Read-only.

	SSH-based: runs `cat /proc/meminfo` on the target server via Press's
	existing Ansible-adhoc pattern. No Prometheus dependency.

	Results are cached per-server for 60 seconds (the SSH+Ansible round-trip
	takes 3-10s — repeated calls within 60s return cached data in <100ms).
	Pass force_refresh=True to bypass the cache (e.g. right after restarting
	a worker to confirm memory dropped).

	Use this BEFORE memory-heavy ops (big reports, simultaneous backups) and
	as the FIRST check when multiple sites on a server start returning 500s.

	Why this exists: 2026-05-23 outage. MariaDB on press-f1 was OOM-killed
	(swap 100% full + RAM exhausted). All 32 sites 500ed for ~25 min until
	manual SSH diagnosis. An agent calling this tool would have seen
	verdict='critical' minutes before the OOM.

	Args:
		server: App server docname (e.g. 'press-f1.sandbox.mvpstorm.com').

	Returns:
		{
			"server": <server>,
			"verdict": "ok" | "elevated" | "critical" | "unknown",
			"reason": <human-readable>,
			"memory_total_mb": <int>,
			"memory_available_mb": <int>,
			"swap_used_pct": <int>,
			"recent_oom_kills": [...],
			"hint": <next action if verdict != ok>,
		}

	Verdict rules:
		ok        — available_mb > 1500 AND swap_used_pct < 80
		elevated  — 500 < available_mb <= 1500 OR swap_used_pct >= 80
		critical  — available_mb <= 500 OR swap_used_pct >= 95
		unknown   — SSH failed or /proc/meminfo missing
	"""
	if not frappe.db.exists("Server", server):
		frappe.throw(f"Server {server!r} not found", frappe.DoesNotExistError)

	# Cache hit? Return immediately to avoid 3-10s SSH round-trip on every poll.
	cache_key = f"mcp:host_memory_pressure:{server}"
	if not force_refresh:
		cached = frappe.cache().get_value(cache_key)
		if cached:
			cached["_cached"] = True
			return cached

	# Use Press's existing Ansible ad-hoc pattern to SSH the target server.
	# Inventory format: single host with trailing comma.
	meminfo_text = None
	try:
		from press.press.doctype.ansible_console.ansible_console import AnsibleAdHoc

		adhoc = AnsibleAdHoc(sources=f"{server},")
		# raw_params=True so the shell module gets the literal command.
		results = adhoc.run("cat /proc/meminfo", raw_params=True)
		# results is a list of host-result dicts; pick the first
		for host_result in results or []:
			out = host_result.get("output") or host_result.get("stdout") or ""
			if out and "MemTotal" in out:
				meminfo_text = out
				break
	except Exception as e:
		return {
			"server": server,
			"verdict": "unknown",
			"reason": f"SSH/Ansible query failed: {e!s}",
			"memory_total_mb": None,
			"memory_available_mb": None,
			"swap_used_pct": None,
			"recent_oom_kills": [],
			"hint": "Check that press-ctrl can SSH to this server (ansible-playbook -m ping).",
		}

	if not meminfo_text:
		return {
			"server": server,
			"verdict": "unknown",
			"reason": "Ansible ran but /proc/meminfo output was empty",
			"memory_total_mb": None,
			"memory_available_mb": None,
			"swap_used_pct": None,
			"recent_oom_kills": [],
			"hint": "Manually verify SSH to the server works.",
		}

	# Parse /proc/meminfo. All values are in kB.
	fields = {}
	for line in meminfo_text.splitlines():
		if ":" in line:
			k, v = line.split(":", 1)
			try:
				fields[k.strip()] = int(v.strip().split()[0])
			except (ValueError, IndexError):
				continue

	mem_total_kb = fields.get("MemTotal", 0)
	mem_available_kb = fields.get("MemAvailable", 0)
	swap_total_kb = fields.get("SwapTotal", 0)
	swap_free_kb = fields.get("SwapFree", 0)
	swap_used_kb = swap_total_kb - swap_free_kb
	swap_used_pct = int((swap_used_kb / swap_total_kb) * 100) if swap_total_kb else 0
	memory_total_mb = mem_total_kb // 1024
	memory_available_mb = mem_available_kb // 1024

	# Verdict — combines available memory + swap pressure
	if memory_available_mb <= 500 or swap_used_pct >= 95:
		verdict = "critical"
		reason = (
			f"Only {memory_available_mb} MB available; swap {swap_used_pct}% used. "
			f"OOM-killer is one bad query away."
		)
		hint = (
			"STOP scheduling memory-heavy ops. Restart 1-2 idle bench gunicorns "
			"to reclaim ~200MB each. Consider scheduling site backups for after "
			"off-hours. If this persists, scale RAM or move sites to another host."
		)
	elif memory_available_mb <= 1500 or swap_used_pct >= 80:
		verdict = "elevated"
		reason = (
			f"{memory_available_mb} MB available, swap {swap_used_pct}% used. "
			"Under the 1.5 GB / 80% safety floor."
		)
		hint = (
			"Avoid concurrent backups / big reports / bulk inserts. "
			"Investigate zombie processes (esbuild watchers from dev mode "
			"are a known cause)."
		)
	else:
		verdict = "ok"
		reason = f"{memory_available_mb} MB available, swap {swap_used_pct}% used — healthy."
		hint = ""

	# Scan recent Agent Jobs for explicit OOM evidence (job_type doesn't say
	# OOM but Failure traceback often mentions 'Killed' or signal 9).
	cutoff = add_to_date(now_datetime(), minutes=-30)
	recent_oom = []
	try:
		failures = frappe.db.sql(
			"""SELECT name, job_type, status, traceback, creation
			   FROM `tabAgent Job`
			   WHERE server = %s AND status = 'Failure' AND creation > %s
			   ORDER BY creation DESC LIMIT 20""",
			(server, cutoff),
			as_dict=True,
		)
		now = now_datetime()
		for f in failures:
			tb = (f.traceback or "")[-2000:]
			if "Killed" in tb or "signal 9" in tb or "OOM" in tb.upper() or "MemoryError" in tb:
				recent_oom.append({
					"job_name": f.name,
					"job_type": f.job_type,
					"age_seconds": int((now - f.creation).total_seconds()),
				})
	except Exception:
		pass

	result = {
		"server": server,
		"verdict": verdict,
		"reason": reason,
		"memory_total_mb": memory_total_mb,
		"memory_available_mb": memory_available_mb,
		"swap_used_pct": swap_used_pct,
		"recent_oom_kills": recent_oom,
		"hint": hint,
		"_cached": False,
	}
	frappe.cache().set_value(cache_key, result, expires_in_sec=_HOST_MEMORY_PRESSURE_CACHE_TTL)
	return result


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

	# On standalone Press, press.api.bench.deploy returns a Deploy Candidate BUILD name,
	# not a Deploy Candidate. wait_for_bench_flip below compares against Deploy Candidate
	# names, so without this translation the poll can never match and the tool always
	# reports 'timeout' with the misleading hint "the Deploy Candidate itself does not
	# exist" — while the build is in fact running fine.
	build = None
	if frappe.db.exists("Deploy Candidate Build", candidate):
		build = candidate
		candidate = (
			frappe.db.get_value("Deploy Candidate Build", build, "deploy_candidate")
			or candidate
		)

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
				"build": build,
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

	# The Deploy Candidate Difference that SiteUpdate needs is written a moment AFTER the
	# build reports Success, so a call issued straight after bench_deploy_and_wait races it
	# and dies with "Could not find suitable Destination Bench". That is a timing artefact,
	# not a real missing bench, so retry briefly instead of making the caller re-issue the
	# whole tool call and re-guess the cadence.
	job_name = None
	last_error = None
	for _attempt in range(6):
		try:
			job_name = site.schedule_update(
				skip_failing_patches=skip_failing_patches,
				skip_backups=skip_backups,
			)
			break
		except frappe.ValidationError as exc:
			if "Destination Bench" not in str(exc):
				raise
			last_error = str(exc)
			frappe.db.rollback()
			site.reload()
			time.sleep(10)
	if job_name is None:
		frappe.throw(
			f"site_update could not be scheduled for {site_name!r} after 6 attempts over "
			f"~60s: {last_error}. If this persists the Deploy Candidate Difference for "
			f"{target_candidate!r} is genuinely missing — confirm the build succeeded with "
			"deploy_candidate_status.",
			frappe.ValidationError,
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


@frappe.whitelist()
def agent_job_progress(
	job_name: str,
	step_output_chars: int = 1500,
	job_output_chars: int = 4000,
) -> dict[str, Any]:
	"""LIVE in-flight progress for an Agent Job — Cursor-style streaming.

	Returns the job's current status PLUS its per-step status and output tails,
	so an agent can poll this every few seconds during a deploy/migrate and
	see exactly which step is running and what it's printing. Mirrors what the
	dashboard's /dashboard/sites/<site>/jobs/<job_name> page renders.

	Unlike agent_job_traceback (which is for post-mortem on Failure rows),
	this is for IN-FLIGHT jobs you're watching. Call it on a loop.

	Args:
		job_name: Agent Job docname, e.g. 'sgc0i98rvm'.
		step_output_chars: chars of each step's output tail (default 1500,
			max 5000 — keeps response under MCP cap when 10+ steps).
		job_output_chars: chars of the parent job's output/traceback tail
			(default 4000, max 20000).

	Returns:
		{
			"name": <job_name>,
			"status": "Pending" | "Running" | "Success" | "Failure" | "Undelivered",
			"job_type": <e.g. "Update Site Migrate">,
			"site": <site or null>,
			"server": <server or null>,
			"bench": <bench or null>,
			"creation": <iso>,
			"modified": <iso>,
			"age_seconds": <int>,
			"current_step": <step_name of first Running/Failure step, or null>,
			"steps": [
				{
					"step_name": ..., "status": ...,
					"start": <iso or null>, "end": <iso or null>,
					"duration": <iso 'HH:MM:SS' or null>,
					"output_tail": <last N chars or empty>,
					"traceback_tail": <last N chars or empty>,
					"output_truncated": <bool>, "traceback_truncated": <bool>,
				}, ...
			],
			"steps_summary": {"Pending": N, "Running": M, "Success": X, "Failure": Y},
			"output_tail": <parent job output>,
			"traceback_tail": <parent job traceback>,
			"output_truncated": <bool>, "traceback_truncated": <bool>,
			"dashboard_url": <link to the dashboard job page>,
		}
	"""
	step_chars = max(200, min(5000, int(step_output_chars)))
	job_chars = max(500, min(20000, int(job_output_chars)))

	if not frappe.db.exists("Agent Job", job_name):
		frappe.throw(
			f"Agent Job {job_name!r} does not exist",
			frappe.DoesNotExistError,
		)
	doc = frappe.get_doc("Agent Job", job_name)
	now = now_datetime()

	step_rows = frappe.get_all(
		"Agent Job Step",
		filters={"agent_job": job_name},
		fields=["name", "step_name", "status", "start", "end", "duration", "output", "traceback"],
		order_by="creation asc, name asc",
		limit=100,
	)

	steps: list[dict] = []
	summary: dict[str, int] = {}
	current_step: str | None = None
	for s in step_rows:
		summary[s.status] = summary.get(s.status, 0) + 1
		if current_step is None and s.status in ("Running", "Failure"):
			current_step = s.step_name
		output = s.output or ""
		tb = s.traceback or ""
		steps.append({
			"step_name": s.step_name,
			"status": s.status,
			"start": s.start.isoformat() if s.start else None,
			"end": s.end.isoformat() if s.end else None,
			"duration": str(s.duration) if s.duration else None,
			"output_tail": output[-step_chars:],
			"traceback_tail": tb[-step_chars:],
			"output_truncated": len(output) > step_chars,
			"traceback_truncated": len(tb) > step_chars,
		})

	job_output = doc.output or ""
	job_tb = doc.traceback or ""

	dashboard_url = None
	if doc.site:
		dashboard_url = (
			f"{frappe.utils.get_url()}/dashboard/sites/{doc.site}/jobs/{job_name}"
		)

	return {
		"name": doc.name,
		"status": doc.status,
		"job_type": doc.job_type,
		"site": doc.site,
		"server": doc.server,
		"bench": doc.bench,
		"creation": doc.creation.isoformat() if doc.creation else None,
		"modified": doc.modified.isoformat() if doc.modified else None,
		"age_seconds": int((now - doc.creation).total_seconds()) if doc.creation else None,
		"current_step": current_step,
		"steps": steps,
		"steps_summary": summary,
		"output_tail": job_output[-job_chars:],
		"traceback_tail": job_tb[-job_chars:],
		"output_truncated": len(job_output) > job_chars,
		"traceback_truncated": len(job_tb) > job_chars,
		"dashboard_url": dashboard_url,
	}


@frappe.whitelist()
def mint_dashboard_login_url(redirect_to: str = "/dashboard") -> dict[str, Any]:
	"""Mint a one-shot ?sid= URL that logs the browser in as the MCP token's
	user on the Press dashboard. Designed for Playwright / E2E tests so they
	don't have to handle password typing or password rotation.

	The token's user (Administrator for the Master token) is logged in via
	Frappe's LoginManager, a real Session row is created, and a URL is
	returned that Frappe's `?sid=<sid>` handler will pick up as the session
	cookie. No password is ever transmitted by the caller.

	Args:
		redirect_to: dashboard path to land on after auth, default
			'/dashboard'. Common choices: '/dashboard/devtools/mcp',
			'/dashboard/sites/<site>/overview'.

	Returns:
		{
			"url": "https://<press-host>/<redirect>?sid=<sid>",
			"sid": <sid>,
			"user": <user that owns the session>,
			"expires_in_seconds": <int — inherits the Press session TTL>,
		}

	Audit: the login is recorded in Frappe's standard Activity Log + the MCP
	Call Log (via the dispatcher's _log_call). Anyone with bench console can
	revoke the SID via `frappe.local.session.sid = None` + db.commit().
	"""
	from frappe.auth import LoginManager

	target_user = frappe.session.user
	if not target_user or target_user == "Guest":
		frappe.throw(
			"mint_dashboard_login_url: token does not resolve to a Press user",
			frappe.PermissionError,
		)

	# Mint a real session via LoginManager (creates the Sessions row +
	# rotates frappe.session.sid). Frappe's CookieManager handles the
	# rest when the browser hits ?sid=<sid>.
	lm = LoginManager()
	lm.login_as(target_user)
	sid = frappe.session.sid
	if not sid or sid == "Guest":
		frappe.throw(
			"mint_dashboard_login_url: LoginManager did not produce a usable SID",
			frappe.ValidationError,
		)
	frappe.db.commit()

	# Press session lifetime — Frappe defaults to 6 hours unless overridden
	# in System Settings.session_expiry. Best-effort: don't fail if missing.
	try:
		expiry = frappe.db.get_single_value("System Settings", "session_expiry") or "06:00:00"
		h, m, *_ = (str(expiry).split(":") + ["0"])[:2]
		expires_in_seconds = int(h) * 3600 + int(m) * 60
	except Exception:  # noqa: BLE001
		expires_in_seconds = 21600

	# Normalize redirect path
	if not redirect_to.startswith("/"):
		redirect_to = "/" + redirect_to

	base = frappe.utils.get_url().rstrip("/")
	url = f"{base}{redirect_to}?sid={sid}"
	return {
		"url": url,
		"sid": sid,
		"user": target_user,
		"expires_in_seconds": expires_in_seconds,
	}


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


@frappe.whitelist()
def site_update_with_hint(name: str, skip_failing_patches: int | bool = False) -> dict[str, Any]:
	"""Friendlier wrapper around press.api.site.update.

	Press's underlying site_update throws 'Could not find suitable Destination
	Bench' for TWO different conditions — confusing because the message
	suggests the destination bench is missing when usually it's that no NEWER
	candidate has been built yet. This wrapper pre-checks and returns a
	structured hint so the calling agent knows exactly what to do next.
	"""
	if not frappe.db.exists("Site", name):
		frappe.throw(f"Site {name!r} not found", frappe.DoesNotExistError)

	site = frappe.db.get_value(
		"Site", name, ["name", "bench", "group", "server", "status"], as_dict=True
	)

	# Pre-flight #1: any Deploy Candidate Difference from source candidate?
	source_candidate = frappe.db.get_value("Bench", site.bench, "candidate")
	diff_count = frappe.db.count(
		"Deploy Candidate Difference",
		{"group": site.group, "source": source_candidate},
	)
	if not diff_count:
		# No newer candidate has been built. Suggest the next step.
		newer_bench = frappe.db.get_value(
			"Bench",
			{"group": site.group, "server": site.server, "status": "Active",
			 "candidate": ["!=", source_candidate]},
			"name",
		)
		hint = (
			"No newer Deploy Candidate exists for this site's Release Group. "
			"Build one first: call release_group_create_deploy_candidate("
			f"name={site.group!r}) then deploy_candidate_schedule_build(...)."
		)
		if newer_bench:
			hint = (
				f"A newer Active bench {newer_bench!r} exists on this server, "
				"but no Deploy Candidate Difference has been computed yet. "
				"This usually self-resolves within ~60s; retry after a brief wait."
			)
		return {
			"ok": False,
			"site": name,
			"source_bench": site.bench,
			"source_candidate": source_candidate,
			"reason": "no_destination_candidate",
			"hint": hint,
		}

	# Pre-flight #2: any Active bench with a different candidate on same server?
	dest = frappe.db.get_value(
		"Bench",
		{"group": site.group, "server": site.server, "status": "Active",
		 "candidate": ["!=", source_candidate]},
		"name",
	)
	if not dest:
		return {
			"ok": False,
			"site": name,
			"source_bench": site.bench,
			"reason": "no_active_destination_bench",
			"hint": (
				"Deploy Candidate Differences exist but no Active bench on the "
				"same server has a different candidate. Either the build is "
				"still running (poll bench_provision_progress) or the build "
				"failed (check deploy_candidate_status)."
			),
		}

	# Pre-flight passed — call Press's real site_update.
	from press.api.site import update as _press_site_update

	job_name = _press_site_update(name=name, skip_failing_patches=bool(skip_failing_patches))
	return {
		"ok": True,
		"site": name,
		"site_update": job_name,
		"destination_bench": dest,
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


# ---------------------------------------------------------------------------
# App lifecycle tools — fetch latest, list pending, register existing
# ---------------------------------------------------------------------------


def _resolve_app_source(
	app_source: str | None = None,
	app: str | None = None,
	release_group: str | None = None,
) -> str:
	"""Resolve an App Source docname from either an explicit name or app+RG."""
	if app_source:
		if not frappe.db.exists("App Source", app_source):
			frappe.throw(f"App Source {app_source!r} not found", frappe.DoesNotExistError)
		return app_source
	if not (app and release_group):
		frappe.throw(
			"Pass either app_source, or both app and release_group",
			frappe.ValidationError,
		)
	src = frappe.db.get_value(
		"Release Group App", {"parent": release_group, "app": app}, "source"
	)
	if not src:
		frappe.throw(
			f"App {app!r} is not on Release Group {release_group!r}",
			frappe.ValidationError,
		)
	return src


@frappe.whitelist()
def app_source_fetch_latest(
	app_source: str | None = None,
	app: str | None = None,
	release_group: str | None = None,
	force: bool = False,
) -> dict[str, Any]:
	"""Poll an App Source's upstream Git remote and create a Draft App Release
	for any new commit on its branch.

	Equivalent to the dashboard's "Fetch Latest" button on an App Source.
	Returns the new release docname, or marks `no_new_release` when the latest
	upstream commit already has a release row.

	Resolve modes (pass ONE):
	- app_source: explicit App Source docname (e.g. SRC-frappe_theme_switcher-001)
	- app + release_group: walk Release Group → child app row → source

	Args:
	- force: ignore the last_github_poll_failed flag (use after fixing creds)
	"""
	source_name = _resolve_app_source(app_source, app, release_group)
	doc = frappe.get_doc("App Source", source_name)
	result = doc.create_release(force=bool(force))
	if not result:
		return {
			"app_source": source_name,
			"app": doc.app,
			"branch": doc.branch,
			"new_release": None,
			"no_new_release": True,
			"reason": "Upstream has no new commits, or last poll failed (pass force=true to retry).",
		}
	rel = frappe.db.get_value(
		"App Release", result, ["name", "hash", "status"], as_dict=True
	)
	return {
		"app_source": source_name,
		"app": doc.app,
		"branch": doc.branch,
		"new_release": rel,
	}


@frappe.whitelist()
def list_pending_releases(
	app: str | None = None,
	release_group: str | None = None,
	app_source: str | None = None,
	limit: int = 20,
) -> dict[str, Any]:
	"""List Draft App Releases waiting for approval.

	Scope filters (any combination):
	- app_source: only this source's releases
	- app + release_group: only releases for `app` on the RG's bound source
	- app alone: every Draft release of that app across all sources
	- (no scope): every Draft release the caller can see (system users only)
	"""
	filters: dict[str, Any] = {"status": "Draft"}
	if app_source:
		filters["source"] = app_source
	elif app and release_group:
		filters["source"] = _resolve_app_source(None, app, release_group)
		filters["app"] = app
	elif app:
		filters["app"] = app

	rows = frappe.get_all(
		"App Release",
		filters=filters,
		fields=["name", "app", "source", "hash", "status", "creation"],
		order_by="creation desc",
		limit_page_length=int(limit),
	)
	return {"filters": filters, "count": len(rows), "releases": rows}


@frappe.whitelist()
def register_existing_app(
	repository_url: str,
	branch: str,
	app_name: str,
	app_title: str | None = None,
	versions: list[str] | None = None,
	team: str | None = None,
) -> dict[str, Any]:
	"""Register an EXISTING GitHub repository as a new App Source.

	Different from `app_create_locally`, which scaffolds a brand-new app on a
	bench. This adds a known-good repo (already on GitHub) as an App Source so
	it can be added to a Release Group and deployed.

	Args:
	- repository_url: full GitHub URL (https://github.com/owner/repo) or
	  owner/repo shorthand
	- branch: git branch to track (e.g. 'main', 'version-15')
	- app_name: lowercase_with_underscores app identifier (must match the app's
	  hooks.py `app_name`)
	- app_title: human-readable title (defaults to app_name titlecased)
	- team: team that owns the App Source (defaults to current team)
	"""
	from press.utils import get_current_team

	# Normalize repository URL → owner, repo
	url = repository_url.strip().rstrip("/")
	if url.startswith("https://github.com/"):
		owner_repo = url[len("https://github.com/") :]
	elif url.startswith("git@github.com:"):
		owner_repo = url[len("git@github.com:") :]
	else:
		owner_repo = url  # assume owner/repo shorthand
	if owner_repo.endswith(".git"):
		owner_repo = owner_repo[:-4]
	parts = owner_repo.split("/")
	if len(parts) != 2 or not all(parts):
		frappe.throw(
			f"Invalid repository_url {repository_url!r}: expected "
			"https://github.com/owner/repo or owner/repo",
			frappe.ValidationError,
		)
	owner, repo = parts

	team_name = team or get_current_team()

	# App Source.versions is a REQUIRED child table. Without it, .insert()
	# fails with 'Data missing in table: Versions'. Resolve from the arg, or
	# derive from a version-NN branch, else default to the latest Frappe
	# Version on record. Validate every value against Frappe Version.
	if not versions:
		derived = None
		if branch.lower().startswith("version-"):
			num = branch.split("-", 1)[1].strip()
			candidate = f"Version {num}"
			if frappe.db.exists("Frappe Version", candidate):
				derived = candidate
		if not derived:
			rows = frappe.get_all(
				"Frappe Version",
				filters={"name": ["like", "Version %"]},
				pluck="name",
			)
			# Highest numeric Version N on record (e.g. Version 16 > Version 15).
			derived = max(
				rows,
				key=lambda v: int(v.rsplit(" ", 1)[1]) if v.rsplit(" ", 1)[1].isdigit() else -1,
			) if rows else "Version 15"
		versions = [derived]
	for v in versions:
		if not frappe.db.exists("Frappe Version", v):
			frappe.throw(
				f"Unknown Frappe Version {v!r}. Valid values come from the "
				"Frappe Version list (e.g. 'Version 15').",
				frappe.ValidationError,
			)

	# Duplicate check
	existing = frappe.db.get_value(
		"App Source",
		{"app": app_name, "repository_owner": owner, "repository": repo, "branch": branch},
		"name",
	)
	if existing:
		return {
			"app_source": existing,
			"app": app_name,
			"already_exists": True,
		}

	# Make sure the App parent row exists (App Source has a Link to App)
	if not frappe.db.exists("App", app_name):
		frappe.get_doc(
			{
				"doctype": "App",
				"name": app_name,
				"title": app_title or app_name.replace("_", " ").title(),
			}
		).insert(ignore_permissions=True)

	doc = frappe.get_doc(
		{
			"doctype": "App Source",
			"app": app_name,
			"app_title": app_title or app_name.replace("_", " ").title(),
			"repository_url": f"https://github.com/{owner}/{repo}",
			"repository_owner": owner,
			"repository": repo,
			"branch": branch,
			"team": team_name,
			"public": 0,
			"versions": [{"version": v} for v in versions],
		}
	).insert(ignore_permissions=True)

	# Fetch first release so the App Source isn't empty
	first_release = None
	try:
		first_release = doc.create_release(force=True)
	except Exception:
		pass

	return {
		"app_source": doc.name,
		"app": app_name,
		"repository_url": doc.repository_url,
		"branch": branch,
		"versions": versions,
		"first_release": first_release,
	}
