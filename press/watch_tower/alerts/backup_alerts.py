"""Daman Backup health Watch Tower alerts."""
import frappe
from ._helpers import TABLE, esc, ts_now


def check_backup_health(doc_dict, rule):
	"""
	Check Daman Backup health:
	- Consecutive failures > 3 for any client
	- No successful backup in last 48 hours
	- Stuck running jobs > 4 hours
	- Recent failed jobs in last 24h
	"""
	from ..email_branding import wrap_email, send_alert_email

	if not frappe.db.exists("DocType", "Backup Client"):
		return False

	issues = []
	ts = ts_now()

	# 1. Clients with consecutive failures > 3
	failing_clients = frappe.db.sql("""
		SELECT client_name, consecutive_failures, last_backup_on,
			days_since_last_backup, total_failed_count
		FROM `tabBackup Client`
		WHERE status = 'Active' AND auto_backup_enabled = 1
			AND consecutive_failures >= 3
	""", as_dict=True)

	for c in failing_clients:
		issues.append(
			f"<tr><td>{esc(c.client_name)}</td>"
			f"<td style='color:#ef4444'><b>{c.consecutive_failures} consecutive failures</b></td>"
			f"<td>Last success: {c.last_backup_on or 'Never'}</td></tr>"
		)

	# 2. Active clients with no backup in 48 hours
	stale_clients = frappe.db.sql("""
		SELECT client_name, last_backup_on, days_since_last_backup
		FROM `tabBackup Client`
		WHERE status = 'Active' AND auto_backup_enabled = 1
			AND (last_backup_on < NOW() - INTERVAL 48 HOUR OR last_backup_on IS NULL)
	""", as_dict=True)

	failing_names = {fc.client_name for fc in failing_clients}
	for c in stale_clients:
		if c.client_name not in failing_names:
			issues.append(
				f"<tr><td>{esc(c.client_name)}</td>"
				f"<td style='color:#f59e0b'><b>No backup in {c.days_since_last_backup or '?'}+ days</b></td>"
				f"<td>Last: {c.last_backup_on or 'Never'}</td></tr>"
			)

	# 3. Stuck running jobs (> 4 hours)
	stuck_jobs = frappe.db.sql("""
		SELECT name, client, progress_percent, current_phase, started_at,
			TIMESTAMPDIFF(MINUTE, started_at, NOW()) as running_min
		FROM `tabBackup Job Queue`
		WHERE status = 'Running' AND started_at < NOW() - INTERVAL 4 HOUR
	""", as_dict=True)

	for j in stuck_jobs:
		issues.append(
			f"<tr><td>{esc(j.client)}</td>"
			f"<td style='color:#ef4444'><b>Stuck at {j.progress_percent}% for {j.running_min} min</b></td>"
			f"<td>{j.current_phase} \u2014 {j.name}</td></tr>"
		)

	# 4. Recent failed jobs (last 24h)
	recent_fails = frappe.db.sql("""
		SELECT client, name, error_message, finished_at
		FROM `tabBackup Job Queue`
		WHERE status = 'Failed' AND finished_at > NOW() - INTERVAL 24 HOUR
		ORDER BY finished_at DESC
		LIMIT 5
	""", as_dict=True)

	if not issues and not recent_fails:
		return False

	body = ""
	if issues:
		body += f"""
<h3 style="color:#ef4444">Backup Issues Detected</h3>
<table {TABLE}>
<tr style="background:#f8fafc"><th>Client</th><th>Issue</th><th>Details</th></tr>
{"".join(issues)}
</table>"""

	if recent_fails:
		fail_rows = ""
		for f in recent_fails:
			err = esc(str(f.error_message or "")[:120])
			fail_rows += (
				f"<tr><td>{esc(f.client)}</td><td>{f.name}</td>"
				f"<td style='color:#ef4444'>{err}</td></tr>"
			)
		body += f"""
<h3>Recent Failures (24h)</h3>
<table {TABLE}>
<tr style="background:#f8fafc"><th>Client</th><th>Job</th><th>Error</th></tr>
{fail_rows}
</table>"""

	body += """
<p style="margin-top:16px">
<a href="https://autodeploypanel.mvpstorm.com/app/backup-job-queue?status=Failed">View Failed Jobs</a> &bull;
<a href="https://autodeploypanel.mvpstorm.com/app/backup-client">View Clients</a>
</p>"""

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\u26a0\ufe0f Backup Alert: {len(issues)} issue(s) \u2014 {ts}",
		important=True,
		message=wrap_email("26a0Fe0f Backup Health Alert", body, f"Daman Backup &bull; {ts}"),
	)
	return True
