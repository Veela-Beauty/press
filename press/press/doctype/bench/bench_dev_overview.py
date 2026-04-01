"""
Dev Tools API — dev overview, git status, console, logs, process management.
Kept in a separate file because bench.py is already >700 lines.
"""
import re

import frappe
from frappe import _


@frappe.whitelist()
def get_dev_overview_benches():
	"""Return all non-archived benches enriched with commit, build, sites, and gap data."""
	frappe.only_for("System Manager")

	benches = frappe.get_all(
		"Bench",
		fields=[
			"name",
			"status",
			"group",
			"group.title as group_title",
			"server",
			"server.title as server_title",
			"cluster.title as cluster_title",
			"is_development_bench",
			"creation",
			"candidate",
		],
		filters={"status": ["not in", ["Archived"]]},
		order_by="is_development_bench desc, name asc",
		limit=200,
	)

	if not benches:
		return []

	bench_names = [b.name for b in benches]

	# ── sites per bench ──────────────────────────────────────────────────────
	all_sites = frappe.get_all(
		"Site",
		filters={"bench": ["in", bench_names]},
		fields=["name", "bench", "status"],
	)
	sites_by_bench = {}
	for s in all_sites:
		sites_by_bench.setdefault(s.bench, []).append(s)

	# ── apps (hashes) per bench ───────────────────────────────────────────────
	bench_apps = frappe.get_all(
		"Bench App",
		filters={"parent": ["in", bench_names]},
		fields=["parent", "app", "hash"],
	)
	apps_by_bench = {}
	for a in bench_apps:
		apps_by_bench.setdefault(a.parent, []).append(a)

	# ── app releases for all hashes (batch) ──────────────────────────────────
	all_hashes = list({a.hash for a in bench_apps if a.hash})[:100]
	releases_map = {}
	if all_hashes:
		for rel in frappe.get_all(
			"App Release",
			filters={"hash": ["in", all_hashes]},
			fields=["hash", "message", "author", "timestamp"],
		):
			releases_map[rel.hash] = rel

	# ── undeployed gap: one batch SQL instead of N COUNT queries (2A perf fix) ──
	# Build (app, deployed_timestamp) pairs, then one query with GROUP BY.
	app_ts_pairs = []
	app_to_benches: dict[str, list[str]] = {}
	for app_entry in bench_apps:
		deployed_rel = releases_map.get(app_entry.hash) if app_entry.hash else None
		ts = deployed_rel.timestamp if deployed_rel else None
		if not ts:
			continue
		app_ts_pairs.append((app_entry.app, ts))
		app_to_benches.setdefault(app_entry.app, []).append(app_entry.parent)

	undeployed_by_bench: dict = {}
	if app_ts_pairs:
		or_clauses = " OR ".join(["(app = %s AND timestamp > %s)"] * len(app_ts_pairs))
		params = [v for pair in app_ts_pairs for v in pair]
		rows = frappe.db.sql(
			f"SELECT app, COUNT(*) as cnt FROM `tabApp Release` WHERE {or_clauses} GROUP BY app",
			params,
			as_dict=True,
		)
		for row in rows:
			for bench_name in app_to_benches.get(row.app, []):
				undeployed_by_bench[bench_name] = (
					undeployed_by_bench.get(bench_name, 0) + row.cnt
				)

	# ── assemble ─────────────────────────────────────────────────────────────
	result = []
	for bench in benches:
		b = dict(bench)

		bench_sites = sites_by_bench.get(bench.name, [])
		b["site_count"] = len(bench_sites)
		b["pending_update_count"] = sum(
			1 for s in bench_sites if s.status == "Pending"
		)
		b["undeployed_count"] = undeployed_by_bench.get(bench.name, 0)

		# last commit: first app with a known release message
		b["last_commit"] = None
		for app_entry in apps_by_bench.get(bench.name, []):
			rel = releases_map.get(app_entry.hash)
			if rel and rel.message:
				b["last_commit"] = {
					"app": app_entry.app,
					"hash": (app_entry.hash or "")[:7],
					"message": (rel.message or "").split("\n")[0][:80],
					"author": rel.author or "",
					"timestamp": str(rel.timestamp) if rel.timestamp else "",
				}
				break

		result.append(b)

	return result


@frappe.whitelist()
def get_dev_panel_data(bench_name):
	"""
	Return data for the expanded DevOverview panel for a specific bench.
	Called directly (not as a doc method) to avoid touching bench.py.
	"""
	frappe.only_for("System Manager")
	bench_doc = frappe.get_doc("Bench", bench_name)
	# ── sites ─────────────────────────────────────────────────────────────────
	sites = frappe.get_all(
		"Site",
		filters={"bench": bench_doc.name},
		fields=["name", "status", "host_name", "is_development_site"],
	)

	site_names = [s.name for s in sites]

	# migration status per site (batch)
	activities = {}
	if site_names:
		for act in frappe.get_all(
			"Site Activity",
			filters={"site": ["in", site_names], "action": ["in", ["Migrate", "Update"]]},
			fields=["site", "action", "creation"],
			order_by="creation desc",
		):
			# only keep the most recent per site
			if act.site not in activities:
				activities[act.site] = act

	# scheduler status per site via site config key
	scheduler_map = {}
	if site_names:
		for cfg in frappe.get_all(
			"Site Config",
			filters={"parent": ["in", site_names], "key": "pause_scheduler"},
			fields=["parent", "value"],
		):
			# bool("0") == True, so use explicit truthy check
			scheduler_map[cfg.parent] = cfg.value in (True, 1, "1", "true", True)

	for s in sites:
		s["migrated"] = bool(activities.get(s.name))
		s["scheduler_enabled"] = not scheduler_map.get(s.name, False)

	# ── recent commits from bench apps — batched (1A perf fix) ───────────────
	app_hashes = {ae.hash: ae for ae in bench_doc.apps if ae.hash}
	panel_releases_map = {}
	if app_hashes:
		for rel in frappe.get_all(
			"App Release",
			filters={"hash": ["in", list(app_hashes.keys())]},
			fields=["hash", "message", "author", "timestamp"],
		):
			panel_releases_map[rel.hash] = rel

	recent_commits = []
	for app_entry in bench_doc.apps:
		rel = panel_releases_map.get(app_entry.hash)
		if rel and rel.message:
			recent_commits.append(
				{
					"app": app_entry.app,
					"hash": (app_entry.hash or "")[:7],
					"message": (rel.message or "").split("\n")[0][:80],
					"author": rel.author or "",
					"timestamp": str(rel.timestamp) if rel.timestamp else "",
				}
			)

	# ── build history (last 5 deploy candidates for this group) ───────────────
	build_history = frappe.get_all(
		"Deploy Candidate",
		filters={"group": bench_doc.group},
		fields=["name", "status", "creation"],
		order_by="creation desc",
		limit=5,
	)

	# ── recent errors (failed agent jobs for bench sites) ─────────────────────
	error_list = []
	if site_names:
		error_list = frappe.get_all(
			"Agent Job",
			filters={"site": ["in", site_names], "status": "Failure"},
			fields=["name", "job_type", "creation", "site"],
			order_by="creation desc",
			limit=10,
		)

	return {
		"sites": sites,
		"recent_commits": recent_commits,
		"build_history": [dict(b) for b in build_history],
		"errors": {
			"count": len(error_list),
			"errors": [dict(e) for e in error_list],
		},
	}


@frappe.whitelist()
def get_bench_app_names(bench_name):
	"""Return the list of app names installed on a bench (for the Push dialog dropdown)."""
	frappe.only_for("System Manager")
	rows = frappe.get_all(
		"Bench App",
		filters={"parent": bench_name},
		fields=["app"],
		order_by="idx asc",
	)
	return [r.app for r in rows]


@frappe.whitelist()
def get_app_git_status(bench_name):
	"""
	Return per-app git status for a bench: branch, commits ahead of remote,
	dirty file count, and last commit message.
	Single docker_execute call (batched) — polls all apps in one shell script.
	"""
	frappe.only_for("System Manager")
	bench = frappe.get_doc("Bench", bench_name)
	app_names = [ae.app for ae in bench.apps if ae.app]
	if not app_names:
		return []
	# Build a single shell script that iterates all apps and outputs one line per app
	# Format per line: APP_NAME:branch:ahead:dirty:last_msg
	lines = ["set -e"]
	for app in app_names:
		lines.append(
			f"cd apps/{app} 2>/dev/null && "
			f"branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?') && "
			f"ahead=$(git rev-list --count '@{{u}}..HEAD' 2>/dev/null || echo 0) && "
			f"dirty=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ') && "
			f"msg=$(git log -1 --format='%s' 2>/dev/null | cut -c1-60) && "
			f'echo "{app}:$branch:$ahead:$dirty:$msg" && cd ../.. '
			f'|| echo "{app}:?:0:0:" && cd ../.. 2>/dev/null'
		)
	cmd = " ; ".join(lines)
	try:
		raw = bench.docker_execute(cmd, save_output=False, create_log=False)
		output = (raw.get("output") or "").strip()
	except Exception:
		return [{"app": a, "branch": "?", "ahead": 0, "dirty": 0, "last_msg": ""} for a in app_names]
	results = []
	for line in output.split("\n"):
		line = line.strip()
		if not line:
			continue
		# Format: app:branch:ahead:dirty:msg
		parts = line.split(":", 4)
		if len(parts) < 1:
			continue
		app = parts[0]
		results.append({
			"app": app,
			"branch": parts[1] if len(parts) > 1 else "?",
			"ahead": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0,
			"dirty": int(parts[3]) if len(parts) > 3 and parts[3].strip().isdigit() else 0,
			"last_msg": parts[4].strip() if len(parts) > 4 else "",
		})
	return results


@frappe.whitelist()
def restart_bench_for_site(bench_name):
	"""Restart bench supervisor processes via the Bench doc method."""
	frappe.only_for("System Manager")
	bench = frappe.get_doc("Bench", bench_name)
	bench.restart_bench()


@frappe.whitelist()
def push_app_to_github(bench_name, app, message):
	"""
	Run git add -A && git commit -m <message> && git push inside the bench
	container for the given app. Uses bench.docker_execute() — requires the
	bench to be Active and the container to have SSH keys for GitHub.
	"""
	frappe.only_for("System Manager")
	bench = frappe.get_doc("Bench", bench_name)
	# Escape single quotes to prevent shell injection
	safe_message = message.replace("'", "'\\''")
	cmd = f"git add -A && git commit -m '{safe_message}' && git push"
	return bench.docker_execute(cmd, subdir=f"apps/{app}")


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
	"""Run a SQL query on a site via bench mariadb (base64 pipe, injection-safe)."""
	import base64
	frappe.only_for("System Manager")
	# Strip SQL comments before checking first keyword
	stripped = _SQL_COMMENT_RE.sub("", query).strip()
	first_word = (stripped.split()[0] if stripped else "").upper()
	if first_word in _WRITE_KEYWORDS and not commit:
		return {"error": f"Write query ({first_word}) blocked — pass commit=True to allow."}
	site, bench = _get_site_bench(site_name)
	b64 = base64.b64encode(query.encode()).decode()
	cmd = f"echo '{b64}' | base64 -d | bench --site {site.name} mariadb"
	try:
		raw = bench.docker_execute(cmd)
		return {"output": raw.get("output", ""), "returncode": raw.get("returncode", 0)}
	except Exception as e:
		return {"error": str(e)}


@frappe.whitelist()
def run_python_on_site(site_name, code):
	"""Run Python code on a site via bench console (base64 pipe, injection-safe)."""
	import base64
	frappe.only_for("System Manager")
	site, bench = _get_site_bench(site_name)
	b64 = base64.b64encode(code.encode()).decode()
	# b64 is [A-Za-z0-9+/=] — completely shell-safe in single quotes
	cmd = f"echo '{b64}' | base64 -d | bench --site {site.name} console"
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
	frappe.only_for("System Manager")
	bench = frappe.get_doc("Bench", bench_name)
	# Tail each file separately (avoids ==> header <== from multi-file tail),
	# grep for timestamped lines only, sort reverse, take top N
	safe_limit = str(int(limit))
	files = " ".join(_LOG_FILES)
	cmd = (
		f"for f in {files}; do "
		f"[ -f $f ] && tail -n 50 $f; "
		f"done 2>/dev/null | grep -E '^[0-9]{{4}}-' | sort -r | head -n {safe_limit}"
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
	frappe.only_for("System Manager")
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
	frappe.only_for("System Manager")
	process_id = int(process_id)  # Raises ValueError/TypeError for non-int
	site, bench = _get_site_bench(site_name)
	cmd = f"bench --site {site.name} mariadb -e 'KILL {process_id}'"
	try:
		return bench.docker_execute(cmd)
	except Exception as e:
		return {"error": str(e)}
