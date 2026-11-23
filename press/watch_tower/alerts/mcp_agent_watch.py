# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""MCP Agent Watch (0.7.59): each hour the last hour of the MCP call log is read for six harmful patterns, and the owner
gets one email that lists what is new. Each event is kept as a Watch Tower Alert Log that names only the pattern, the
tool and the call-log row: every user can read the Alert Log, while the call log (code, SQL, output) is MCP Auditor only.

  refusals     a token, or calls without a valid token, refused 20+ times in the hour (probing, or a broken agent)
  destructive  SQL that drops, truncates or alters a table, or deletes / updates without WHERE
  secret hunt  code or SQL that reaches for secrets (get_password, __Auth, encryption_key, the site config, keys)
  secret out   a response that carries a secret value or a private key
  rare tool    a successful call of a dangerous tool that is rarely needed (restore, uninstall, archive, SSH cert)
  runaway      a token at 3x its usual calls per active hour, and at least 60 calls
"""

import json
import re

import frappe
from frappe.utils import add_to_date, get_url, now_datetime

from ._helpers import TABLE, esc, ts_now

RULE_NAME = "MCP Agent Watch"
RECIPIENTS = ["eng.elgogary@gmail.com"]
REFUSAL_STATUSES = ("PermissionError", "RateLimitError")
REFUSALS_PER_HOUR = 20
RUNAWAY_FACTOR = 3
RUNAWAY_MIN_CALLS = 60
CODE_TOOLS = ("site_run_sql", "site_run_python")
RARE_TOOLS = (
	"site_restore",
	"site_uninstall_app",
	"site_deactivate",
	"release_group_archive",
	"release_group_remove_app",
	"bench_ssh_cert_generate",
	"bench_run_repo_script",
)
DDL = re.compile(r"\b(drop\s+(table|database)|truncate|alter\s+table)\b", re.I)
WHERE = re.compile(r"\bwhere\b", re.I)
# frappe.conf and get_site_config are left out: agents read them for host names and flags (24 of 58 hits in a week)
SECRET_HUNT = re.compile(
	r"get_password|get_decrypted_password|__Auth|encryption_key|db_password|admin_password|api_secret"
	r"|site_config\.json|id_rsa|\.ssh/",
	re.I,
)
# MariaDB REGEXP: a secret key, then quotes / colon / spaces, then a 16+ character value ("(hidden)" never matches)
SECRET_VALUE = r"(db_password|encryption_key|api_secret|admin_password|secret_key)[\\\\\" :=']{1,12}[A-Za-z0-9+/_=-]{16,}"
PRIVATE_KEY = "%PRIVATE KEY-----%"
MAX_EVENTS = 50


def check_mcp_agent_watch(doc_dict, rule):
	"""Global: memoized because the engine calls it once per candidate document."""
	from .scheduler_alerts import _memoized

	return _memoized("mcp_agent_watch", lambda: _eval_mcp_agent_watch(rule))


def _eval_mcp_agent_watch(rule, since=None):
	since = since or add_to_date(now_datetime(), hours=-1)
	events = find_events(since)
	seen = set(
		frappe.get_all(
			"Watch Tower Alert Log",
			filters={"rule_name": RULE_NAME, "alert_datetime": [">", add_to_date(now_datetime(), hours=-3)]},
			pluck="target_document_name",
		)
	)
	new = [e for e in events if e["key"] not in seen]
	if not new:
		return False
	for event in new[:MAX_EVENTS]:
		_record(rule, event)
	_send(new[:MAX_EVENTS], total=len(new))
	return True


def find_events(since):
	return _refusals(since) + _code_events(since) + _secret_out(since) + _rare_tools(since) + _runaways(since)


def _event(pattern, row=None, key=None, token=None, detail=""):
	row = row or frappe._dict()
	return {
		"pattern": pattern,
		"key": key or f"{pattern}:{row.name}",
		"call": row.name,
		"tool": row.tool or "",
		"token": token if token is not None else (row.token or ""),
		"user": row.user or "",
		"at": row.creation,
		"detail": detail,
	}


def _refusals(since):
	rows = frappe.db.sql(
		"""
		SELECT IFNULL(token, '') AS token, COUNT(*) AS n, MAX(creation) AS creation
		FROM `tabPress MCP Call Log`
		WHERE creation >= %s AND status IN %s
		GROUP BY IFNULL(token, '') HAVING COUNT(*) >= %s
		""",
		(since, REFUSAL_STATUSES, REFUSALS_PER_HOUR),
		as_dict=True,
	)
	return [
		_event(
			"refusals",
			frappe._dict(creation=r.creation),
			key=f"refusals:{r.token or 'no-token'}:{since:%Y%m%d%H}",
			token=r.token or "(no valid token)",
			detail=f"{r.n} refused calls in the hour",
		)
		for r in rows
	]


def _code_events(since):
	rows = frappe.db.sql(
		"""
		SELECT name, tool, token, user, creation, args_json FROM `tabPress MCP Call Log`
		WHERE creation >= %s AND tool IN %s AND status = 'Success'
		ORDER BY creation LIMIT 5000
		""",
		(since, CODE_TOOLS),
		as_dict=True,
	)
	events = []
	for r in rows:
		args = _args(r.args_json)
		text = str(args.get("query") or args.get("code") or "")
		if is_destructive(r.tool, text, args):
			events.append(_event("destructive", r))
		if SECRET_HUNT.search(text):
			events.append(_event("secret hunt", r))
	return events


def is_destructive(tool, text, args):
	if tool == "site_run_sql" and not args.get("commit"):
		return False  # read-only: run_sql_on_site refuses a write without commit
	if DDL.search(text):
		return True
	return tool == "site_run_sql" and any(
		s.strip().lower().startswith(("delete", "update")) and not WHERE.search(s) for s in text.split(";")
	)


def _secret_out(since):
	rows = frappe.db.sql(
		"""
		SELECT name, tool, token, user, creation FROM `tabPress MCP Call Log`
		WHERE creation >= %s AND (response_json REGEXP %s OR response_json LIKE %s)
		LIMIT 200
		""",
		(since, SECRET_VALUE, PRIVATE_KEY),
		as_dict=True,
	)
	return [_event("secret out", r) for r in rows]


def _rare_tools(since):
	rows = frappe.db.sql(
		"""
		SELECT name, tool, token, user, creation FROM `tabPress MCP Call Log`
		WHERE creation >= %s AND tool IN %s AND status = 'Success'
		LIMIT 200
		""",
		(since, RARE_TOOLS),
		as_dict=True,
	)
	return [_event("rare tool", r) for r in rows]


def _runaways(since):
	rows = frappe.db.sql(
		"""
		SELECT h.token, h.n, h.creation, IFNULL(b.per_hour, 0) AS per_hour FROM
			(SELECT token, COUNT(*) AS n, MAX(creation) AS creation FROM `tabPress MCP Call Log`
			 WHERE creation >= %(since)s AND token IS NOT NULL GROUP BY token) h
		LEFT JOIN
			(SELECT token, COUNT(*) / COUNT(DISTINCT DATE_FORMAT(creation, '%%Y%%m%%d%%H')) AS per_hour
			 FROM `tabPress MCP Call Log` WHERE creation >= %(week)s AND creation < %(since)s AND token IS NOT NULL
			 GROUP BY token) b ON b.token = h.token
		WHERE h.n >= %(min_calls)s AND h.n > %(factor)s * IFNULL(b.per_hour, 0)
		""",
		{
			"since": since,
			"week": add_to_date(since, days=-7),
			"min_calls": RUNAWAY_MIN_CALLS,
			"factor": RUNAWAY_FACTOR,
		},
		as_dict=True,
	)
	return [
		_event(
			"runaway",
			frappe._dict(creation=r.creation),
			key=f"runaway:{r.token}:{since:%Y%m%d%H}",
			token=r.token,
			detail=f"{r.n} calls in the hour, usually {round(r.per_hour)} per active hour",
		)
		for r in rows
	]


def _args(args_json):
	try:
		value = json.loads(args_json or "{}")
	except ValueError:
		return {}  # cut at MAX_ARGS_LOG_LEN: not valid JSON
	return value if isinstance(value, dict) else {}


def _record(rule, event):
	"""An Alert Log row everyone may read: the pattern, the tool and the row name only, never code, SQL or output."""
	frappe.get_doc(
		{
			"doctype": "Watch Tower Alert Log",
			"rule": rule.name if rule else None,
			"rule_name": RULE_NAME,
			"status": "Success",
			"alert_datetime": now_datetime(),
			"triggered_by": "Scheduler",
			"target_doctype": "Press MCP Call Log" if event["call"] else None,
			"target_document": event["call"],
			"target_document_name": event["key"],
			"action_summary": f"{event['pattern']}: {event['tool'] or 'several calls'}",
		}
	).insert(ignore_permissions=True)


def _send(events, total):
	from ..email_branding import send_alert_email, wrap_email

	ts = ts_now()
	rows = "".join(
		f"<tr><td><b>{esc(e['pattern'])}</b></td><td>{esc(e['tool'])}</td><td>{esc(e['token'])}</td>"
		f"<td>{esc(e['user'])}</td><td>{esc(str(e['at'])[:19])}</td><td>{_link(e)}</td></tr>"
		for e in events
	)
	body = f"""
<p><b>{total} new MCP agent event(s)</b> in the last hour{f", the first {len(events)} below" if total > len(events) else ""}.
Open a row to see its code, SQL and output.</p>
<table {TABLE}>
<tr style="background:#f8fafc"><th>Pattern</th><th>Tool</th><th>Token</th><th>User</th><th>When</th><th>Call</th></tr>
{rows}
</table>"""
	send_alert_email(
		recipients=RECIPIENTS,
		subject=f"MCP Agent Watch: {total} event(s) {ts}",
		message=wrap_email("MCP Agent Watch", body, f"press-ctrl &bull; {ts}"),
	)


def _link(event):
	if not event["call"]:
		return esc(event["detail"])
	return f'<a href="{esc(get_url("/app/press-mcp-call-log/" + event["call"]))}">{esc(event["call"])}</a>'
