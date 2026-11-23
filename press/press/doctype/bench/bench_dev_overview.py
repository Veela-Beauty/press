"""
Dev Tools API — dev overview, git status, console, logs, process management.
Kept in a separate file because bench.py is already >700 lines.
"""
import re
from typing import Any

import frappe
from frappe import _

from press.press.doctype.bench.bench_app_ownership import is_app_owned_by_current_team
from press.utils import ensure_team_access
from press.press.doctype.bench.dev_overview.site_container import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	_LOG_FILES,
	_LOG_PATTERN,
	_SQL_COMMENT_RE,
	_WRITE_KEYWORDS,
	_get_site_bench,
	get_db_processlist,
	get_recent_logs,
	kill_db_process,
	run_python_on_site,
	run_sql_on_site,
)
from press.press.doctype.bench.dev_overview.app_files import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	_APP_FILE_BANNED,
	_APP_FILE_MAX_BYTES,
	_validate_app_path,
	bench_list_app_files,
	bench_read_app_file,
)
from press.press.doctype.bench.dev_overview.code_server import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	_can_use_code_server,
	_ensure_code_server_role_access,
	get_code_server_status,
	restart_code_server,
	rotate_code_server_password,
	set_code_server_password_expiry_days,
	setup_code_server,
)
from press.press.doctype.bench.dev_overview.ssh import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	SSH_RULE_MUST_FOLLOW,
	bench_ssh_connect,
	bench_ssh_instructions,
	bench_ssh_register_key,
	generate_ssh_certificate,
	get_ssh_certificate,
)


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
	ensure_team_access(bench_name=bench_name)
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
	ensure_team_access(bench_name=bench_name)
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
	ensure_team_access(bench_name=bench_name)
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
		owned = is_app_owned_by_current_team(bench_name, app)
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
			results.append({"app": app, "branch": branch, "ahead": ahead, "dirty": dirty, "has_remote": has_remote, "last_msg": msg, "is_owned": owned})
		except Exception:
			results.append({"app": app, "branch": "?", "ahead": 0, "dirty": 0, "has_remote": True, "last_msg": "", "is_owned": owned})
	return results


@frappe.whitelist()
def get_bench_dev_info(bench_name):
	"""Return server IP, SSH port, and SSH access state for a bench (used by VS Code links)."""
	ensure_team_access(bench_name=bench_name)
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
def restart_bench_for_site(bench_name):
	"""Restart bench supervisor processes via the Bench doc method."""
	ensure_team_access(bench_name=bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	bench.restart_bench()


@frappe.whitelist()
def push_app_to_github(bench_name, app, message, branch_name=None):
	"""Thin shim — real implementation lives in bench_app_push.py to keep
	bench_dev_overview.py under its file-size budget."""
	from press.press.doctype.bench.bench_app_push import push_app_to_github as _impl
	return _impl(bench_name, app, message, branch_name=branch_name)


# ── App Source Read API ──────────────────────────────────────────────────────


# ── SSH Instructions API ─────────────────────────────────────────────────────
