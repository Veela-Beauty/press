# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Commands run inside a bench's container: SQL and the Python console on a site, the database process list and
kill, and the recent bench logs (moved from bench_dev_overview.py in 0.7.56)."""

import re

import frappe

from press.utils import ensure_team_access


# ── Shared helpers ───────────────────────────────────────────────────────────

def _get_site_bench(site_name):
	"""Load Site + its parent Bench doc. Used by console/processlist APIs."""
	site = frappe.get_doc("Site", site_name)
	bench = frappe.get_doc("Bench", site.bench)
	return site, bench


# ── Console APIs ─────────────────────────────────────────────────────────────

_WRITE_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "REPLACE"}


_SQL_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


@frappe.whitelist()
def run_sql_on_site(site_name, query, commit=False):
	"""Run a SQL query on a site via bench mariadb (base64 pipe, injection-safe).

	The pipeline must run INSIDE the bench container, not on the host. The
	old `cmd = "echo ... | bench ..."` got assembled into the host command
	`docker exec ... echo ... | bench ...` — the host shell sees `|` as a
	pipe boundary and runs `bench` on the HOST (where it isn't on PATH for
	non-interactive Press Agent processes), not inside the container.

	Wrap the whole pipeline in `bash -lc '...'` so docker exec ships a
	SINGLE arg to the container's bash, which then reads the frappe user's
	profile (-l) and finds `bench` at /home/frappe/.local/bin/bench.
	"""
	import base64
	ensure_team_access(site_name=site_name)
	# Strip SQL comments before checking first keyword
	stripped = _SQL_COMMENT_RE.sub("", query).strip()
	first_word = (stripped.split()[0] if stripped else "").upper()
	if first_word in _WRITE_KEYWORDS and not commit:
		return {"error": f"Write query ({first_word}) blocked — pass commit=True to allow."}
	site, bench = _get_site_bench(site_name)
	b64 = base64.b64encode(query.encode()).decode()
	# b64 is [A-Za-z0-9+/=] — safe in single quotes
	cmd = f"bash -lc 'echo {b64} | base64 -d | bench --site {site.name} mariadb'"
	try:
		raw = bench.docker_execute(cmd)
		return {"output": raw.get("output", ""), "returncode": raw.get("returncode", 0)}
	except Exception as e:
		return {"error": str(e)}


@frappe.whitelist()
def run_python_on_site(site_name, code):
	"""Run Python code on a site via bench console (base64 pipe, injection-safe).

	Same in-container pipeline pattern as run_sql_on_site — see that
	function's docstring for the bash -lc rationale.
	"""
	import base64
	ensure_team_access(site_name=site_name)
	site, bench = _get_site_bench(site_name)
	b64 = base64.b64encode(code.encode()).decode()
	cmd = f"bash -lc 'echo {b64} | base64 -d | bench --site {site.name} console'"
	try:
		raw = bench.docker_execute(cmd)
		return {"output": raw.get("output", ""), "returncode": raw.get("returncode", 0)}
	except Exception as e:
		return {"error": str(e)}


# ── Recent Logs API ──────────────────────────────────────────────────────────

_LOG_PATTERN = re.compile(
	r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}),?\d*\s+"
	r"(ERROR|WARNING|INFO|DEBUG)\s+"
	r"(\S+?)\s+(.*)$"
)


# Log files available in a typical bench container
_LOG_FILES = [
	"logs/frappe.log",
	"logs/scheduler.log",
	"logs/web.error.log",
	"logs/bench.log",
]


@frappe.whitelist()
def get_recent_logs(bench_name, log_type=None, limit=50):
	"""Read recent log lines from bench container (frappe.log, scheduler.log, web.error.log, bench.log)."""
	ensure_team_access(bench_name=bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	# cat all log files, grep timestamped lines, sort reverse, take top N.
	# Avoids shell for-loops which break in docker_execute escaping.
	safe_limit = str(int(limit))
	files = " ".join(_LOG_FILES)
	cmd = (
		f"cat {files} 2>/dev/null"
		f" | grep -E '^[0-9]{{4}}-' | sort -r | head -n {safe_limit}"
	)
	try:
		raw = bench.docker_execute(cmd)
		output = (raw.get("output") or "").strip()
	except Exception:
		return []
	if not output:
		return []
	entries = []
	for line in output.split("\n"):
		line = line.strip()
		if not line:
			continue
		m = _LOG_PATTERN.match(line)
		if not m:
			continue
		level = m.group(2)
		if log_type and log_type.upper() != level:
			continue
		entries.append({
			"timestamp": m.group(1),
			"level": level,
			"source": m.group(3),
			"message": m.group(4).strip(),
		})
	return entries


# ── DB Process List APIs ─────────────────────────────────────────────────────

@frappe.whitelist()
def get_db_processlist(site_name):
	"""Return active MariaDB processes for a site via SHOW PROCESSLIST."""
	ensure_team_access(site_name=site_name)
	site, bench = _get_site_bench(site_name)
	# Sanitize site name for SQL LIKE — allow only alphanumeric, dash, dot, underscore
	safe_db_name = re.sub(r"[^a-zA-Z0-9._-]", "", site.name).replace("-", "_")
	cmd = (
		f"bench --site {site.name} mariadb -e "
		"\"SELECT ID, USER, TIME, COMMAND AS state, "
		"SUBSTRING(INFO, 1, 200) AS query "
		"FROM INFORMATION_SCHEMA.PROCESSLIST "
		f"WHERE DB LIKE '%{safe_db_name}%' "
		"ORDER BY TIME DESC\" --batch"
	)
	try:
		raw = bench.docker_execute(cmd)
		output = (raw.get("output") or "").strip()
	except Exception:
		return []
	if not output:
		return []
	lines = output.split("\n")
	results = []
	for line in lines:
		parts = line.split("\t")
		if len(parts) < 4:
			continue
		# Skip header row
		if parts[0] == "ID" or parts[0] == "id":
			continue
		try:
			proc_id = int(parts[0])
		except (ValueError, IndexError):
			continue
		results.append({
			"id": proc_id,
			"user": parts[1] if len(parts) > 1 else "",
			"time": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0,
			"state": parts[3] if len(parts) > 3 else "",
			"query": parts[4].strip() if len(parts) > 4 else "",
		})
	return results


@frappe.whitelist()
def kill_db_process(site_name, process_id):
	"""Kill a MariaDB process by ID for a site."""
	ensure_team_access(site_name=site_name)
	process_id = int(process_id)  # Raises ValueError/TypeError for non-int
	site, bench = _get_site_bench(site_name)
	cmd = f"bench --site {site.name} mariadb -e 'KILL {process_id}'"
	try:
		return bench.docker_execute(cmd)
	except Exception as e:
		return {"error": str(e)}
