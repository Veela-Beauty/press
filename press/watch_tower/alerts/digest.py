"""Daily alert digest (0.7.77). An alert that needs no action within hours is kept here and shown once a day in the
08:00 health report instead of arriving as its own email (26 Nov 2026: about 60 alert emails a day, all through the
Brevo account Press also sends customer emails with). Urgent alerts skip it: send_alert_email(important=True) or
(immediate=True)."""

import json
import re

DIGEST_KEY = "wt:digest:alerts"
MAX_KEPT = 2000  # newest kept if a broken check fires all day; bounds the Redis list
_DATE_TIME = re.compile(r"\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}(?::\d{2})?)?")


def kind_of(subject):
	"""The alert type: the subject without its counts, dates and times, so "17 scheduled job failure(s) - 2026-11-24
	21:00" and "16 scheduled job failure(s) - 2026-11-24 05:01" are one type."""
	s = _DATE_TIME.sub("", subject)
	s = re.sub(r"\d+", "N", s)
	s = re.sub(r"[\s\u2014-]+$", "", s)
	return re.sub(r"\s+", " ", s).strip()


def _cache(cache):
	if cache is not None:
		return cache
	import frappe

	return frappe.cache()


def add(subject, at, cache=None):
	"""Keep one alert for the next report (subject and time only; the dashboard has the detail)."""
	c = _cache(cache)
	c.rpush(DIGEST_KEY, json.dumps({"subject": str(subject)[:200], "at": str(at)[:16]}))
	c.ltrim(DIGEST_KEY, -MAX_KEPT, -1)


def peek(cache=None):
	"""The kept alerts, oldest first. They stay until clear(n) after the report was sent."""
	out = []
	for raw in _cache(cache).lrange(DIGEST_KEY, 0, -1) or []:
		try:
			out.append(json.loads(raw))
		except (TypeError, ValueError):
			continue
	return out


def clear(n, cache=None):
	"""Drop the n oldest alerts (the ones the sent report showed); any added since stay for the next report."""
	if n > 0:
		_cache(cache).ltrim(DIGEST_KEY, n, -1)


def group(items):
	"""One row per alert type: how many times, first and last time, the latest subject. Most frequent first."""
	rows = {}
	for it in items:
		k = kind_of(it["subject"])
		row = rows.setdefault(
			k, {"kind": k, "times": 0, "first": it["at"], "last": it["at"], "subject": it["subject"]}
		)
		row["times"] += 1
		row["first"] = min(row["first"], it["at"])
		if it["at"] >= row["last"]:
			row["last"], row["subject"] = it["at"], it["subject"]
	return sorted(rows.values(), key=lambda r: (-r["times"], r["kind"]))


def html(items, table, th_bg, esc):
	"""The report section, or "" when nothing was kept."""
	rows = group(items)
	if not rows:
		return ""
	body = "".join(
		f"<tr><td>{esc(r['subject'])}</td><td><b>{r['times']}</b></td>"
		f"<td>{esc(r['first'][5:])}</td><td>{esc(r['last'][5:])}</td></tr>"
		for r in rows
	)
	return f"""
<h3>Alerts since the last report</h3>
<table {table}>
<tr {th_bg}><th>Latest alert</th><th>Times</th><th>First</th><th>Last</th></tr>
{body}
</table>
"""
