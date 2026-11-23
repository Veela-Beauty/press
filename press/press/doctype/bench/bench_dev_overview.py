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

# Returned by every bench_ssh_* tool inside its data payload (so any agent on
# any MCP client sees it even if they ignore the envelope-level _warning).
# Reinforces ~/.claude/CLAUDE.md "Press Bench SSH Rule" — files edited inside
# the bench container at /home/frappe/frappe-bench/apps/<app>/... MUST be
# git committed + pushed before the SSH session ends. Press redeploys wipe
# uncommitted edits.
SSH_RULE_MUST_FOLLOW = (
	"RULE: any file you edit at /home/frappe/frappe-bench/apps/<app>/... "
	"MUST be git commit + push'd BEFORE you exit this SSH session. "
	"Press deploys rebuild the container from the registered Git repo; "
	"uncommitted edits are LOST on the next deploy. Preferred: use the "
	"Press MCP tool app_git_push (commits + pushes from inside the bench "
	"with audit trail). No 'TODO commit later' — if you edit, you push."
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
		"rule_must_follow": SSH_RULE_MUST_FOLLOW,
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


@frappe.whitelist()
def bench_ssh_register_key(
	public_key: str,
	label: str | None = None,
	make_default: bool = True,
) -> dict[str, Any]:
	"""Register the caller's SSH public key with Press (one-time, before
	bench_ssh_cert_generate can sign it).

	Press's bench_ssh_cert_generate signs the user's DEFAULT key. External
	agents (no dashboard session) need this tool to upload + default their
	pubkey in one shot. Stores against frappe.session.user (the token's
	owner).

	Args:
		public_key: full ssh-ed25519 / ssh-rsa / ecdsa-... public key string
			(the .pub file content, including the algorithm prefix)
		label: optional human-readable label
		make_default: if True (default), mark this key as the user's
			default — bench_ssh_cert_generate signs the default key.
			Pass False to keep an existing default in place.

	Returns:
		{name, label, is_default, already_registered}

	Idempotent: if the same key is already registered, returns the
	existing record. If make_default=True and another key was previously
	default, this also re-defaults to the registered key (so the next
	cert tool call signs THIS key, not the previous one).
	"""
	if not public_key or not isinstance(public_key, str):
		raise frappe.ValidationError("public_key must be a non-empty string")
	pk = public_key.strip()
	if not pk.split(" ", 1)[0] in (
		"ssh-ed25519", "ssh-rsa", "ecdsa-sha2-nistp256",
		"ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521",
	):
		raise frappe.ValidationError(
			"public_key must start with a supported algorithm "
			"(ssh-ed25519, ssh-rsa, ecdsa-sha2-*)"
		)
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
		key_name = existing.name
		already_registered = True
	else:
		# First time: insert. Frappe's User SSH Key controller handles
		# the is_default uniqueness — only one key per user can be default.
		doc = frappe.get_doc({
			"doctype": "User SSH Key",
			"user": frappe.session.user,
			"ssh_public_key": pk,
			"label": label or "mcp-issued",
			"is_default": 0,  # Set after insert via _make_default helper
		}).insert(ignore_permissions=True)
		key_name = doc.name
		already_registered = False

	if make_default:
		# Clear any other default for this user, then set ours
		frappe.db.sql(
			"UPDATE `tabUser SSH Key` SET is_default = 0 "
			"WHERE user = %s AND name != %s",
			(frappe.session.user, key_name),
		)
		frappe.db.set_value("User SSH Key", key_name, "is_default", 1)
		frappe.db.commit()
		final_default = True
	else:
		final_default = bool(
			frappe.db.get_value("User SSH Key", key_name, "is_default")
		)
		frappe.db.commit()

	return {
		"name": key_name,
		"label": label or (existing.label if existing else "mcp-issued"),
		"is_default": final_default,
		"already_registered": already_registered,
		"rule_must_follow": SSH_RULE_MUST_FOLLOW,
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
		"rule_must_follow": SSH_RULE_MUST_FOLLOW,
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
			# Verified live: SSH on port 22011 lands you DIRECTLY inside the
			# bench container as user `frappe` at /home/frappe. The bench
			# tree is at /home/frappe/frappe-bench. Two gotchas:
			# 1. PATH doesn't include /home/frappe/.local/bin for non-interactive
			#    SSH (no .bashrc loaded). Use absolute /home/frappe/.local/bin/bench
			#    OR `bash -lc 'bench ...'` to source profile.
			# 2. bench commands MUST be run from /home/frappe/frappe-bench (the
			#    bench dir), not /home/frappe.
			"interactive_shell": (
				f"# ssh -p {ssh_port} -i ~/.ssh/<key> frappe@{server_ip}\n"
				f"# (interactive shells DO load .bashrc — bench will be on PATH)"
			),
			"site_console": (
				f"ssh -p {ssh_port} -i ~/.ssh/<key> frappe@{server_ip} "
				f"\"cd {bench_path} && /home/frappe/.local/bin/bench "
				f"--site {site_name or '<site>'} console\""
			),
			"site_mariadb": (
				f"ssh -p {ssh_port} -i ~/.ssh/<key> frappe@{server_ip} "
				f"\"cd {bench_path} && /home/frappe/.local/bin/bench "
				f"--site {site_name or '<site>'} mariadb\""
			),
			"oneshot_sql": (
				f"ssh -p {ssh_port} -i ~/.ssh/<key> frappe@{server_ip} "
				f"\"cd {bench_path} && /home/frappe/.local/bin/bench "
				f"--site {site_name or '<site>'} mariadb <<< 'SELECT 1'\""
			),
			"tail_log": (
				f"ssh -p {ssh_port} -i ~/.ssh/<key> frappe@{server_ip} "
				f"\"tail -f {bench_path}/logs/web.log\""
			),
			"grep_app_source": (
				f"ssh -p {ssh_port} -i ~/.ssh/<key> frappe@{server_ip} "
				f"\"grep -rn '<symbol>' {apps_path}/<app>/ --include='*.py'\""
			),
			"_note": (
				"SSH on this port (22011) lands you INSIDE the bench container "
				"already — no docker exec step needed. cd /home/frappe/frappe-bench "
				"first, then use absolute /home/frappe/.local/bin/bench in non-"
				"interactive sessions (or open an interactive shell which loads "
				".bashrc and puts bench on PATH)."
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


@frappe.whitelist()
def bench_ssh_connect(
	bench_name: str,
	site_name: str | None = None,
) -> dict[str, Any]:
	"""One-call SSH bootstrap: instructions + freshly-minted cert + a
	ready-to-run ssh command with the LIVE port already filled in.

	Folds bench_ssh_instructions + bench_ssh_cert_generate into a single call
	so callers never have to chain two tools or hardcode the SSH port (which
	changes on every Press redeploy: ssh_port = 22000 + bench.port_offset, and
	a redeploy creates a new Bench instance with a new offset).

	Requires the caller to have already registered a pubkey via
	bench_ssh_register_key; if not, returns instructions only with cert=None
	and a needs_key flag so the caller knows to register first.

	Args:
		bench_name: Bench docname (e.g. "bench-0022-000037-press-f1")
		site_name: optional site name for site-specific after-login paths

	Returns:
		{server_ip, ssh_port, user, ready_command, certificate, cert_name,
		 cert_valid_until, needs_key, save_cert_to, instructions}
	"""
	instructions = bench_ssh_instructions(bench_name=bench_name, site_name=site_name)

	cert = None
	needs_key = not instructions.get("has_registered_key")
	if not needs_key:
		try:
			cert = generate_ssh_certificate(bench_name)
		except Exception as e:  # noqa: BLE001 — surface the reason, do not 500
			cert = {"error": str(e)}

	ssh_port = instructions["ssh_port"]
	server_ip = instructions["server_ip"]
	# Concrete command pointing at the canonical cert path the instructions
	# tell the user to save to. No placeholder — paste-and-run.
	ready_command = f"ssh -p {ssh_port} -i ~/.ssh/id_ed25519 frappe@{server_ip}"

	cert_body = None
	cert_name = None
	cert_valid_until = None
	if isinstance(cert, dict) and not cert.get("error"):
		cert_body = cert.get("certificate")
		cert_name = cert.get("cert_name")
		cert_valid_until = cert.get("valid_until")

	return {
		"server_ip": server_ip,
		"ssh_port": ssh_port,
		"user": "frappe",
		"ready_command": ready_command,
		"certificate": cert_body,
		"cert_name": cert_name,
		"cert_valid_until": cert_valid_until,
		"needs_key": needs_key,
		"save_cert_to": "~/.ssh/id_ed25519-cert.pub",
		"next_steps": (
			"Register a key first: bench_ssh_register_key(public_key=...)"
			if needs_key
			else (
				"Save 'certificate' to ~/.ssh/id_ed25519-cert.pub (next to your "
				"id_ed25519 private key), then run 'ready_command'. The port is "
				"the CURRENT one: re-call this tool after any redeploy instead of "
				"reusing an old port."
			)
			if cert_body
			else (
				"Port + command are ready. No fresh cert was returned inline; call "
				"bench_ssh_cert_generate(bench_name=...) to mint one, save it to "
				"~/.ssh/id_ed25519-cert.pub, then run 'ready_command'. The port is "
				"the CURRENT one: re-call this tool after any redeploy."
			)
		),
		"rule_must_follow": instructions.get("rule_must_follow"),
		"instructions": instructions,
	}
