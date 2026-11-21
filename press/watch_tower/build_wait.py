"""Build waiting for the morning health report (owner 2026-11-21): how long each developer's deploys ran yesterday,
from the build request to the site updates that followed, and the slowest benches; on Mondays also the last 7 days.

One deploy = a Deploy Candidate Build plus the Site Updates that started within FOLLOW_MINUTES of its end (later ones
were scheduled or started by hand: nobody sat through that gap). Minutes in deploys per person = the union of those
spans, so deploys running at the same time count once. Read only.
"""

from collections import defaultdict
from datetime import datetime, timedelta

import frappe
from frappe.utils import add_days, get_datetime, getdate, now_datetime

FOLLOW_MINUTES = 15
SLOWEST_BENCHES = 3


def report_data(today=None):
	"""Yesterday, and the last 7 days on Mondays; None when the section cannot be read (the report still goes out)."""
	today = getdate(today or now_datetime())
	start_of_today = datetime.combine(today, datetime.min.time())
	try:
		out = {"yesterday": collect(add_days(start_of_today, -1), start_of_today), "week": None}
		if today.weekday() == 0:
			out["week"] = collect(add_days(start_of_today, -7), start_of_today)
		return out
	except Exception:  # one section must not stop the morning report
		frappe.log_error(title="Health report: build waiting section failed", message=frappe.get_traceback())
		return None


def collect(since, until):
	builds = frappe.get_all(
		"Deploy Candidate Build",
		filters={"creation": ["between", [since, until]]},
		fields=["owner", "deploy_candidate", "group", "status", "creation", "build_end"],
		limit_page_length=10000,
	)
	follow = _site_updates([b.deploy_candidate for b in builds])
	people = defaultdict(lambda: {"deploys": 0, "failed": 0, "spans": [], "minutes": []})
	benches = defaultdict(list)
	for b in builds:
		start = get_datetime(b.creation)
		built = get_datetime(b.build_end) if b.build_end else start
		ends = [
			e for s, e in follow.get(b.deploy_candidate, []) if s <= built + timedelta(minutes=FOLLOW_MINUTES)
		]
		end = max(ends or [built])
		minutes = (end - start).total_seconds() / 60
		person = people[b.owner]
		person["deploys"] += 1
		person["failed"] += b.status == "Failure"
		person["spans"].append((start, end))
		person["minutes"].append(minutes)
		benches[b.group].append(minutes)
	developers = [
		{
			"developer": owner,
			"deploys": p["deploys"],
			"failed": p["failed"],
			"minutes_in_deploys": round(union_minutes(p["spans"])),
			"typical": round(median(p["minutes"]), 1),
			"slowest": round(max(p["minutes"]), 1),
		}
		for owner, p in people.items()
	]
	developers.sort(key=lambda d: -d["minutes_in_deploys"])
	slow = sorted(benches.items(), key=lambda kv: -median(kv[1]))[:SLOWEST_BENCHES]
	titles = dict(
		frappe.get_all(
			"Release Group",
			filters={"name": ["in", [g for g, _ in slow] or ["-"]]},
			fields=["name", "title"],
			as_list=True,
		)
	)
	return {
		"developers": developers,
		"benches": [
			{
				"bench": titles.get(g) or g,
				"deploys": len(m),
				"typical": round(median(m), 1),
				"slowest": round(max(m), 1),
			}
			for g, m in slow
		],
	}


def _site_updates(candidates):
	out = defaultdict(list)
	if not candidates:
		return out
	for su in frappe.get_all(
		"Site Update",
		filters={
			"destination_candidate": ["in", candidates],
			"update_start": ["is", "set"],
			"update_end": ["is", "set"],
		},
		fields=["destination_candidate", "update_start", "update_end"],
		limit_page_length=50000,
	):
		out[su.destination_candidate].append((get_datetime(su.update_start), get_datetime(su.update_end)))
	return out


def union_minutes(spans):
	total, cur_start, cur_end = 0.0, None, None
	for start, end in sorted(spans):
		if cur_end is None or start > cur_end:
			if cur_end is not None:
				total += (cur_end - cur_start).total_seconds()
			cur_start, cur_end = start, end
		else:
			cur_end = max(cur_end, end)
	if cur_end is not None:
		total += (cur_end - cur_start).total_seconds()
	return total / 60


def median(values):
	values = sorted(values)
	return values[len(values) // 2] if values else 0.0


def html(data, table_attrs, th_attrs, escape):
	"""The email section. Developer and bench names are escaped."""
	if not data:
		return ""
	out = _period_html("Build waiting yesterday", data["yesterday"], table_attrs, th_attrs, escape)
	if data.get("week"):
		out += _period_html("Build waiting, last 7 days", data["week"], table_attrs, th_attrs, escape)
	return out


def _period_html(title, period, table_attrs, th_attrs, escape):
	if not period["developers"]:
		return f"<h3>{title}</h3><p>No deploys.</p>"
	rows = "".join(
		f"<tr><td>{escape(d['developer'])}</td><td>{d['deploys']}</td><td>{d['failed']}</td>"
		f"<td><b>{d['minutes_in_deploys']}</b></td><td>{d['typical']}</td><td>{d['slowest']}</td></tr>"
		for d in period["developers"]
	)
	benches = "".join(
		f"<tr><td>{escape(b['bench'])}</td><td>{b['deploys']}</td><td>{b['typical']}</td><td>{b['slowest']}</td></tr>"
		for b in period["benches"]
	)
	return f"""
<h3>{title}</h3>
<table {table_attrs}>
<tr {th_attrs}><th>Developer</th><th>Deploys</th><th>Failed</th><th>Minutes in deploys</th><th>Typical deploy (min)</th><th>Slowest (min)</th></tr>
{rows}
</table>
<p style="margin:8px 0 4px">Slowest benches (typical minutes from the build request to sites updated):</p>
<table {table_attrs}>
<tr {th_attrs}><th>Bench</th><th>Deploys</th><th>Typical (min)</th><th>Slowest (min)</th></tr>
{benches}
</table>
"""
