# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Memory pressure on an app server over SSH, cached 60 s per server (moved from deploy_flow.py in 0.7.54)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import add_to_date, now_datetime

_HOST_MEMORY_PRESSURE_CACHE_TTL = 60  # seconds


@frappe.whitelist()
def host_memory_pressure(server: str, force_refresh: bool = False) -> dict[str, Any]:
	"""Snapshot of memory pressure on an app server. Read-only.

	SSH-based: runs `cat /proc/meminfo` on the target server via Press's
	existing Ansible-adhoc pattern. No Prometheus dependency.

	Results are cached per-server for 60 seconds (the SSH+Ansible round-trip
	takes 3-10s — repeated calls within 60s return cached data in <100ms).
	Pass force_refresh=True to bypass the cache (e.g. right after restarting
	a worker to confirm memory dropped).

	Use this BEFORE memory-heavy ops (big reports, simultaneous backups) and
	as the FIRST check when multiple sites on a server start returning 500s.

	Why this exists: 2026-05-23 outage. MariaDB on press-f1 was OOM-killed
	(swap 100% full + RAM exhausted). All 32 sites 500ed for ~25 min until
	manual SSH diagnosis. An agent calling this tool would have seen
	verdict='critical' minutes before the OOM.

	Args:
		server: App server docname (e.g. 'press-f1.sandbox.mvpstorm.com').

	Returns:
		{
			"server": <server>,
			"verdict": "ok" | "elevated" | "critical" | "unknown",
			"reason": <human-readable>,
			"memory_total_mb": <int>,
			"memory_available_mb": <int>,
			"swap_used_pct": <int>,
			"recent_oom_kills": [...],
			"hint": <next action if verdict != ok>,
		}

	Verdict rules:
		ok        — available_mb > 1500 AND swap_used_pct < 80
		elevated  — 500 < available_mb <= 1500 OR swap_used_pct >= 80
		critical  — available_mb <= 500 OR swap_used_pct >= 95
		unknown   — SSH failed or /proc/meminfo missing
	"""
	if not frappe.db.exists("Server", server):
		frappe.throw(f"Server {server!r} not found", frappe.DoesNotExistError)

	# Cache hit? Return immediately to avoid 3-10s SSH round-trip on every poll.
	cache_key = f"mcp:host_memory_pressure:{server}"
	if not force_refresh:
		cached = frappe.cache().get_value(cache_key)
		if cached:
			cached["_cached"] = True
			return cached

	# Use Press's existing Ansible ad-hoc pattern to SSH the target server.
	# Inventory format: single host with trailing comma.
	meminfo_text = None
	try:
		from press.press.doctype.ansible_console.ansible_console import AnsibleAdHoc

		adhoc = AnsibleAdHoc(sources=f"{server},")
		# raw_params=True so the shell module gets the literal command.
		results = adhoc.run("cat /proc/meminfo", raw_params=True)
		# results is a list of host-result dicts; pick the first
		for host_result in results or []:
			out = host_result.get("output") or host_result.get("stdout") or ""
			if out and "MemTotal" in out:
				meminfo_text = out
				break
	except Exception as e:
		return {
			"server": server,
			"verdict": "unknown",
			"reason": f"SSH/Ansible query failed: {e!s}",
			"memory_total_mb": None,
			"memory_available_mb": None,
			"swap_used_pct": None,
			"recent_oom_kills": [],
			"hint": "Check that press-ctrl can SSH to this server (ansible-playbook -m ping).",
		}

	if not meminfo_text:
		return {
			"server": server,
			"verdict": "unknown",
			"reason": "Ansible ran but /proc/meminfo output was empty",
			"memory_total_mb": None,
			"memory_available_mb": None,
			"swap_used_pct": None,
			"recent_oom_kills": [],
			"hint": "Manually verify SSH to the server works.",
		}

	# Parse /proc/meminfo. All values are in kB.
	fields = {}
	for line in meminfo_text.splitlines():
		if ":" in line:
			k, v = line.split(":", 1)
			try:
				fields[k.strip()] = int(v.strip().split()[0])
			except (ValueError, IndexError):
				continue

	mem_total_kb = fields.get("MemTotal", 0)
	mem_available_kb = fields.get("MemAvailable", 0)
	swap_total_kb = fields.get("SwapTotal", 0)
	swap_free_kb = fields.get("SwapFree", 0)
	swap_used_kb = swap_total_kb - swap_free_kb
	swap_used_pct = int((swap_used_kb / swap_total_kb) * 100) if swap_total_kb else 0
	memory_total_mb = mem_total_kb // 1024
	memory_available_mb = mem_available_kb // 1024

	# Verdict — combines available memory + swap pressure
	if memory_available_mb <= 500 or swap_used_pct >= 95:
		verdict = "critical"
		reason = (
			f"Only {memory_available_mb} MB available; swap {swap_used_pct}% used. "
			f"OOM-killer is one bad query away."
		)
		hint = (
			"STOP scheduling memory-heavy ops. Restart 1-2 idle bench gunicorns "
			"to reclaim ~200MB each. Consider scheduling site backups for after "
			"off-hours. If this persists, scale RAM or move sites to another host."
		)
	elif memory_available_mb <= 1500 or swap_used_pct >= 80:
		verdict = "elevated"
		reason = (
			f"{memory_available_mb} MB available, swap {swap_used_pct}% used. "
			"Under the 1.5 GB / 80% safety floor."
		)
		hint = (
			"Avoid concurrent backups / big reports / bulk inserts. "
			"Investigate zombie processes (esbuild watchers from dev mode "
			"are a known cause)."
		)
	else:
		verdict = "ok"
		reason = f"{memory_available_mb} MB available, swap {swap_used_pct}% used — healthy."
		hint = ""

	# Scan recent Agent Jobs for explicit OOM evidence (job_type doesn't say
	# OOM but Failure traceback often mentions 'Killed' or signal 9).
	cutoff = add_to_date(now_datetime(), minutes=-30)
	recent_oom = []
	try:
		failures = frappe.db.sql(
			"""SELECT name, job_type, status, traceback, creation
			   FROM `tabAgent Job`
			   WHERE server = %s AND status = 'Failure' AND creation > %s
			   ORDER BY creation DESC LIMIT 20""",
			(server, cutoff),
			as_dict=True,
		)
		now = now_datetime()
		for f in failures:
			tb = (f.traceback or "")[-2000:]
			if "Killed" in tb or "signal 9" in tb or "OOM" in tb.upper() or "MemoryError" in tb:
				recent_oom.append({
					"job_name": f.name,
					"job_type": f.job_type,
					"age_seconds": int((now - f.creation).total_seconds()),
				})
	except Exception:
		pass

	result = {
		"server": server,
		"verdict": verdict,
		"reason": reason,
		"memory_total_mb": memory_total_mb,
		"memory_available_mb": memory_available_mb,
		"swap_used_pct": swap_used_pct,
		"recent_oom_kills": recent_oom,
		"hint": hint,
		"_cached": False,
	}
	frappe.cache().set_value(cache_key, result, expires_in_sec=_HOST_MEMORY_PRESSURE_CACHE_TTL)
	return result
