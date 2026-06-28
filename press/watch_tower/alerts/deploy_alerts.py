"""Deploy-related Watch Tower alerts -  stuck and failed builds."""
import frappe
from frappe.utils import get_datetime
from ._helpers import TABLE, TH_BG, SITE_URL, esc, ts_now, should_send_alert


def check_failed_deploys(doc_dict, rule):
	"""Check for failed deploys in last hour, include error details."""
	failed = frappe.db.sql("""
		SELECT name, status, build_start, build_end, build_error
		FROM `tabDeploy Candidate Build`
		WHERE status = 'Failure'
			AND modified > NOW() - INTERVAL 1 HOUR
		ORDER BY creation DESC LIMIT 10
	""", as_dict=True)

	if not failed:
		return False

	fingerprint = ",".join(sorted(b.name for b in failed))
	if not should_send_alert("deploy_failed", fingerprint):
		return False

	_send_failed_deploy_email(failed)
	return True


def _send_failed_deploy_email(failed):
	from ..email_branding import wrap_email, send_alert_email
	ts = ts_now()

	rows = ""
	for b in failed:
		start = get_datetime(b.build_start).strftime("%b %d %H:%M") if b.build_start else "\u2014"
		error = esc(str(b.build_error or "No error captured")[:300])
		rows += (
			f"<tr><td><a href='{SITE_URL}/dashboard/deploys/{b.name}'>{b.name}</a></td>"
			f"<td>{start}</td>"
			f"<td style='color:#ef4444'>{error}</td></tr>"
		)

	body = f"""
<table {TABLE}>
<tr {TH_BG}><th>Build</th><th>Started</th><th>Error</th></tr>
{rows}
</table>
<p><a href="{SITE_URL}/dashboard/deploys">\u2192 View all deploys</a></p>"""

	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"\u274c Press: {len(failed)} deploy build(s) failed",
		important=True,
		message=wrap_email(f"274c Deploy Build Failed ({len(failed)})", body, f"press-ctrl &bull; {ts}"),
	)
