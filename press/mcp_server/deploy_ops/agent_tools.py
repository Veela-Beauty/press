# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Agent Job tools over MCP: list jobs, follow one, read its traceback, and judge an app server's agent
healthy, slow or stuck (moved from deploy_flow.py in 0.7.54)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import add_to_date, now_datetime


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
