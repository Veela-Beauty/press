"""Stuck-Pending Agent Job auto-recovery (Sanad fork — not in upstream).

Background — recurring pattern observed 2026-05-24 onward:
When Press has a Redis/OOM cascade, the agent's HTTP enqueue can abort
mid-flight (ExecAbortError on the redis pipeline). The Agent Job row
gets created with status='Pending' but the request never actually
reaches the agent worker — `start`, `end`, and `job_id` stay NULL
forever. Press's normal poll_pending_jobs cron checks the AGENT for
job status; it has no concept of "job was never delivered to begin with".

Symptoms:
  - Site shows 'Pending' status in dashboard
  - bench.archive() fails with ArchiveBenchError: Cannot archive bench
    because of ongoing jobs
  - Agent Job sits Pending for hours/days with empty traceback

Manual fix has been needed THREE times in the same week. This module
runs hourly and:

  1. Finds Agent Jobs Pending > STUCK_THRESHOLD_HOURS (default 2h)
  2. For each, checks agent_health(server). If 'ok' or 'elevated',
     calls retry_in_place() — which re-enqueues the same HTTP request.
  3. Only marks Failure if (a) agent verdict was 'stuck'/'no_activity'
     so retry would fail anyway, OR (b) the retry itself raises.

This is RECOVERY first, FAILURE last — we try to finish the user's
work before giving up.

Wired in press/hooks.py scheduler_events.cron at "0,30 * * * *"
(every 30 minutes) — 48 polls/day, each ~5ms = 240ms/day DB time.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_to_date, now_datetime

STUCK_THRESHOLD_HOURS = 2
# Job types that are LEGITIMATELY slow — don't touch even when "stuck".
# Backup of dmg-erp (6 GB) can take 20+ min; site clones / migrations can
# take 10+ min on a busy box. We err on the safe side.
SLOW_BY_DESIGN_JOB_TYPES = {
	"Backup Site",
	"Restore Site",
	"Clone Site",
	"Migrate Site",
	"Physical Backup Site",
	"Physical Restore Site",
}


def recover_stuck_jobs() -> dict[str, int]:
	"""Find stuck Pending Agent Jobs and try to recover them.

	Returns a small dict for logging:
		{scanned, slow_by_design_skipped, retried, marked_failure, agent_dead}

	Best-effort: a single bad job never aborts the whole loop. Each job
	is wrapped in try/except and logged via frappe.log_error on failure.
	"""
	from press.mcp_server.deploy_flow import host_memory_pressure  # for cross-reference

	cutoff = add_to_date(None, hours=-STUCK_THRESHOLD_HOURS)
	stuck = frappe.db.sql(
		"""
		SELECT name, job_type, server, server_type, site, bench, creation
		FROM `tabAgent Job`
		WHERE status = 'Pending' AND creation < %s
		ORDER BY creation ASC
		""",
		(cutoff,),
		as_dict=True,
	)

	counters = {
		"scanned": len(stuck),
		"slow_by_design_skipped": 0,
		"retried": 0,
		"marked_failure": 0,
		"agent_dead": 0,
	}
	if not stuck:
		return counters

	# Group by server so we ask agent_health ONCE per server, not N times.
	# (Big batches from a single OOM cascade affect one server.)
	servers_seen: dict[str, str] = {}  # server -> verdict
	for job in stuck:
		try:
			_handle_one(job, servers_seen, counters)
		except Exception:
			frappe.log_error(
				title="stuck_job_recovery: per-job failure",
				message=f"job={job.name} server={job.server}\n{frappe.get_traceback()}",
			)
			frappe.db.rollback()

	frappe.db.commit()
	return counters


def _handle_one(job, servers_seen, counters):
	# Skip job types that legitimately take >2h (backups of huge DBs etc).
	if job.job_type in SLOW_BY_DESIGN_JOB_TYPES:
		counters["slow_by_design_skipped"] += 1
		return

	if not job.server:
		# Orphan job with no server (rare — usually a Run Remote Builder
		# job that was killed before bench was set). Mark Failure: no
		# target to retry against.
		_mark_failure(job.name, "no server set on Agent Job — cannot retry")
		counters["marked_failure"] += 1
		return

	verdict = _get_or_check_agent_health(job.server, servers_seen)

	if verdict in ("stuck", "no_activity"):
		# Agent is dead — retrying would just sit Pending again.
		# Mark Failure now so the Site can flip back to a usable status
		# (operator can re-trigger after fixing the agent).
		_mark_failure(
			job.name,
			f"Marked Failure by stuck_job_recovery cron: stuck Pending "
			f"for >{STUCK_THRESHOLD_HOURS}h AND target server "
			f"{job.server!r} agent verdict='{verdict}'. No point retrying "
			f"until the agent is restored. Re-trigger this op once the "
			f"server is healthy.",
		)
		counters["marked_failure"] += 1
		counters["agent_dead"] += 1
		return

	# Agent looks alive ('ok' or 'elevated' or 'unknown'). Try to actually
	# finish the user's work via retry_in_place — which re-enqueues the
	# HTTP request from the same Agent Job record (no orphan).
	try:
		doc = frappe.get_doc("Agent Job", job.name)
		doc.retry_in_place()
		counters["retried"] += 1
	except Exception as e:
		# retry_in_place failed (network, agent rejected, etc).
		# THAT means the agent really can't accept it — mark Failure.
		_mark_failure(
			job.name,
			f"Marked Failure by stuck_job_recovery cron: stuck Pending "
			f"for >{STUCK_THRESHOLD_HOURS}h, agent_health for {job.server!r} "
			f"was '{verdict}' so we tried retry_in_place — that raised: "
			f"{type(e).__name__}: {e}. Operator can re-trigger after "
			f"diagnosing the agent.",
		)
		counters["marked_failure"] += 1


def _get_or_check_agent_health(server: str, cache: dict[str, str]) -> str:
	"""agent_health is SSH-based (~3-10s). Cache per cron run."""
	if server in cache:
		return cache[server]
	try:
		from press.mcp_server.deploy_flow import agent_health

		result = agent_health(server=server, lookback_minutes=10)
		verdict = result.get("verdict", "unknown")
	except Exception:
		verdict = "unknown"
	cache[server] = verdict
	return verdict


def _mark_failure(job_name: str, reason: str) -> None:
	frappe.db.set_value(
		"Agent Job",
		job_name,
		{
			"status": "Failure",
			"end": now_datetime(),
			"traceback": reason,
		},
		update_modified=True,
	)
	_run_failure_callback(job_name)


def _run_failure_callback(job_name: str) -> None:
	"""Run the job's own callback so the record it was created for advances.

	Setting Agent Job.status with a bare db.set_value skips process_job_updates,
	so the linked Bench/Site keeps whatever transient status it had. Nothing
	else ever revisits it: a Bench left at "Pending" is invisible to
	archive_broken_benches and to every retry path, so it sits there forever.

	Observed 2026-09-08 on release group bench-0014: four benches frozen at
	"Pending" for 8 days, across both New Bench and Archive Bench jobs, every
	one of them carrying this cron's own failure message in its traceback.
	"""
	from press.press.doctype.agent_job.agent_job import process_job_updates
	from press.utils import log_error

	try:
		process_job_updates(job_name)
		frappe.db.commit()
	except Exception:
		# A broken callback must not stop the sweep from failing other jobs.
		frappe.db.rollback()
		log_error("Stuck Job Recovery Callback Failed", agent_job=job_name)
