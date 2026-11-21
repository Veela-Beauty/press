"""Deploy Times page (Press dashboard; owner 2026-11-21, prototype PRS-SP-03): per developer per day and per bench,
how long deploys ran from the build request to the site updates that followed, and where a typical deploy's time goes.
Same counting as the morning report (build_wait.py). System users only, read only, cached 10 minutes.
"""

from collections import defaultdict
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import add_days, get_datetime, getdate, now_datetime

from press.watch_tower.build_wait import FOLLOW_MINUTES, median, union_minutes

CACHE_KEY = "press:deploy_times"
CACHE_SECONDS = 600
SHOWN_DAYS = 30  # the page shows 7 or 30 days and compares with the period before, so 60 days are read


@frappe.whitelist()
def get_deploy_times():
	if frappe.session.data.user_type != "System User":  # the rule press/api/account.py uses for system users
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	data = frappe.cache.get_value(CACHE_KEY)
	if not data:
		data = build()
		frappe.cache.set_value(CACHE_KEY, data, expires_in_sec=CACHE_SECONDS)
	return data


def build():
	today = getdate(now_datetime())
	builds = frappe.get_all(
		"Deploy Candidate Build",
		filters={"creation": [">=", add_days(today, -2 * SHOWN_DAYS)]},
		fields=[
			"name",
			"owner",
			"deploy_candidate",
			"group",
			"status",
			"creation",
			"build_end",
			"build_duration",
		],
		limit_page_length=50000,
	)
	updates = _site_updates([b.deploy_candidate for b in builds])
	cut = add_days(today, -SHOWN_DAYS)
	days = defaultdict(lambda: defaultdict(lambda: {"deploys": 0, "failed": 0, "spans": [], "minutes": []}))
	benches = defaultdict(lambda: {"wall": [], "build": [], "site": [], "by": defaultdict(int), "failed": 0})
	followed = {}
	for b in builds:
		start = get_datetime(b.creation)
		built = get_datetime(b.build_end) if b.build_end else start
		follow = [
			u
			for u in updates.get(b.deploy_candidate, [])
			if u.start <= built + timedelta(minutes=FOLLOW_MINUTES)
		]
		followed[b.deploy_candidate] = follow
		end = max([u.end for u in follow] or [built])
		minutes = (end - start).total_seconds() / 60
		d = days[b.owner][str(start.date())]
		d["deploys"] += 1
		d["failed"] += b.status == "Failure"
		d["spans"].append((start, end))
		d["minutes"].append(minutes)
		if start.date() >= cut:
			g = benches[b.group]
			g["wall"].append(minutes)
			g["build"].append(_seconds(b.build_duration) / 60)
			g["site"] += [u.minutes for u in follow]
			g["by"][b.owner] += 1
			g["failed"] += b.status == "Failure"
	names = dict(
		frappe.get_all(
			"User", filters={"name": ["in", list(days) or ["-"]]}, fields=["name", "full_name"], as_list=True
		)
	)
	return {
		"today": str(today),
		"developers": {
			owner: {
				"name": names.get(owner) or owner,
				"days": {
					day: {
						"deploys": v["deploys"],
						"failed": v["failed"],
						"minutes": round(union_minutes(v["spans"])),
						"typical": round(median(v["minutes"]), 1),
						"slowest": round(max(v["minutes"]), 1),
					}
					for day, v in sorted(per_day.items())
				},
			}
			for owner, per_day in days.items()
		},
		"benches": _bench_rows(benches, names),
		"stages": _stages([b for b in builds if get_datetime(b.creation).date() >= cut], followed),
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
		fields=["destination_candidate", "update_start", "update_end", "update_duration"],
		limit_page_length=200000,
	):
		out[su.destination_candidate].append(
			frappe._dict(
				start=get_datetime(su.update_start),
				end=get_datetime(su.update_end),
				minutes=_seconds(su.update_duration) / 60,
			)
		)
	return out


def _bench_rows(benches, names):
	groups = frappe.get_all(
		"Release Group", filters={"name": ["in", list(benches) or ["-"]]}, fields=["name", "title"]
	)
	titles = {g.name: g.title for g in groups}
	apps = defaultdict(int)
	for row in frappe.get_all(
		"Release Group App", filters={"parent": ["in", list(benches) or ["-"]]}, fields=["parent"]
	):
		apps[row.parent] += 1
	sites = defaultdict(int)
	for row in frappe.get_all(
		"Site", filters={"group": ["in", list(benches) or ["-"]], "status": "Active"}, fields=["group"]
	):
		sites[row.group] += 1
	rows = []
	for group, g in benches.items():
		top = max(g["by"].items(), key=lambda kv: kv[1])[0]
		rows.append(
			{
				"group": group,
				"bench": titles.get(group) or group,
				"apps": apps[group],
				"sites": sites[group],
				"deploys": len(g["wall"]),
				"failed": g["failed"],
				"typical": round(median(g["wall"]), 1),
				"slowest": round(max(g["wall"]), 1),
				"build": round(median(g["build"]), 1),
				"site_update": round(median(g["site"]), 1),
				"main": names.get(top) or top,
			}
		)
	return sorted(rows, key=lambda r: -r["deploys"] * r["typical"])


def _stages(builds, followed):
	"""Typical minutes per stage over the shown period: build, wait for the server job, start the bench, wait for the
	site update, update the sites. Agent Job start/end come from the server agent's clock (UTC) while Press stamps the
	rest in the site's time zone: the whole-hour offset between a job's creation and start is taken out."""
	ok = [b for b in builds if b.status == "Success"]
	benches = dict(
		frappe.get_all(
			"Bench",
			filters={"candidate": ["in", [b.deploy_candidate for b in ok] or ["-"]]},
			fields=["candidate", "name"],
			as_list=True,
		)
	)
	jobs = {
		j.bench: j
		for j in frappe.get_all(
			"Agent Job",
			filters={
				"job_type": "New Bench",
				"status": "Success",
				"bench": ["in", list(benches.values()) or ["-"]],
			},
			fields=["bench", "creation", "start", "end", "duration"],
			limit_page_length=20000,
		)
	}
	offsets = sorted(
		round((get_datetime(j.start) - get_datetime(j.creation)).total_seconds() / 3600)
		for j in jobs.values()
		if j.start
	)
	offset = timedelta(hours=offsets[len(offsets) // 2]) if offsets else timedelta(0)
	build, wait_job, start_bench, wait_site, update = [], [], [], [], []
	for b in ok:
		build.append(_seconds(b.build_duration))
		job = jobs.get(benches.get(b.deploy_candidate))
		follow = followed.get(b.deploy_candidate) or []
		if follow:
			update.append(max(u.minutes for u in follow) * 60)
		if not (job and job.start and job.end and b.build_end):
			continue
		start, end = get_datetime(job.start) - offset, get_datetime(job.end) - offset
		wait_job.append((start - get_datetime(b.build_end)).total_seconds())
		start_bench.append(_seconds(job.duration))
		if follow:
			wait_site.append((min(u.start for u in follow) - end).total_seconds())
	return [
		{"name": "Build", "kind": "work", "min": _minutes(build)},
		{"name": "Wait for the server job", "kind": "wait", "min": _minutes(wait_job)},
		{"name": "Start the bench", "kind": "work", "min": _minutes(start_bench)},
		{"name": "Wait for the site update", "kind": "wait", "min": _minutes(wait_site)},
		{"name": "Update the sites", "kind": "work", "min": _minutes(update)},
	]


def _minutes(seconds):
	return round(max(0.0, median(seconds)) / 60, 1)


def _seconds(value):
	if not value:
		return 0.0
	if isinstance(value, timedelta):
		return value.total_seconds()
	if isinstance(value, int | float):  # Site Update keeps seconds, Deploy Candidate Build "h:mm:ss"
		return float(value)
	text = str(value)
	if ":" not in text:
		return float(text)
	h, m, s = text.split(":")
	return int(h) * 3600 + int(m) * 60 + float(s)
