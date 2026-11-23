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
from press.mcp_server.deploy_ops.candidates import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	_BENCH_PROVISION_JOB_TYPES,
	_derive_provision_stage,
	bench_provision_progress,
	deploy_candidate_schedule_build,
	deploy_candidate_status,
	release_group_create_deploy_candidate,
)
from press.mcp_server.deploy_ops.waits import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	HTTP_WAIT_CAP_SECONDS,
	bench_deploy_and_wait,
	site_update_and_wait,
	site_update_with_hint,
	wait_for_bench_flip,
)
from press.mcp_server.deploy_ops.site_tools import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	list_sites_on_release_group,
	mint_dashboard_login_url,
	site_schedule_update,
	site_status,
)


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


def _installation_for_owner(owner: str, team: str | None = None) -> str | None:
	"""Find a GitHub App installation already proven to work for this owner.

	Same GitHub org or user means the same installation, so an existing App
	Source is the most reliable source. `press.api.github.options` rebuilds its
	installation list from App Sources the same way.
	"""
	rows = frappe.get_all(
		"App Source",
		filters={"repository_owner": owner, "github_installation_id": ["is", "set"]},
		pluck="github_installation_id",
		limit=1,
	)
	if rows:
		return rows[0]

	if team:
		rows = frappe.get_all(
			"App Source",
			filters={"team": team, "github_installation_id": ["is", "set"]},
			pluck="github_installation_id",
			limit=1,
		)
		if rows:
			return rows[0]

	return None


def _repo_is_public(owner: str, repo: str) -> bool:
	"""Anonymous probe. A public repo needs no clone credentials at all."""
	try:
		import requests

		resp = requests.get(
			f"https://api.github.com/repos/{owner}/{repo}",
			headers={"Accept": "application/vnd.github+json"},
			timeout=10,
		)
		return resp.status_code == 200
	except Exception:
		return False


@frappe.whitelist()
def register_existing_app(
	repository_url: str,
	branch: str,
	app_name: str,
	app_title: str | None = None,
	versions: list[str] | None = None,
	team: str | None = None,
	github_installation_id: str | None = None,
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

	# Resolve the GitHub App installation BEFORE inserting.
	#
	# App Source.get_repo_url() returns a bare, credential-less URL when
	# github_installation_id is empty. For a PRIVATE repo the build then dies at
	# `git clone` with an empty error and 0.0s duration, minutes later and far
	# from the cause. Registration itself still reports success, because
	# create_release authenticates through the team token instead. Fail here
	# rather than there.
	is_public = _repo_is_public(owner, repo)
	installation_id = github_installation_id or _installation_for_owner(owner, team_name)

	if not installation_id and not is_public:
		frappe.throw(
			f"No GitHub App installation could be resolved for {owner!r}, and "
			f"{owner}/{repo} is not public. The App Source would be created but "
			"could never be cloned by a build. Pass github_installation_id "
			"explicitly, or register this app through the Press dashboard "
			"('Add app from GitHub'), which sets it for you.",
			frappe.ValidationError,
		)

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
			"public": 1 if is_public else 0,
			"github_installation_id": installation_id,
			"versions": [{"version": v} for v in versions],
		}
	).insert(ignore_permissions=True)

	# Fetch first release so the App Source isn't empty. Report a failure rather
	# than swallowing it: a silent pass here is what makes a broken registration
	# look healthy.
	first_release = None
	release_error = None
	try:
		first_release = doc.create_release(force=True)
	except Exception as e:
		release_error = str(e)
		frappe.log_error(
			title=f"register_existing_app: first release failed for {app_name}",
			message=frappe.get_traceback(),
		)

	return {
		"app_source": doc.name,
		"app": app_name,
		"repository_url": doc.repository_url,
		"branch": branch,
		"versions": versions,
		"public": doc.public,
		"github_installation_id": installation_id,
		"first_release": first_release,
		"first_release_error": release_error,
	}
