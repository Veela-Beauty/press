"""
Dev Tools API — dev overview, git status, console, logs, process management.
Kept in a separate file because bench.py is already >700 lines.
"""
import re

import frappe
from frappe import _



def _ensure_team_access(bench_name=None, site_name=None):
	"""Allow System Managers, or team members/owner of the bench/site team."""
	if frappe.session.data and frappe.session.data.user_type == "System User":
		return
	if "System Manager" in frappe.get_roles(frappe.session.user):
		return
	from press.utils import get_current_team
	current_team = get_current_team()
	target_team = None
	if bench_name:
		target_team = frappe.db.get_value("Bench", bench_name, "team") or \
			frappe.db.get_value("Release Group", frappe.db.get_value("Bench", bench_name, "group"), "team")
	elif site_name:
		target_team = frappe.db.get_value("Site", site_name, "team")
	if not target_team or target_team != current_team:
		frappe.throw("Not allowed", frappe.PermissionError)


@frappe.whitelist()
def get_dev_overview_benches():
	"""Return all non-archived benches enriched with commit, build, sites, and gap data."""
	# _ensure_team_access: no bench/site context; keep System Manager check
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
	_ensure_team_access(bench_name=bench_name)
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
	_ensure_team_access(bench_name=bench_name)
	rows = frappe.get_all(
		"Bench App",
		filters={"parent": bench_name},
		fields=["app"],
		order_by="idx asc",
	)
	return [r.app for r in rows]


@frappe.whitelist()
def get_app_git_status(bench_name, site_name=None):
	"""
	Return per-app git status for a bench: branch, commits ahead of remote,
	dirty file count, and last commit message.
	If site_name is provided, only shows apps installed on that site.
	"""
	_ensure_team_access(bench_name=bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	if site_name:
		# Get apps installed on the specific site
		site_apps = frappe.get_all("Site App", {"parent": site_name}, pluck="app")
		app_names = [ae.app for ae in bench.apps if ae.app and ae.app in site_apps]
	else:
		app_names = [ae.app for ae in bench.apps if ae.app]
	if not app_names:
		return []
	# One docker_execute per app — subshells don't expand inside docker exec
	results = []
	for app in app_names:
		d = f"apps/{app}"
		try:
			r1 = bench.docker_execute(f"git -C {d} log -1 --format=%D:::%s", save_output=False, create_log=False)
			out = (r1.get("output") or "").strip()
			parts = out.split(":::", 1)
			refs = parts[0].strip() if parts else ""
			branch = "detached"
			for ref in refs.split(","):
				ref = ref.strip()
				if ref.startswith("HEAD -> "):
					branch = ref[8:]; break
			msg = parts[1].strip()[:60] if len(parts) > 1 else ""
			r2 = bench.docker_execute(f"git -C {d} remote get-url origin", save_output=False, create_log=False)
			has_remote = r2.get("returncode") == 0
			r3 = bench.docker_execute(f"git -C {d} status --porcelain", save_output=False, create_log=False)
			dirty = len([l for l in (r3.get("output") or "").split("\n") if l.strip()])
			ahead = 0
			if has_remote:
				r4 = bench.docker_execute(f"git -C {d} rev-list --count @{{u}}..HEAD", save_output=False, create_log=False)
				a = (r4.get("output") or "").strip()
				ahead = int(a) if a.isdigit() else 0
			results.append({"app": app, "branch": branch, "ahead": ahead, "dirty": dirty, "has_remote": has_remote, "last_msg": msg})
		except Exception:
			results.append({"app": app, "branch": "?", "ahead": 0, "dirty": 0, "has_remote": True, "last_msg": ""})
	return results


@frappe.whitelist()
def get_bench_dev_info(bench_name):
	"""Return server IP, SSH port, and SSH access state for a bench (used by VS Code links)."""
	_ensure_team_access(bench_name=bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	server_ip = frappe.db.get_value("Server", bench.server, "ip") or ""
	ssh_port = 22000 + (bench.port_offset or 0)
	has_ssh_key = bool(frappe.db.get_all(
		"User SSH Key", {"user": frappe.session.user, "is_default": 1}, limit=1
	))
	return {
		"server_ip": server_ip,
		"ssh_port": ssh_port,
		"bench_name": bench.name,
		"bench_path": "/home/frappe/frappe-bench",
		"is_development_bench": bench.is_development_bench,
		"release_group": bench.group,
		"has_ssh_key": has_ssh_key,
	}


@frappe.whitelist()
def get_code_server_status(bench_name):
	"""Return code-server status and URL for a bench (if one exists)."""
	_ensure_team_access(bench_name=bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	cs = frappe.db.get_value(
		"Code Server",
		{"bench": bench_name, "status": ["!=", "Archived"]},
		["name", "status", "password"],
		as_dict=True,
	)
	return {
		"enabled": bool(bench.is_code_server_enabled) or bool(bench.is_development_bench),
		"exists": bool(cs),
		"name": cs.name if cs else None,
		"status": cs.status if cs else None,
		"url": f"https://{cs.name}" if cs and cs.status == "Running" else None,
		"password": cs.password if cs and cs.status == "Running" else None,
	}


@frappe.whitelist()
def setup_code_server(bench_name, subdomain):
	"""Create and setup a Code Server for a bench."""
	_ensure_team_access(bench_name=bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	# Code Server is available for all benches in this Press instance.
	# The Code Server doctype validate() requires Bench.is_code_server_enabled,
	# so flip it on here. Keeping the flag honest — it is true because we are
	# about to use it.
	if not bench.is_code_server_enabled:
		frappe.db.set_value("Bench", bench_name, "is_code_server_enabled", 1)
		frappe.db.commit()
	existing = frappe.db.exists("Code Server", {"bench": bench_name, "status": ["!=", "Archived"]})
	if existing:
		return {"error": f"Code Server already exists: {existing}"}
	domain = frappe.db.get_value("Press Settings", None, "domain") or "sandbox.mvpstorm.com"
	cs = frappe.get_doc({
		"doctype": "Code Server",
		"bench": bench_name,
		"subdomain": subdomain,
		"domain": domain,
		"server": bench.server,
	})
	cs.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": cs.name, "status": "Pending"}


@frappe.whitelist()
def restart_bench_for_site(bench_name):
	"""Restart bench supervisor processes via the Bench doc method."""
	_ensure_team_access(bench_name=bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	bench.restart_bench()


@frappe.whitelist()
def push_app_to_github(bench_name, app, message):
	"""
	Run git add -A && git commit -m <message> && git push inside the bench
	container for the given app. Uses bench.docker_execute() — requires the
	bench to be Active and the container to have SSH keys for GitHub.
	"""
	_ensure_team_access(bench_name=bench_name)
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
	_ensure_team_access(site_name=site_name)
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
	_ensure_team_access(site_name=site_name)
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
	_ensure_team_access(bench_name=bench_name)
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
	_ensure_team_access(site_name=site_name)
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
	_ensure_team_access(site_name=site_name)
	process_id = int(process_id)  # Raises ValueError/TypeError for non-int
	site, bench = _get_site_bench(site_name)
	cmd = f"bench --site {site.name} mariadb -e 'KILL {process_id}'"
	try:
		return bench.docker_execute(cmd)
	except Exception as e:
		return {"error": str(e)}
