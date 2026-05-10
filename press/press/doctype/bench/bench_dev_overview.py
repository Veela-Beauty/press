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
def get_ssh_certificate(bench_name):
	"""Return the user's current SSH certificate status for this bench's release group.

	Iterates ALL the user's enabled keys (not just default) and returns data for the
	first key with a non-expired cert. Default key wins on ties. If no key has a
	valid cert, returns has_valid_cert=False with the default key's label as a hint.

	Shape:
	  {has_ssh_key, has_valid_cert, cert_name, valid_until, expires_in_seconds,
	   certificate, principal, key_label}
	Used by the Bench Actions page to decide Local VS Code card state.
	"""
	ensure_team_access(bench_name=bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	rg = frappe.get_doc("Release Group", bench.group)
	# Default key first — wins ties, and surfaces the right label when no cert is valid.
	keys = frappe.db.get_all(
		"User SSH Key",
		filters={"user": frappe.session.user, "is_disabled": 0, "is_removed": 0},
		fields=["name", "label"],
		order_by="is_default desc, creation asc",
	)
	result = {
		"has_ssh_key": bool(keys), "has_valid_cert": False, "cert_name": None,
		"valid_until": None, "expires_in_seconds": 0, "certificate": None,
		"principal": rg.name, "key_label": keys[0].label if keys else None,
	}
	now = frappe.utils.now_datetime()
	for key in keys:
		cert = rg.get_certificate(ssh_key_name=key.name)
		if not cert:
			continue
		expires_in = max(0, int((frappe.utils.get_datetime(cert.valid_until) - now).total_seconds()))
		if expires_in <= 0:
			continue
		result.update({
			"has_valid_cert": True, "cert_name": cert.name,
			"valid_until": str(cert.valid_until), "expires_in_seconds": expires_in,
			"certificate": cert.ssh_certificate, "key_label": key.label,
		})
		break
	return result


@frappe.whitelist()
def generate_ssh_certificate(bench_name):
	"""Mint a new SSH certificate for the caller + this bench's release group.

	Delegates to ReleaseGroup.generate_certificate which enforces team.ssh_access_enabled
	and the ReleaseGroupActions.SSHAccess role guard. Returns the same shape as
	get_ssh_certificate so the UI can unify its handling.
	"""
	ensure_team_access(bench_name=bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	rg = frappe.get_doc("Release Group", bench.group)
	rg.generate_certificate()
	frappe.db.commit()
	return get_ssh_certificate(bench_name)


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


def _can_use_code_server(bench_name, team):
	"""Non-raising variant of the role check — returns bool for UI rendering.

	Logs unexpected exceptions via frappe.log_error so silent denial doesn't
	mask bugs (e.g. schema changes, import failures, cross-team probes).
	"""
	from press.api.feature_access import has_feature
	try:
		return bool(has_feature(team=team, feature_id="code_server"))
	except Exception:
		frappe.log_error(
			title="Code Server can_use probe failed",
			message=f"bench={bench_name} team={team}\n{frappe.get_traceback()}",
		)
		return False


@frappe.whitelist()
def get_code_server_status(bench_name):
	"""Return code-server status and URL for a bench (if one exists)."""
	ensure_team_access(bench_name=bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	cs_row = frappe.db.get_value(
		"Code Server",
		{"bench": bench_name, "status": ["!=", "Archived"]},
		["name", "status", "password", "password_set_at", "password_expiry_days"],
		as_dict=True,
	)
	result = {
		"enabled": bool(bench.is_code_server_enabled) or bool(bench.is_development_bench),
		"can_use": _can_use_code_server(bench_name, bench.team),
		"exists": bool(cs_row),
		"name": cs_row.name if cs_row else None,
		"status": cs_row.status if cs_row else None,
		"url": f"https://{cs_row.name}" if cs_row and cs_row.status == "Running" else None,
		"password": None,
	}
	if cs_row:
		# Always attach expiry info (even while Pending) so UI can render countdown.
		# Password fieldtype masks via frappe.db.get_value — must call get_password()
		# on the doc to decrypt. Only return it when Running.
		cs_doc = frappe.get_doc("Code Server", cs_row.name)
		if cs_row.status == "Running":
			result["password"] = cs_doc.get_password("password")
		result["password_set_at"] = cs_row.password_set_at
		result["password_expires_at"] = cs_doc.get_password_expires_at()
		result["password_expiry_days"] = cs_doc.get_password_expiry_days()
		result["password_is_expired"] = cs_doc.is_password_expired()
	return result


def _ensure_code_server_role_access(bench_name):
	"""Team-member check + role-level Code Server feature-access check.

	Use at every Code Server mutation endpoint. Returns the team name on success
	so callers don't re-query. Raises PermissionError when the caller's role has
	Code Server disabled — the role/team config is enforced by has_feature.
	"""
	ensure_team_access(bench_name=bench_name)
	team = frappe.db.get_value("Bench", bench_name, "team")
	from press.api.feature_access import has_feature
	if not has_feature(team=team, feature_id="code_server"):
		frappe.throw(
			"Code Server is not enabled for your role. Ask an admin to grant the Code Server feature on your role.",
			frappe.PermissionError,
		)
	return team


@frappe.whitelist()
def setup_code_server(bench_name, subdomain):
	"""Create and setup a Code Server for a bench."""
	_ensure_code_server_role_access(bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	# Code Server is available for all benches in this Press instance.
	# The Code Server doctype validate() requires Bench.is_code_server_enabled,
	# AND the bench container's supervisor.conf needs a [program:code-server]
	# block which is only rendered when is_code_server_enabled is in the bench
	# config JSON. save() triggers Bench.on_update → update_bench_config job
	# which regenerates supervisor.conf + reread + update inside the container.
	# Without this, "Setup Code Server" fails with "supervisorctl start code-server:"
	# exit 2 (program not found).
	# Flag lives in TWO places: the Bench DB column (Code Server validate gate)
	# and the bench_config JSON (agent's supervisor.conf template reads this).
	#
	# bench.save() unfortunately resets this field back to 0 somewhere in
	# Press's validate chain (the rebuild of bench_config reads self.
	# is_code_server_enabled at line 345 of bench.py but something earlier
	# clears it — even direct assignment before save() fails). So we bypass
	# the doctype save entirely: write both column and JSON directly, then
	# manually queue the Update Bench Configuration agent job to regenerate
	# supervisor.conf inside the container.
	import json as _json
	from press.agent import Agent
	config_json = _json.loads(bench.bench_config or "{}")
	if not bench.is_code_server_enabled or not config_json.get("is_code_server_enabled"):
		config_json["is_code_server_enabled"] = True
		frappe.db.set_value(
			"Bench",
			bench_name,
			{
				"is_code_server_enabled": 1,
				"bench_config": _json.dumps(config_json, indent=4),
			},
			update_modified=False,
		)
		frappe.db.commit()
		# Reload bench so Agent.update_bench_config sees the new JSON
		bench = frappe.get_doc("Bench", bench_name)
		Agent(bench.server).update_bench_config(bench)
	# Block retry if there's a non-archived Code Server already
	existing = frappe.db.exists("Code Server", {"bench": bench_name, "status": ["!=", "Archived"]})
	if existing:
		return {"error": f"Code Server already exists: {existing}"}

	# Clean up orphan Archived rows with the same target name — the Code Server
	# doctype name is subdomain+domain, so archived failed attempts collide with
	# new creates. Delete them to free the name for a clean retry.
	domain = frappe.db.get_value("Press Settings", None, "domain") or "sandbox.mvpstorm.com"
	candidate_name = f"{subdomain}.{domain}"
	for stale in frappe.db.get_all(
		"Code Server",
		filters={"name": candidate_name, "status": "Archived"},
		pluck="name",
	):
		frappe.delete_doc("Code Server", stale, force=True, ignore_permissions=True)
	frappe.db.commit()

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
	ensure_team_access(bench_name=bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	bench.restart_bench()


@frappe.whitelist()
def push_app_to_github(bench_name, app, message, branch_name=None):
	"""Thin shim — real implementation lives in bench_app_push.py to keep
	bench_dev_overview.py under its file-size budget."""
	from press.press.doctype.bench.bench_app_push import push_app_to_github as _impl
	return _impl(bench_name, app, message, branch_name=branch_name)



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


# ── App Source Read API ──────────────────────────────────────────────────────

# 1 MB cap on app file reads. App source files are mostly <100 KB; the cap
# stops accidental reads of huge generated/vendored files (e.g. compiled JS
# bundles, locale .po files) that would blow past Frappe's response budget.
_APP_FILE_MAX_BYTES = 1 * 1024 * 1024

# Path-traversal guard: reject any segment that resolves outside apps/<app>/.
_APP_FILE_BANNED = ("..", "")


def _validate_app_path(app: str, relative_path: str) -> str:
	"""Sanitize + canonicalize the requested file path.

	Returns the absolute path inside the container (under
	/home/frappe/frappe-bench/apps/<app>/) ready to pass to `cat`.
	Raises frappe.ValidationError on traversal attempts or empty input.
	"""
	if not app or not isinstance(app, str) or "/" in app or app in _APP_FILE_BANNED:
		raise frappe.ValidationError(f"app name {app!r} is invalid")
	if not relative_path or not isinstance(relative_path, str):
		raise frappe.ValidationError("relative_path must be a non-empty string")
	# Reject ../ traversal and absolute paths (re-rooting via leading /)
	if relative_path.startswith("/"):
		raise frappe.ValidationError("relative_path must not be absolute")
	for seg in relative_path.split("/"):
		if seg in _APP_FILE_BANNED or seg.startswith(".."):
			raise frappe.ValidationError(
				f"relative_path segment {seg!r} is not allowed"
			)
	# Container-side path. The bench's docker_execute pwd is already
	# /home/frappe/frappe-bench, but we use the absolute path for clarity
	# and to avoid the agent's subdir kwarg.
	return f"/home/frappe/frappe-bench/apps/{app}/{relative_path}"


@frappe.whitelist()
def bench_read_app_file(
	bench_name: str,
	app: str,
	relative_path: str,
) -> dict[str, Any]:
	"""Read a source file from an app installed in this bench.

	Args:
		bench_name: Bench docname (e.g. "bench-0015-000012-press-f1")
		app: app name as installed in apps/ (e.g. "erpnext", "frappe", "press")
		relative_path: path under apps/<app>/ (e.g.
			"erpnext/accounts/report/general_ledger/general_ledger.py")

	Returns:
		{path, content, encoding, size_bytes} on success, or
		{error, path} on missing file / oversize / read failure.

	Read-only by design — no write counterpart. Use site_file_write for
	user-uploaded content; source files should not be edited via MCP.
	"""
	ensure_team_access(bench_name=bench_name)
	abs_path = _validate_app_path(app, relative_path)
	bench = frappe.get_doc("Bench", bench_name)
	# Wrap in `bash -lc '...'` for the same reason as run_sql_on_site:
	# the host shell would otherwise interpret `<` and `|` as its own
	# redirects/pipes. See run_sql_on_site docstring for full rationale.
	size_cmd = f"bash -lc 'wc -c < {abs_path} 2>/dev/null || echo MISSING'"
	try:
		size_raw = bench.docker_execute(size_cmd, create_log=False)
	except Exception as e:
		return {"error": str(e), "path": abs_path}
	size_text = (size_raw.get("output") or "").strip()
	if not size_text or size_text == "MISSING":
		return {"error": "not_found", "path": abs_path}
	try:
		size_bytes = int(size_text)
	except ValueError:
		return {"error": "could_not_stat", "path": abs_path, "raw": size_text}
	if size_bytes > _APP_FILE_MAX_BYTES:
		return {
			"error": "too_large",
			"path": abs_path,
			"size_bytes": size_bytes,
			"limit_bytes": _APP_FILE_MAX_BYTES,
		}
	# base64-pipe to dodge any binary content / control chars that would
	# corrupt the stdout payload going back through Press Agent.
	read_cmd = f"bash -lc 'base64 -w0 {abs_path}'"
	try:
		raw = bench.docker_execute(read_cmd, create_log=False)
	except Exception as e:
		return {"error": str(e), "path": abs_path}
	import base64 as _b64
	encoded = (raw.get("output") or "").strip()
	try:
		data = _b64.b64decode(encoded)
	except Exception:
		return {"error": "decode_failed", "path": abs_path}
	# Try utf-8; fall back to base64 for binaries (rare in apps/).
	try:
		content = data.decode("utf-8")
		return {
			"path": abs_path,
			"content": content,
			"encoding": "utf-8",
			"size_bytes": size_bytes,
		}
	except UnicodeDecodeError:
		return {
			"path": abs_path,
			"content_b64": encoded,
			"encoding": "base64",
			"size_bytes": size_bytes,
		}


@frappe.whitelist()
def bench_list_app_files(
	bench_name: str,
	app: str,
	relative_path: str = "",
	pattern: str | None = None,
) -> dict[str, Any]:
	"""List files under apps/<app>/<relative_path>/ inside the bench container.

	Args:
		bench_name: Bench docname
		app: app name
		relative_path: subdir under apps/<app>/ ("" = app root)
		pattern: optional glob (e.g. "*.py", "**/general_ledger*"). Find -name.

	Returns: {dir, files: [...], count} (capped at 200 entries).
	"""
	ensure_team_access(bench_name=bench_name)
	# Reuse path validator with a sentinel name when relative_path is empty
	probe_path = relative_path if relative_path else "."
	# Validation: empty string is fine ("." resolves to app root); other
	# checks (../, /) still apply.
	if relative_path:
		_validate_app_path(app, relative_path)
	if "/" in app or not app or app in _APP_FILE_BANNED:
		raise frappe.ValidationError(f"app name {app!r} is invalid")
	dir_abs = f"/home/frappe/frappe-bench/apps/{app}"
	if relative_path:
		dir_abs = f"{dir_abs}/{relative_path}"
	bench = frappe.get_doc("Bench", bench_name)
	# find with -path stays inside the dir, -maxdepth caps recursion
	if pattern:
		# Sanitize pattern: only allow alphanumeric + glob chars
		import re as _re
		if not _re.match(r"^[A-Za-z0-9_./*?\[\]-]+$", pattern):
			raise frappe.ValidationError(
				f"pattern {pattern!r} contains disallowed characters"
			)
		# Wrap in bash -lc so the | head pipe runs in the container
		find_cmd = (
			f"bash -lc \"find {dir_abs} -name '{pattern}' -type f "
			f"2>/dev/null | head -200\""
		)
	else:
		find_cmd = (
			f"bash -lc 'find {dir_abs} -maxdepth 2 -type f "
			f"2>/dev/null | head -200'"
		)
	try:
		raw = bench.docker_execute(find_cmd, create_log=False)
	except Exception as e:
		return {"error": str(e), "dir": dir_abs}
	output = (raw.get("output") or "").strip()
	if not output:
		return {"dir": dir_abs, "files": [], "count": 0}
	files = [line.strip() for line in output.split("\n") if line.strip()]
	return {"dir": dir_abs, "files": files, "count": len(files)}


# ── SSH Instructions API ─────────────────────────────────────────────────────


@frappe.whitelist()
def bench_ssh_register_key(public_key: str, label: str | None = None) -> dict[str, Any]:
	"""Register the caller's SSH public key with Press (one-time, before
	bench_ssh_cert_generate can sign it).

	Press signs ONLY keys that are registered for the current user under
	`User SSH Key`. External agents (no dashboard session) must call this
	tool to upload their pubkey before requesting a cert. The pubkey is
	stored against frappe.session.user (the token's owner).

	Args:
		public_key: full ssh-ed25519 / ssh-rsa / ecdsa-... public key string
			(the .pub file content, including the algorithm prefix)
		label: optional human-readable label for the key

	Returns:
		{name, label, is_default, fingerprint}

	Idempotent: if the same key is already registered, returns the
	existing record without raising.
	"""
	if not public_key or not isinstance(public_key, str):
		raise frappe.ValidationError("public_key must be a non-empty string")
	pk = public_key.strip()
	# Crude prefix check — the doctype validator does the real parsing.
	if not pk.split(" ", 1)[0] in (
		"ssh-ed25519", "ssh-rsa", "ecdsa-sha2-nistp256",
		"ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521",
	):
		raise frappe.ValidationError(
			"public_key must start with a supported algorithm "
			"(ssh-ed25519, ssh-rsa, ecdsa-sha2-*)"
		)
	# Check for duplicate by full pubkey content — Press stores it as a Code field
	existing = frappe.db.get_value(
		"User SSH Key",
		{
			"user": frappe.session.user,
			"ssh_public_key": pk,
			"is_removed": 0,
		},
		["name", "label", "is_default"],
		as_dict=True,
	)
	if existing:
		return {
			"name": existing.name,
			"label": existing.label,
			"is_default": bool(existing.is_default),
			"already_registered": True,
		}
	doc = frappe.get_doc({
		"doctype": "User SSH Key",
		"user": frappe.session.user,
		"ssh_public_key": pk,
		"label": label or "mcp-issued",
		# Auto-default if this is the user's first key (so cert tool finds it)
		"is_default": 1 if not frappe.db.exists(
			"User SSH Key",
			{"user": frappe.session.user, "is_disabled": 0, "is_removed": 0},
		) else 0,
	}).insert(ignore_permissions=True)
	frappe.db.commit()
	return {
		"name": doc.name,
		"label": doc.label,
		"is_default": bool(doc.is_default),
		"already_registered": False,
	}


@frappe.whitelist()
def bench_ssh_instructions(
	bench_name: str,
	site_name: str | None = None,
) -> dict[str, Any]:
	"""Return human-readable SSH connection instructions for a bench.

	Pure information lookup — does NOT grant access. To actually get SSH
	in, the caller needs to (1) upload their pubkey via bench_ssh_register_key,
	then (2) call bench_ssh_cert_generate to sign it.

	Args:
		bench_name: Bench docname (e.g. "bench-0015-000012-press-f1")
		site_name: optional site name to include site-specific paths

	Returns:
		{server_ip, ssh_port, user, paths, commands, do, do_not,
		 prerequisite, how_to_get_cert, connect_command}
	"""
	ensure_team_access(bench_name=bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	server = bench.server
	server_ip = frappe.db.get_value("Server", server, "ip") or server
	# Real port = 22000 + bench.port_offset (per get_bench_dev_info — same
	# logic Press uses for its own VS Code links). Hardcoded 22 was wrong.
	ssh_port = 22000 + (bench.port_offset or 0)
	bench_path = "/home/frappe/frappe-bench"
	apps_path = f"{bench_path}/apps"
	site_paths: dict[str, str] = {}
	if site_name:
		# Validate the site is on this bench
		site_bench = frappe.db.get_value("Site", site_name, "bench")
		if site_bench != bench_name:
			raise frappe.ValidationError(
				f"Site {site_name!r} is not on bench {bench_name!r} "
				f"(it's on {site_bench!r}). Pick a site on this bench."
			)
		site_paths = {
			"site_root": f"{bench_path}/sites/{site_name}",
			"site_config": f"{bench_path}/sites/{site_name}/site_config.json",
			"public_files": f"{bench_path}/sites/{site_name}/public/files",
			"private_files": f"{bench_path}/sites/{site_name}/private/files",
		}
	# Has the caller already registered an SSH key? Tells the agent
	# whether they need to do step 1 first.
	has_registered_key = bool(frappe.db.exists(
		"User SSH Key",
		{
			"user": frappe.session.user,
			"is_disabled": 0,
			"is_removed": 0,
		},
	))
	return {
		"server": server,
		"server_ip": server_ip,
		"ssh_port": ssh_port,
		"user": "frappe",
		"has_registered_key": has_registered_key,
		"prerequisite": (
			"You need TWO MCP calls before you can SSH in:\n"
			"  1. bench_ssh_register_key(public_key=<your-id_ed25519.pub-content>)\n"
			"     — registers your pubkey under your User SSH Key. Idempotent.\n"
			"  2. bench_ssh_cert_generate(bench_name=<bench>) — signs your\n"
			"     registered key with Press's CA. Returns a short-lived cert.\n"
			"\n"
			"Save the certificate string from (2) to ~/.ssh/id_ed25519-cert.pub\n"
			"alongside your matching id_ed25519 private key. SSH will pick up\n"
			"the cert automatically when you connect with -i ~/.ssh/id_ed25519."
		)
		if not has_registered_key
		else (
			"You already have a registered SSH key. Just call "
			"bench_ssh_cert_generate(bench_name=<bench>) to mint a cert "
			"signed against your registered key, save it to "
			"~/.ssh/<your-key>-cert.pub, then ssh in with the connect_command."
		),
		"connect_command": (
			f"ssh -p {ssh_port} -i ~/.ssh/<your-key-with-cert> frappe@{server_ip}"
		),
		"after_login_paths": {
			"bench_root": bench_path,
			"apps_dir": apps_path,
			"sites_dir": f"{bench_path}/sites",
			"logs_dir": f"{bench_path}/logs",
			**site_paths,
		},
		"useful_commands": {
			"enter_bench": f"cd {bench_path}",
			"site_console": (
				f"cd {bench_path} && bench --site {site_name or '<site>'} console"
			),
			"site_shell": (
				f"cd {bench_path} && bench --site {site_name or '<site>'} mariadb"
			),
			"tail_log": f"tail -f {bench_path}/logs/web.log",
			"app_source": (
				f"cd {apps_path}/<app> && grep -rn '<symbol>' --include='*.py'"
			),
		},
		"do": [
			"Use bench --site <site> console for read-only inspection",
			"Run `git log` / `git diff` inside apps/<app> to see what changed",
			"Tail logs/web.log + logs/scheduler.log when reproducing a bug",
			"Use `bench --site <site> migrate --dry-run` before real migration",
		],
		"do_not": [
			"Edit app source files in-place (apps/<app>/...) — those are git-managed; the next deploy will overwrite changes",
			"Run `bench update` from the SSH session — use Press's Bench → Update flow so the deploy candidate is recorded",
			"Run `git pull` in apps/ — Press owns the deployment lifecycle; manual pulls cause drift the next deploy can't reconcile",
			"Modify site_config.json by hand for sensitive keys (db_password, encryption_key) — those are under Press's control",
			"Leave background processes running after disconnect (no nohup/screen for long jobs); use Press scheduled jobs instead",
		],
	}


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



@frappe.whitelist()
def rotate_code_server_password(bench_name):
	"""Rotate the Code Server password for this bench. Team-member access only."""
	_ensure_code_server_role_access(bench_name)
	name = frappe.db.exists(
		"Code Server", {"bench": bench_name, "status": ["!=", "Archived"]}
	)
	if not name:
		return {"error": "No active Code Server for this bench"}
	doc = frappe.get_doc("Code Server", name)
	return doc.rotate_password()


@frappe.whitelist()
def restart_code_server(bench_name):
	"""Restart the Code Server process for this bench.

	Idempotent recovery path: re-asserts is_code_server_enabled on the bench,
	queues an agent config update (so supervisor.conf regenerates with the
	code-server block), then starts the process with the current password.
	Team-member access only.
	"""
	_ensure_code_server_role_access(bench_name)
	import json as _json
	from press.agent import Agent
	from frappe.utils.password import get_decrypted_password

	cs_name = frappe.db.exists(
		"Code Server", {"bench": bench_name, "status": ["!=", "Archived"]}
	)
	if not cs_name:
		return {"error": "No active Code Server for this bench — click Launch Code Server first."}

	bench = frappe.get_doc("Bench", bench_name)
	# Always re-assert the flag in BOTH places (column + bench_config JSON) even
	# if they look set — the canonical cause of a broken CS is that one of them
	# drifted. Writing both then queueing update_bench_config guarantees the
	# agent regenerates supervisor.conf with the code-server block before we try
	# to start the process.
	config_json = _json.loads(bench.bench_config or "{}")
	config_json["is_code_server_enabled"] = True
	frappe.db.set_value(
		"Bench",
		bench_name,
		{"is_code_server_enabled": 1, "bench_config": _json.dumps(config_json, indent=4)},
		update_modified=False,
	)
	frappe.db.commit()
	bench = frappe.get_doc("Bench", bench_name)

	agent = Agent(bench.server, server_type="Server")
	# Always queue update_bench_config — this regenerates supervisor.conf with the
	# code-server block (required before start_code_server can find the program).
	# Agent Jobs on the same bench run sequentially, so start_code_server will see
	# the fresh supervisor when it runs.
	try:
		agent.update_bench_config(bench)
	except Exception as e:
		frappe.log_error(title="Restart Code Server: update_bench_config failed", message=str(e))
		return {"error": "Failed to queue config update — check Error Log"}

	password = get_decrypted_password("Code Server", cs_name, "password")
	try:
		agent.start_code_server(bench_name, cs_name, password)
		frappe.db.set_value("Code Server", cs_name, "status", "Pending", update_modified=False)
		frappe.db.commit()
	except Exception as e:
		frappe.log_error(title="Restart Code Server: start_code_server failed", message=str(e))
		return {"error": "Failed to queue start job — check Error Log"}

	return {"restarted": True, "status": "Pending"}


@frappe.whitelist()
def set_code_server_password_expiry_days(bench_name, days):
	"""Set the per-CS override for how many days the password stays valid.

	Pass 0 (or empty) to clear the override — the global Press Settings default applies.
	Team-member access only.
	"""
	_ensure_code_server_role_access(bench_name)
	try:
		days_int = int(days or 0)
	except (TypeError, ValueError):
		frappe.throw("days must be an integer")
	if days_int < 0:
		frappe.throw("days must be zero or positive")
	name = frappe.db.exists(
		"Code Server", {"bench": bench_name, "status": ["!=", "Archived"]}
	)
	if not name:
		return {"error": "No active Code Server for this bench"}
	frappe.db.set_value("Code Server", name, "password_expiry_days", days_int)
	frappe.db.commit()
	return {"updated": True, "password_expiry_days": days_int}
