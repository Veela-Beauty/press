"""Scheduler and error log Watch Tower alerts."""
import datetime
import frappe
from frappe.utils import get_datetime
from ._helpers import (
	TABLE, TH_BG, SITE_URL, NOISE_PATTERNS, ERROR_SPIKE_THRESHOLD,
	esc, ts_now, should_send_alert,
)

# A background/scheduled job running longer than this is treated as stuck/hung.
STUCK_JOB_MINUTES = 30
# How far back each "recent failures" sweep looks.
LOOKBACK_HOURS = 1


def check_error_log_spike(doc_dict, rule):
	"""Check if REAL error count exceeds threshold, filtering out noise."""
	# Build parameterized noise filter -  NOISE_PATTERNS is a hardcoded tuple,
	# but we use frappe.db.escape() defensively to prevent injection if patterns change.
	noise_clauses = " AND ".join(
		f"IFNULL(method,'') NOT LIKE {frappe.db.escape(f'%{p}%')}" for p in NOISE_PATTERNS
	)
	count = frappe.db.sql(f"""
		SELECT COUNT(*) FROM `tabError Log`
		WHERE creation > NOW() - INTERVAL 1 HOUR AND {noise_clauses}
	""")[0][0]

	if count <= ERROR_SPIKE_THRESHOLD:
		return False

	top_errors = frappe.db.sql(f"""
		SELECT method, COUNT(*) as cnt
		FROM `tabError Log`
		WHERE creation > NOW() - INTERVAL 1 HOUR AND {noise_clauses}
		GROUP BY method ORDER BY cnt DESC LIMIT 5
	""", as_dict=True)

	recent = frappe.db.sql(f"""
		SELECT name, method, error, creation
		FROM `tabError Log`
		WHERE creation > NOW() - INTERVAL 1 HOUR AND {noise_clauses}
		ORDER BY creation DESC LIMIT 5
	""", as_dict=True)

	_send_error_spike_email(count, top_errors, recent)
	return True


def check_scheduler_health(doc_dict, rule):
	"""Check if poll_pending_jobs is registered. Auto-fixes if missing."""
	count = frappe.db.count(
		"Scheduled Job Type",
		{"method": ["like", "%poll_pending_jobs%"]},
	)
	if count > 0:
		return False

	try:
		from frappe.core.doctype.scheduled_job_type.scheduled_job_type import sync_jobs
		sync_jobs()
		frappe.db.commit()
		auto_fixed = True
	except Exception:
		auto_fixed = False

	_send_scheduler_alert_email(auto_fixed)
	return True


def check_worker_queue_depth(doc_dict, rule):
	"""Check if RQ worker queues are backing up."""
	from ..email_branding import wrap_email, send_alert_email
	import subprocess

	ts = ts_now()
	issues = []

	# Check RQ queue lengths via redis-cli
	try:
		result = subprocess.run(
			["redis-cli", "-p", "11000", "llen", "default"],
			capture_output=True, text=True, timeout=5,
		)
		default_len = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0

		result = subprocess.run(
			["redis-cli", "-p", "11000", "llen", "long"],
			capture_output=True, text=True, timeout=5,
		)
		long_len = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0

		result = subprocess.run(
			["redis-cli", "-p", "11000", "llen", "short"],
			capture_output=True, text=True, timeout=5,
		)
		short_len = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0

		if default_len > 50:
			issues.append(f"Default queue: <b>{default_len}</b> pending jobs")
		if long_len > 20:
			issues.append(f"Long queue: <b>{long_len}</b> pending jobs")
		if short_len > 100:
			issues.append(f"Short queue: <b>{short_len}</b> pending jobs")
	except Exception:
		pass

	if not issues:
		return False

	body = "<ul>" + "".join(f"<li>{i}</li>" for i in issues) + "</ul>"
	body += "<p>Workers may be stuck or overloaded. Check <code>supervisorctl status</code>.</p>"

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\U0001f4e5 Worker Queue Backup \u2014 {ts}",
		message=wrap_email("\U0001f4e5 Worker Queue Depth Alert", body, f"press-ctrl &bull; {ts}"),
	)
	return True


def _send_error_spike_email(count, top_errors, recent):
	from ..email_branding import wrap_email, send_alert_email
	ts = ts_now()

	top_rows = ""
	for e in top_errors:
		top_rows += f"<tr><td>{esc(e.method or 'Unknown')}</td><td><b>{e.cnt}</b></td></tr>"

	recent_rows = ""
	for e in recent:
		created = get_datetime(e.creation).strftime("%H:%M:%S")
		snippet = esc(str(e.error or "")[:200])
		recent_rows += (
			f"<tr><td>{created}</td>"
			f"<td>{esc(e.method or '')}</td>"
			f"<td><small>{snippet}</small></td></tr>"
		)

	body = f"""
<h3>Top Error Methods</h3>
<table {TABLE}>
<tr {TH_BG}><th>Method</th><th>Count</th></tr>
{top_rows}
</table>

<h3>Most Recent Errors</h3>
<table {TABLE}>
<tr {TH_BG}><th>Time</th><th>Method</th><th>Error</th></tr>
{recent_rows}
</table>
<p><a href="{SITE_URL}/app/error-log">\u2192 View all errors</a></p>"""

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\u26a0\ufe0f Press: {count} errors in last hour",
		message=wrap_email(f"\u26a0\ufe0f Error Log Spike: {count} errors", body, f"press-ctrl &bull; {ts}"),
	)


def _send_scheduler_alert_email(auto_fixed):
	from ..email_branding import wrap_email, send_alert_email
	ts = ts_now()
	fix_status = (
		"\U0001f527 <b>Auto-fixed:</b> sync_jobs ran successfully."
		if auto_fixed else
		"\u274c <b>Auto-fix failed.</b> Manual intervention required."
	)

	body = f"""
<p>The <code>poll_pending_jobs</code> scheduler job is <b>not registered</b>.</p>
<p>All deploys will hang forever until this is fixed.</p>
<p>{fix_status}</p>
<h3>Manual Fix</h3>
<pre style="background:#f1f5f9;padding:12px;border-radius:4px;">
ssh press-ctrl
cd /home/frappe/frappe-bench
bench --site demo.mvpstorm.com execute \\
  frappe.core.doctype.scheduled_job_type.scheduled_job_type.sync_jobs
</pre>"""

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject="\U0001f6a8 CRITICAL: poll_pending_jobs missing!",
		message=wrap_email("\U0001f6a8 CRITICAL: Scheduler Missing!", body, f"press-ctrl &bull; {ts}"),
	)


# =====================================================================================
# Hidden-failure checks: scheduled jobs that fail, background (RQ) jobs that fail or hang.
# These surface silent failures that "scheduler is registered" checks miss. All read-only.
# =====================================================================================

# The engine evaluates a Python-Method rule once PER candidate document (batched). These
# checks are global (they scan everything themselves), so a brief memo collapses that burst
# into a single real computation per hourly run - the TTL is well under the hourly cadence.
_MEMO_TTL_SEC = 120


def _memoized(key, worker):
	"""Run worker() at most once per _MEMO_TTL_SEC; cache the bool result across the
	engine's per-document calls so one hourly run computes once. A worker that raises is
	logged once and cached as no-alert, so a transient DB/Redis error can't make the engine
	retry it for every candidate document in the batch (10k+ docs -> 10k+ error logs).
	expires=True forces a Redis read past the stale in-process cache for TTL keys."""
	cache = frappe.cache()
	ck = f"wt:jobcheck:{key}"
	hit = cache.get_value(ck, expires=True)
	if hit is not None:
		return hit == "1"
	try:
		result = bool(worker())
	except Exception:
		frappe.log_error(title=f"Watch Tower job-check failed: {key}", message=frappe.get_traceback())
		result = False
	cache.set_value(ck, "1" if result else "0", expires_in_sec=_MEMO_TTL_SEC)
	return result


def check_scheduled_job_failures(doc_dict, rule):
	"""Alert when scheduled (cron) jobs FAILED in the last hour - a silent cron failure
	that nothing else surfaces. Reads Scheduled Job Log; never writes. Memoized because the
	engine calls this once per candidate document."""
	return _memoized("scheduled_job_failures", _eval_scheduled_job_failures)


def _eval_scheduled_job_failures():
	rows = frappe.db.sql(
		"""
		SELECT scheduled_job_type, COUNT(*) AS cnt, MAX(creation) AS last_seen
		FROM `tabScheduled Job Log`
		WHERE status = 'Failed' AND creation > NOW() - INTERVAL %s HOUR
		GROUP BY scheduled_job_type ORDER BY cnt DESC LIMIT 20
		""",
		(LOOKBACK_HOURS,),
		as_dict=True,
	)
	if not rows:
		return False

	total = sum(r.cnt for r in rows)
	# fingerprint on type:count (NOT the hour) on purpose: should_send_alert caps at 3 sends
	# then its Redis key expires ~6h after the last send, so a persistent failure re-alerts
	# every ~6h instead of being silenced. Adding the hour here would defeat that throttle.
	fingerprint = "|".join(sorted(f"{r.scheduled_job_type}:{r.cnt}" for r in rows))
	if not should_send_alert("scheduled_job_failures", fingerprint):
		return True

	last_err = frappe.db.get_value(
		"Scheduled Job Log",
		{"status": "Failed", "scheduled_job_type": rows[0].scheduled_job_type},
		"details",
		order_by="creation desc",
	)
	_send_job_failure_email(rows, total, last_err)
	return True


def check_failed_background_jobs(doc_dict, rule):
	"""Alert on RQ background jobs that FAILED in the last hour (deploys, site updates,
	syncs, agent jobs). Scheduled Job Log does NOT capture these. Read-only; memoized."""
	return _memoized("failed_background_jobs", _eval_failed_background_jobs)


def _eval_failed_background_jobs():
	cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=LOOKBACK_HOURS)
	failed = []
	for q in _rq_queues():
		try:
			reg = q.failed_job_registry
			# newest 200: registries sort oldest-first, so recent failures are at the tail
			for jid in _recent_job_ids(reg, 200):
				try:
					job = q.fetch_job(jid)
					if job is None:
						continue
					ended = _as_naive_utc(getattr(job, "ended_at", None))
					if ended and ended >= cutoff:
						failed.append((q.name, _job_label(job), _exc_last_line(job)))
				except Exception:
					continue
		except Exception:
			continue

	if not failed:
		return False
	fingerprint = "|".join(sorted(f"{qn}:{fn}" for qn, fn, _ in failed))
	if not should_send_alert("failed_background_jobs", fingerprint):
		return True
	_send_bg_failure_email(failed)
	return True


def check_stuck_jobs(doc_dict, rule):
	"""Alert on RQ jobs RUNNING longer than STUCK_JOB_MINUTES - a hung job that never
	finishes (dead worker / infinite loop), the silent killer. Read-only; memoized."""
	return _memoized("stuck_jobs", _eval_stuck_jobs)


def _eval_stuck_jobs():
	now = datetime.datetime.utcnow()
	stuck = []
	for q in _rq_queues():
		try:
			reg = q.started_job_registry
			# oldest 200: oldest-running = most likely hung (registries sort oldest-first)
			for jid in reg.get_job_ids()[:200]:
				try:
					job = q.fetch_job(jid)
					if job is None:
						continue
					started = _as_naive_utc(getattr(job, "started_at", None))
					if not started:
						continue
					mins = int((now - started).total_seconds() // 60)
					if mins > STUCK_JOB_MINUTES:
						stuck.append((q.name, _job_label(job), mins, getattr(job, "id", "") or ""))
				except Exception:
					continue
		except Exception:
			continue

	if not stuck:
		return False
	# fingerprint on job id so distinct hung instances of the same function don't collide
	fingerprint = "|".join(sorted(f"{qn}:{jid or fn}" for qn, fn, _, jid in stuck))
	if not should_send_alert("stuck_jobs", fingerprint):
		return True
	_send_stuck_email(stuck)
	return True


# ----- shared RQ helpers (version-tolerant; return empty / None instead of raising) -----

def _recent_job_ids(registry, n=200):
	"""Most-recent N job ids from an RQ registry. Registries sort oldest-first, so the
	last N are the newest; falls back to the head slice on older RQ versions. Never raises."""
	try:
		ids = registry.get_job_ids(-n, -1)
		if ids:
			return ids
	except Exception:
		pass
	try:
		return registry.get_job_ids()[:n]
	except Exception:
		return []


def _rq_queues():
	"""All RQ queues for this bench, or [] if RQ/redis is unavailable. Never raises."""
	try:
		from frappe.utils.background_jobs import get_redis_conn
		from rq import Queue
		return Queue.all(connection=get_redis_conn())
	except Exception:
		return []


def _as_naive_utc(dt):
	"""RQ timestamps may be tz-aware or naive across versions; normalise to naive UTC
	so comparisons never raise a tz mismatch."""
	if dt is None:
		return None
	if getattr(dt, "tzinfo", None) is not None:
		dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
	return dt


def _job_label(job):
	return getattr(job, "func_name", None) or getattr(job, "id", "") or "unknown"


def _exc_last_line(job):
	exc = getattr(job, "exc_info", None) or ""
	lines = [ln for ln in str(exc).strip().splitlines() if ln.strip()]
	return lines[-1] if lines else ""


# ----- email bodies -----

def _send_job_failure_email(rows, total, last_err):
	from ..email_branding import wrap_email, send_alert_email
	ts = ts_now()
	job_rows = "".join(
		f"<tr><td>{esc(r.scheduled_job_type)}</td><td><b>{r.cnt}</b></td>"
		f"<td>{get_datetime(r.last_seen).strftime('%H:%M')}</td></tr>"
		for r in rows
	)
	snippet = esc(str(last_err or "")[-400:]) if last_err else "(no detail captured)"
	body = f"""
<p><b>{total}</b> scheduled job run(s) FAILED in the last hour.</p>
<table {TABLE}>
<tr {TH_BG}><th>Scheduled Job</th><th>Failures</th><th>Last</th></tr>
{job_rows}
</table>
<h3>Last error ({esc(rows[0].scheduled_job_type)})</h3>
<pre style="background:#f1f5f9;padding:12px;border-radius:4px;white-space:pre-wrap;">{snippet}</pre>
<p><a href="{SITE_URL}/app/scheduled-job-log?status=Failed">→ View failed scheduled jobs</a></p>"""
	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\u26a0\ufe0f {total} scheduled job failure(s) - {ts}",
		message=wrap_email("\u26a0\ufe0f Scheduled Job Failures", body, f"press-ctrl &bull; {ts}"),
	)


def _send_bg_failure_email(failed):
	from ..email_branding import wrap_email, send_alert_email
	ts = ts_now()
	rows_html = "".join(
		f"<tr><td>{esc(qn)}</td><td>{esc(fn)}</td><td><small>{esc(err[:200])}</small></td></tr>"
		for qn, fn, err in failed[:30]
	)
	body = f"""
<p><b>{len(failed)}</b> background job(s) FAILED in the last hour (deploys, syncs, agent jobs).</p>
<table {TABLE}>
<tr {TH_BG}><th>Queue</th><th>Job</th><th>Error</th></tr>
{rows_html}
</table>
<p>Inspect with <code>bench --site SITE show-pending-jobs</code> or the RQ failed registry.</p>"""
	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\u26a0\ufe0f {len(failed)} background job failure(s) - {ts}",
		message=wrap_email("\u26a0\ufe0f Background Job Failures", body, f"press-ctrl &bull; {ts}"),
	)


def _send_stuck_email(stuck):
	from ..email_branding import wrap_email, send_alert_email
	ts = ts_now()
	rows_html = "".join(
		f"<tr><td>{esc(qn)}</td><td>{esc(fn)}</td><td><b>{mins}</b> min</td></tr>"
		for qn, fn, mins, _jid in sorted(stuck, key=lambda x: -x[2])[:30]
	)
	body = f"""
<p><b>{len(stuck)}</b> background job(s) have been RUNNING for over {STUCK_JOB_MINUTES} min - likely hung.</p>
<table {TABLE}>
<tr {TH_BG}><th>Queue</th><th>Job</th><th>Running</th></tr>
{rows_html}
</table>
<p>A worker may be stuck. Check <code>supervisorctl status</code> and the RQ started registry.</p>"""
	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\u26a0\ufe0f {len(stuck)} stuck job(s) - {ts}",
		message=wrap_email("\u26a0\ufe0f Stuck / Hung Jobs", body, f"press-ctrl &bull; {ts}"),
	)
