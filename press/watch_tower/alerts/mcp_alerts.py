"""MCP speed: a tool that got slower than its own usual time.

Every MCP call logs its server time (Press MCP Call Log.duration_ms). Each hour this compares a tool's average over
the last hour with its average over the 7 days before, so tools that are slow by design (deploy waits, site_run_python)
alert only when they get slower than usual for them. The server never sees a caller's own network, so a slow line on
the caller's side does not show here (2026-11-23: a caller's 11 s site_config_get was 1.2 s of server time).
"""

import frappe
from frappe.utils import add_to_date, now_datetime

from ._helpers import SITE_URL, TABLE, TH_BG, esc, should_send_alert, ts_now
from .scheduler_alerts import _memoized

MIN_CALLS = 5
SLOWER_BY = 3
MIN_AVG_MS = 1000


def check_mcp_calls_slow(doc_dict, rule):
	"""Alert when an MCP tool with MIN_CALLS calls in the last hour averaged over SLOWER_BY times its 7-day average
	and over MIN_AVG_MS. Reads Press MCP Call Log; never writes. Memoized: the engine calls this once per candidate."""
	return _memoized("mcp_calls_slow", _eval_mcp_calls_slow)


def _eval_mcp_calls_slow():
	# cutoffs from Frappe's clock, the one `creation` is written with (NOW() is the database session's clock)
	now = now_datetime()
	rows = frappe.db.sql(
		"""
		SELECT recent.tool, recent.calls, recent.avg_ms, usual.avg_ms AS usual_ms
		FROM (
			SELECT tool, COUNT(duration_ms) AS calls, AVG(duration_ms) AS avg_ms FROM `tabPress MCP Call Log`
			WHERE creation > %(hour_ago)s GROUP BY tool
		) recent
		JOIN (
			SELECT tool, AVG(duration_ms) AS avg_ms FROM `tabPress MCP Call Log`
			WHERE creation > %(week_ago)s AND creation <= %(hour_ago)s GROUP BY tool
		) usual ON usual.tool = recent.tool
		WHERE recent.calls >= %(min_calls)s AND recent.avg_ms > %(min_avg_ms)s
			AND recent.avg_ms > usual.avg_ms * %(slower_by)s
		ORDER BY recent.avg_ms DESC LIMIT 20
		""",
		{
			"hour_ago": add_to_date(now, hours=-1),
			"week_ago": add_to_date(now, days=-7),
			"min_calls": MIN_CALLS,
			"min_avg_ms": MIN_AVG_MS,
			"slower_by": SLOWER_BY,
		},
		as_dict=True,
	)
	if not rows:
		return False
	# fingerprint on the tool names only (not the hour or the times): should_send_alert then caps a lasting slowdown
	# at 3 emails per 6 h instead of one every hour
	if not should_send_alert("mcp_calls_slow", "|".join(sorted(r.tool for r in rows))):
		return True
	_send_slow_email(rows)
	return True


def _send_slow_email(rows):
	from ..email_branding import send_alert_email, wrap_email

	ts = ts_now()
	table_rows = "".join(
		f"<tr><td>{esc(r.tool)}</td><td>{r.calls}</td><td><b>{float(r.avg_ms) / 1000:.1f} s</b></td>"
		f"<td>{float(r.usual_ms) / 1000:.1f} s</td></tr>"
		for r in rows
	)
	body = f"""
<p>{len(rows)} MCP tool(s) ran over {SLOWER_BY} times slower than usual in the last hour.</p>
<table {TABLE}>
<tr {TH_BG}><th>Tool</th><th>Calls</th><th>Average, last hour</th><th>Average, last 7 days</th></tr>
{table_rows}
</table>
<p><a href="{SITE_URL}/app/press-mcp-call-log">Open the MCP call log</a></p>"""
	more = f" and {len(rows) - 1} more" if len(rows) > 1 else ""
	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"MCP calls slow: {rows[0].tool}{more} - {ts}",
		message=wrap_email("MCP calls slow", body, f"press-ctrl &bull; {ts}"),
	)
