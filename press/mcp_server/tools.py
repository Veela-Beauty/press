# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""MCP tool catalog — declarative mapping of tool name to whitelisted method.

Each entry:
	method: dotted-path to the underlying whitelisted Python function
	description: shown in tool list
	required_args: list of arg names the tool requires
	args_schema: JSON Schema fragment describing every arg the tool accepts.
		The dispatcher uses `required_args` for validation; `args_schema` is
		published to MCP clients (and the dashboard test-call form) so they
		know the exact canonical name + type of each parameter without
		guessing from natural language descriptions.
	risk: 'low' | 'medium' | 'high' — gates the dialog UX + verify_token

WHEN ADDING / REMOVING / RENAMING A TOOL HERE, ALSO UPDATE:
	dashboard/src/components/mcp/_tool_catalog.js  (frontend mirror used by
	the Issue Token dialog to show categories, risk badges, and search).
The two files MUST stay in sync; otherwise the new tool will not appear in
the scope picker and existing tokens with that scope cannot be issued via UI.

Every `required_args` entry MUST appear as a property in `args_schema` —
enforced at import time by `_assert_schema_covers_required_args()` below.
"""
from __future__ import annotations

# Reusable JSON Schema fragments for args that appear across many tools.
# Reference these via _S("site_name") etc. when building per-tool schemas to
# keep arg descriptions consistent and the file scannable.
_ARG_FRAGMENTS: dict[str, dict] = {
	"site_name": {"type": "string", "description": "Site name (FQDN), e.g. 'example.sandbox.mvpstorm.com'"},
	"site": {"type": "string", "description": "Site name (FQDN), e.g. 'example.sandbox.mvpstorm.com'"},
	"bench_name": {"type": "string", "description": "Bench docname, e.g. 'bench-0011-000187-press-f1'"},
	"release_group": {"type": "string", "description": "Release Group docname"},
	"target_bench": {"type": "string", "description": "Target Bench docname to host the cloned/moved site"},
	"target_release_group": {"type": "string", "description": "Destination Release Group docname"},
	"new_subdomain": {"type": "string", "description": "Subdomain for the new site (without the root domain)"},
	"new_title": {"type": "string", "description": "Display title for the new doc"},
	"name": {"type": "string", "description": "Primary docname for the target object"},
	"target_doctype": {"type": "string", "enum": ["Site", "Release Group", "Bench"],
		"description": "DocType the lock targets"},
	"target_name": {"type": "string", "description": "Docname the lock targets (matches target_doctype)"},
	"reason": {"type": "string", "description": "Free-text reason; appears in audit log"},
	"token_id": {"type": "string", "description": "Press MCP Token docname"},
	"app": {"type": "string", "description": "App name, e.g. 'erpnext', 'frappe', 'press'"},
	"app_name": {"type": "string", "description": "App name (lowercase, underscores)"},
	"app_title": {"type": "string", "description": "Human-readable app title"},
	"github_owner": {"type": "string", "description": "GitHub user or org name that will own the new repo"},
	"message": {"type": "string", "description": "Git commit message"},
	"code": {"type": "string", "description": "Python source to execute in the site's bench console"},
	"query": {"type": "string", "description": "SQL query string. Default is read-only — pass commit=true to allow writes."},
	"dn": {"type": "string", "description": "Deploy Candidate Build docname (sometimes called 'dcb name')"},
	"apps": {
		"type": "array",
		"items": {
			"type": "object",
			"properties": {
				"app": {"type": "string", "description": "App name, e.g. 'accubuild_core'"},
				"release": {"type": "string", "description": "App Release docname (from bench_deploy_information next_release)"},
				"hash": {"type": "string", "description": "Commit hash for that release (from bench_deploy_information releases[].hash)"},
			},
			"required": ["app", "release", "hash"],
		},
		"description": "List of {app, release, hash} dicts. Get release+hash from bench_deploy_information(name).apps[*].releases[0] or .next_release + matching releases[] entry. NOT a flat list of app names — each entry must be a dict.",
	},
	"domain": {"type": "string", "description": "Custom domain name, e.g. 'app.example.com'"},
	"config": {"type": "object", "description": "Dict of config keys → values to merge"},
	"key": {"type": "string", "description": "site_config.json key to set"},
	"value": {"description": "Value for the site_config.json key (string/number/bool — type matches the key)"},
	"relative_path": {"type": "string", "description": "Path relative to the site's public/files or private/files folder"},
	"content": {"type": "string", "description": "File content to write (UTF-8)"},
	"dependencies": {"type": "object", "description": "Dict of dependency name → version"},
	"release_name": {"type": "string", "description": "App Release docname"},
	"candidate_name": {"type": "string", "description": "Deploy Candidate docname"},
	"target_candidate": {"type": "string", "description": "Deploy Candidate to wait for the site to flip onto"},
	"repo": {"type": "string", "description": "GitHub repo in 'owner/name' form (must be in the allowlist)"},
	"branch": {"type": "string", "description": "Git branch or commit SHA"},
	"script_path": {"type": "string", "description": "Repo-relative path to the Python script to execute"},
	"public_key": {"type": "string", "description": "OpenSSH-format public key (e.g. 'ssh-ed25519 AAAA... user@host')"},
	"server": {"type": "string", "description": "App server docname, e.g. 'press-f1.sandbox.mvpstorm.com'"},
	"job_name": {"type": "string", "description": "Agent Job docname (10-char ID), e.g. 'jqc727far7'"},
	"app_source": {"type": "string", "description": "App Source docname (e.g. 'SRC-frappe_theme_switcher-001')"},
	"repository_url": {"type": "string", "description": "GitHub repository URL (https://github.com/owner/repo) or owner/repo shorthand"},
	"force": {"type": "boolean", "description": "Bypass safety checks (e.g. last_github_poll_failed flag)"},
	"team": {"type": "string", "description": "Team docname (defaults to current team)"},
	"limit": {"type": "integer", "minimum": 1, "maximum": 200, "description": "Max rows to return"},
	"source": {"type": "string", "description": "App Source docname to add to the group (e.g. 'SRC-erpnext-001')"},
	"title": {"type": "string", "description": "Release Group display title"},
	"version": {"type": "string", "description": "Frappe version, e.g. 'Version 15'"},
	"cluster": {"type": "string", "description": "Cluster docname, e.g. 'Default'"},
	"saas_app": {"type": "string", "description": "Saas App docname (optional; '' if none)"},
	"dc_name": {"type": "string", "description": "Deploy Candidate docname to redeploy from"},
	"new_apps": {
		"type": "array",
		"items": {
			"type": "object",
			"properties": {
				"name": {"type": "string", "description": "App name, e.g. 'erpnext'"},
				"source": {"type": "string", "description": "App Source docname for that app"},
			},
			"required": ["name", "source"],
		},
		"description": "Apps for the NEW Release Group: list of {name, source} dicts (note: 'name' here is the app name, not a release/hash).",
	},
}


def _schema(required: list[str], optional: dict | None = None) -> dict:
	"""Build a JSON Schema object for a tool from arg fragments.

	`required` lists arg names that must be present; their fragments come from
	_ARG_FRAGMENTS. `optional` is a {arg_name: schema_fragment_or_None} dict —
	pass None to reuse the shared fragment, or pass an inline dict for tool-specific
	args that don't appear elsewhere.
	"""
	props: dict[str, dict] = {}
	for arg in required:
		if arg not in _ARG_FRAGMENTS:
			raise KeyError(
				f"_schema: arg {arg!r} has no fragment in _ARG_FRAGMENTS — "
				f"add it there or pass an inline schema via optional"
			)
		props[arg] = _ARG_FRAGMENTS[arg]
	for arg, frag in (optional or {}).items():
		if frag is None:
			if arg not in _ARG_FRAGMENTS:
				raise KeyError(f"_schema: optional arg {arg!r} has no fragment — pass inline")
			props[arg] = _ARG_FRAGMENTS[arg]
		else:
			props[arg] = frag
	return {
		"type": "object",
		"properties": props,
		"required": list(required),
	}


# Tool name -> spec
TOOLS: dict[str, dict] = {
	# Clone (Obj 1)
	"clone_bench": {
		"method": "press.press.doctype.release_group.release_group_clone.clone_release_group",
		"description": "Clone a Release Group on the same server with the same apps",
		"required_args": ["release_group", "new_title"],
		"args_schema": _schema(
			["release_group", "new_title"],
			{"lifetime": {"type": "string", "enum": ["persistent", "sandbox"],
				"description": "How long the clone lives. 'persistent' = forever; 'sandbox' = 24h TTL."}},
		),
		"risk": "medium",
	},
	"clone_site": {
		"method": "press.press.doctype.site.site_clone.clone_site",
		"description": "Clone a Site onto a target bench (3 modes)",
		"required_args": ["site", "target_bench", "new_subdomain"],
		"args_schema": _schema(
			["site", "target_bench", "new_subdomain"],
			{
				"mode": {"type": "string", "enum": ["latest_backup", "fresh_backup", "empty"],
					"description": "Data source. 'latest_backup' (default) restores most recent offsite backup; 'fresh_backup' queues a new backup first; 'empty' installs apps only."},
				"plan": {"type": "string", "description": "Site Plan docname for the new site (defaults to source's plan)"},
			},
		),
		"risk": "medium",
	},
	# Move (Obj 2)
	"move_site_to_release_group": {
		"method": "press.api.site_move.move_to_release_group",
		"description": "Move a Site to a different Release Group",
		"required_args": ["site", "target_release_group"],
		"args_schema": _schema(["site", "target_release_group"]),
		"risk": "medium",
	},
	# Locks (Obj 3)
	"lock_acquire": {
		"method": "press.api.lock.acquire",
		"description": "Acquire an advisory lock on Site or Release Group",
		"required_args": ["target_doctype", "target_name", "reason"],
		"args_schema": _schema(
			["target_doctype", "target_name", "reason"],
			{
				"ttl_minutes": {"type": "integer", "minimum": 1, "maximum": 1440,
					"description": "Lock TTL in minutes (default 30, max 1440)"},
				"override": {"type": "boolean", "description": "Force-override an existing lock (use sparingly)"},
			},
		),
		"risk": "medium",
	},
	"lock_release": {
		"method": "press.api.lock.release",
		"description": "Release an advisory lock you hold",
		"required_args": ["target_doctype", "target_name"],
		"args_schema": _schema(["target_doctype", "target_name"]),
		"risk": "medium",
	},
	"lock_status": {
		"method": "press.api.lock.status",
		"description": "Inspect lock state of Site or Release Group",
		"required_args": ["target_doctype", "target_name"],
		"args_schema": _schema(["target_doctype", "target_name"]),
		"risk": "low",
	},
	# Read-only (4b additions)
	"list_release_groups": {
		"method": "press.api.bench.all",
		"description": "List Release Groups visible to the calling user",
		"required_args": [],
		"args_schema": _schema([]),
		"risk": "low",
	},
	"list_sites": {
		"method": "press.api.site.all",
		"description": "List Sites visible to the calling user. Note: this is the broad team-scoped list with status/tag filters only — does NOT accept a release_group arg. Use list_sites_on_release_group to filter by RG.",
		"required_args": [],
		"args_schema": _schema([]),
		"risk": "low",
	},
	"list_sites_on_release_group": {
		"method": "press.mcp_server.deploy_flow.list_sites_on_release_group",
		"description": "List sites belonging to a specific Release Group (team-scoped for non-System users). Use this when you want to know 'which sites would be touched by a bench rebuild of RG X'. Returns {name, status, bench, team, host_name, group} per site.",
		"required_args": ["release_group"],
		"args_schema": _schema(
			["release_group"],
			{
				"status": {
					"type": "string",
					"enum": ["Active", "Inactive", "Suspended", "Pending", "Broken", "Archived"],
					"description": "Optional status filter (default: all statuses)",
				},
			},
		),
		"risk": "low",
	},
	"bench_set_app_branch": {
		"method": "press.mcp_server.deploy_flow.bench_set_app_branch",
		"description": "Change the Git branch an App Source uses for a Release Group. Use BEFORE triggering a deploy candidate when you want to deploy a feature branch instead of whatever Press is currently pointed at. Args: release_group, app, branch. After this call, use release_group_create_deploy_candidate + deploy_candidate_schedule_build (or bench_deploy_and_wait). The branch must exist on the configured repository — no pre-validation here. Affects every RG that shares this App Source; for per-RG isolation, create a new App Source first via the Desk.",
		"required_args": ["release_group", "app", "branch"],
		"args_schema": _schema(["release_group", "app", "branch"]),
		"risk": "medium",
	},
	# Token self-management
	"list_my_tokens": {
		"method": "press.mcp_server.dashboard.list_my_tokens",
		"description": "List active MCP tokens for the calling user",
		"required_args": [],
		"args_schema": _schema([]),
		"risk": "low",
	},
	"revoke_my_token": {
		"method": "press.mcp_server.auth.revoke_token",
		"description": "Revoke an MCP token by docname",
		"required_args": ["token_id"],
		"args_schema": _schema(["token_id"]),
		"risk": "medium",
	},
	# Git ops
	"app_git_status": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_app_git_status",
		"description": "Get git branch/commit/dirty status for apps in a bench (per-site)",
		"required_args": ["bench_name"],
		"args_schema": _schema(["bench_name"],
			{"site_name": None}),
		"risk": "low",
	},
	"app_git_push": {
		"method": "press.press.doctype.bench.bench_dev_overview.push_app_to_github",
		"description": "Commit + push an app's working tree to GitHub from inside the bench container",
		"required_args": ["bench_name", "app", "message"],
		"args_schema": _schema(["bench_name", "app", "message"]),
		"risk": "high",
	},
	"app_create_locally": {
		"method": "press.press.doctype.bench.bench_app_management.create_app_locally",
		"description": "Run `bench new-app` inside a bench container",
		"required_args": ["bench_name", "app_name", "app_title"],
		"args_schema": _schema(["bench_name", "app_name", "app_title"]),
		"risk": "medium",
	},
	"app_init_github": {
		"method": "press.press.doctype.bench.bench_app_management.init_github_for_app",
		"description": "Create a GitHub repo for an existing local app and register it in Press",
		"required_args": ["bench_name", "app_name", "github_owner"],
		"args_schema": _schema(["bench_name", "app_name", "github_owner"]),
		"risk": "medium",
	},
	# Console / shell (run code inside bench container)
	"site_run_python": {
		"method": "press.press.doctype.bench.bench_dev_overview.run_python_on_site",
		"description": "Run a Python snippet on a site in the bench console (full power, system-manager only)",
		"required_args": ["site_name", "code"],
		"args_schema": _schema(["site_name", "code"]),
		"risk": "high",
	},
	"site_run_sql": {
		"method": "press.press.doctype.bench.bench_dev_overview.run_sql_on_site",
		"description": "Run SQL on the site database (default read-only; commit=true for writes)",
		"required_args": ["site_name", "query"],
		"args_schema": _schema(["site_name", "query"],
			{"commit": {"type": "boolean", "description": "Allow writes (INSERT/UPDATE/DELETE/DDL). Default false (read-only)."}}),
		"risk": "high",
	},
	# Logs + diagnostics
	"bench_recent_logs": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_recent_logs",
		"description": "Tail recent bench logs (frappe.log, scheduler.log, error.log, etc.)",
		"required_args": ["bench_name"],
		"args_schema": _schema(["bench_name"],
			{
				"log_type": {"type": "string", "description": "Log file name, e.g. 'frappe.log', 'scheduler.log', 'error.log'"},
				"limit": {"type": "integer", "minimum": 1, "maximum": 5000,
					"description": "Number of trailing lines to return (default 200, max 5000)"},
			}),
		"risk": "low",
	},
	"site_db_processlist": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_db_processlist",
		"description": "MariaDB SHOW PROCESSLIST for the site DB",
		"required_args": ["site_name"],
		"args_schema": _schema(["site_name"]),
		"risk": "low",
	},
	"deploy_failure_details": {
		"method": "press.press.doctype.deploy_candidate_build.build_diagnostics.get_failure_details",
		"description": "Inspect a failed Deploy Candidate Build (failed step, stage, output)",
		"required_args": ["dn"],
		"args_schema": _schema(["dn"]),
		"risk": "low",
	},
	# Bench / Release Group lifecycle
	"bench_deploy": {
		"method": "press.api.bench.deploy",
		"description": "Trigger a deploy for a Release Group. Args: name (Release Group docname, e.g. 'bench-0005'); apps (list of DICTS, NOT strings — each item {app, release, hash}). Get release+hash from bench_deploy_information(name).apps[*].releases[0]. Returns the Deploy Candidate docname — pass it to wait_for_bench_flip's target_candidate.",
		"required_args": ["name", "apps"],
		"args_schema": _schema(["name", "apps"]),
		"risk": "medium",
	},
	"bench_deploy_information": {
		"method": "press.api.bench.deploy_information",
		"description": "Get deploy candidate / pending updates info for a Release Group",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "low",
	},
	"bench_restart": {
		"method": "press.api.bench.restart",
		"description": "Restart a Bench (gunicorn + workers)",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "medium",
	},
	"bench_update": {
		"method": "press.api.bench.update",
		"description": "Update a Bench to the latest deploy",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "high",
	},
	# Site lifecycle
	"site_migrate": {
		"method": "press.api.site.migrate",
		"description": "Run `bench --site X migrate` on the site",
		"required_args": ["name"],
		"args_schema": _schema(["name"],
			{"skip_failing_patches": {"type": "boolean",
				"description": "Skip patches that fail during migration (not recommended)"}}),
		"risk": "medium",
	},
	"site_backup": {
		"method": "press.api.site.backup",
		"description": "Trigger a site backup. Note: this endpoint does NOT take an `offsite` flag — site backups via this API are always local + offsite per the team's configured backup schedule. For an explicit offsite-only backup, use Site.backup() directly via console.",
		"required_args": ["name"],
		"args_schema": _schema(["name"],
			{
				"with_files": {"type": "boolean", "description": "Include public + private files in the backup"},
			}),
		"risk": "medium",
	},
	"site_install_app": {
		"method": "press.api.site.install_app",
		"description": "Install an app on a site",
		"required_args": ["name", "app"],
		"args_schema": _schema(["name", "app"]),
		"risk": "medium",
	},
	"site_uninstall_app": {
		"method": "press.api.site.uninstall_app",
		"description": "Uninstall an app from a site",
		"required_args": ["name", "app"],
		"args_schema": _schema(["name", "app"]),
		"risk": "high",
	},
	"site_activate": {
		"method": "press.api.site.activate",
		"description": "Activate a previously deactivated site",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "medium",
	},
	"site_deactivate": {
		"method": "press.api.site.deactivate",
		"description": "Deactivate a site (puts it in maintenance mode)",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "high",
	},
	"site_update": {
		"method": "press.mcp_server.deploy_flow.site_update_with_hint",
		"description": "Update a site to the latest bench deploy. Wraps press.api.site.update with pre-flight checks. If no newer Deploy Candidate exists yet, returns {ok:false, reason:'no_destination_candidate', hint:'...'} instead of throwing the misleading 'Could not find suitable Destination Bench' error. Args: name (site FQDN). Optional: skip_failing_patches (bool).",
		"required_args": ["name"],
		"args_schema": _schema(["name"], {
			"skip_failing_patches": {"type": "boolean",
				"description": "Skip failing patches during migrate (default false)"},
		}),
		"risk": "high",
	},
	# SSH access (cert generation lets agents SSH into bench container)
	"bench_ssh_cert_get": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_ssh_certificate",
		"description": "Get the existing SSH certificate for a bench (returns None if not yet generated)",
		"required_args": ["bench_name"],
		"args_schema": _schema(["bench_name"]),
		"risk": "medium",
	},
	"bench_ssh_cert_generate": {
		"method": "press.press.doctype.bench.bench_dev_overview.generate_ssh_certificate",
		"description": "Generate an SSH certificate for a bench so the agent can SSH into the bench container",
		"required_args": ["bench_name"],
		"args_schema": _schema(["bench_name"]),
		"risk": "high",
	},
	"bench_dev_info": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_bench_dev_info",
		"description": "Get bench dev connection info: server IP, SSH port, is_development_bench flag",
		"required_args": ["bench_name"],
		"args_schema": _schema(["bench_name"]),
		"risk": "low",
	},
	# Site config (medium-risk — structured replacement for site_run_python config edits)
	"site_config_get": {
		"method": "press.mcp_server.file_ops.site_config_get",
		"description": "Read site_config.json keys (sensitive keys redacted)",
		"required_args": ["site_name"],
		"args_schema": _schema(["site_name"]),
		"risk": "medium",
	},
	"site_config_set": {
		"method": "press.mcp_server.file_ops.site_config_set",
		"description": "Set a single site_config.json key (sensitive keys forbidden)",
		"required_args": ["site_name", "key", "value"],
		"args_schema": _schema(["site_name", "key", "value"]),
		"risk": "medium",
	},
	# File ops (medium-risk — constrained to public/private folders)
	"site_file_read": {
		"method": "press.mcp_server.file_ops.site_file_read",
		"description": "Read a file from the site's public/files/ or private/files/ folder",
		"required_args": ["site_name", "relative_path"],
		"args_schema": _schema(["site_name", "relative_path"]),
		"risk": "medium",
	},
	"site_file_write": {
		"method": "press.mcp_server.file_ops.site_file_write",
		"description": "Write a file to the site's public/files/ or private/files/ folder",
		"required_args": ["site_name", "relative_path", "content"],
		"args_schema": _schema(["site_name", "relative_path", "content"]),
		"risk": "medium",
	},
	# Domains (Obj 8)
	"site_domains_list": {
		"method": "press.api.site.domains",
		"description": "List domains attached to a site",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "low",
	},
	"site_add_domain": {
		"method": "press.api.site.add_domain",
		"description": "Attach a custom domain to a site",
		"required_args": ["name", "domain"],
		"args_schema": _schema(["name", "domain"]),
		"risk": "medium",
	},
	"site_remove_domain": {
		"method": "press.api.site.remove_domain",
		"description": "Detach a custom domain from a site",
		"required_args": ["name", "domain"],
		"args_schema": _schema(["name", "domain"]),
		"risk": "medium",
	},
	"site_set_host_name": {
		"method": "press.api.site.set_host_name",
		"description": "Set the primary domain (host name) for a site",
		"required_args": ["name", "domain"],
		"args_schema": _schema(["name", "domain"]),
		"risk": "medium",
	},
	"site_update_config_bulk": {
		"method": "press.api.site.update_config",
		"description": "Bulk-update site_config.json keys (passes through Press's update_config — uses Press internal allow-list)",
		"required_args": ["name", "config"],
		"args_schema": _schema(["name", "config"]),
		"risk": "medium",
	},
	# Bench config (Obj 8)
	"bench_update_config": {
		"method": "press.api.bench.update_config",
		"description": "Bulk-update bench common_site_config keys",
		"required_args": ["name", "config"],
		"args_schema": _schema(["name", "config"]),
		"risk": "medium",
	},
	"bench_update_dependencies": {
		"method": "press.api.bench.update_dependencies",
		"description": "Update bench dependency versions (Python/Node/etc) — triggers rebuild",
		"required_args": ["name", "dependencies"],
		"args_schema": _schema(["name", "dependencies"]),
		"risk": "high",
	},
	# Deploy / release flow (Obj 10)
	"app_release_approve": {
		"method": "press.mcp_server.deploy_flow.app_release_approve",
		"description": "Approve a Draft App Release for inclusion in Deploy Candidates",
		"required_args": ["release_name"],
		"args_schema": _schema(["release_name"]),
		"risk": "medium",
	},
	"app_source_fetch_latest": {
		"method": "press.mcp_server.deploy_flow.app_source_fetch_latest",
		"description": "Poll an App Source's upstream Git remote and create a Draft App Release for any new commit on its branch. Equivalent to the dashboard's 'Fetch Latest' button. Pass either app_source explicitly, OR app + release_group to walk the link. Returns the new release docname or marks no_new_release=true when upstream has no new commits. Pass force=true to retry after last_github_poll_failed.",
		"required_args": [],
		"args_schema": _schema([], {"app_source": None, "app": None, "release_group": None, "force": None}),
		"risk": "low",
	},
	"list_pending_releases": {
		"method": "press.mcp_server.deploy_flow.list_pending_releases",
		"description": "List Draft App Releases waiting for approval. Filter by app_source, OR app + release_group, OR app alone. Returns count + array of {name, app, source, hash, status, creation}.",
		"required_args": [],
		"args_schema": _schema([], {"app": None, "release_group": None, "app_source": None, "limit": None}),
		"risk": "low",
	},
	"register_existing_app": {
		"method": "press.mcp_server.deploy_flow.register_existing_app",
		"description": "Register an EXISTING GitHub repository as a new App Source. Different from app_create_locally (which scaffolds a NEW app). Use when a teammate or external maintainer pushed an app to GitHub and you need Press to track it. Args: repository_url (https URL or owner/repo), branch, app_name (must match hooks.py). Optional: app_title, versions, team, github_installation_id. PRIVATE repos need a GitHub App installation or the build cannot clone them; it is auto-resolved from an existing App Source with the same repository_owner, and registration now FAILS LOUDLY when it cannot be resolved instead of leaving an App Source that dies later at git clone. Returns app_source docname.",
		"required_args": ["repository_url", "branch", "app_name"],
		"args_schema": _schema(["repository_url", "branch", "app_name"], {"app_title": None, "versions": {"type": "array", "items": {"type": "string"}, "description": "Frappe Versions to tag, e.g. ['Version 15']. Auto-resolved from a version-NN branch or the latest on record if omitted."}, "team": None, "github_installation_id": {"type": "string", "description": "GitHub App installation id used to mint clone tokens. Auto-resolved from an existing App Source with the same repository_owner when omitted. Required for a private repo when none can be resolved."}}),
		"risk": "medium",
	},
	"release_group_create_deploy_candidate": {
		"method": "press.mcp_server.deploy_flow.release_group_create_deploy_candidate",
		"description": "Create a new Deploy Candidate for a Release Group",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "medium",
	},
	"deploy_candidate_schedule_build": {
		"method": "press.mcp_server.deploy_flow.deploy_candidate_schedule_build",
		"description": "Schedule build + deploy for a Deploy Candidate; returns the build job name",
		"required_args": ["candidate_name"],
		"args_schema": _schema(["candidate_name"]),
		"risk": "medium",
	},
	"deploy_candidate_status": {
		"method": "press.mcp_server.deploy_flow.deploy_candidate_status",
		"description": "Status of a Deploy Candidate Build OR a Deploy Candidate. `name` may be either; response contains a `kind: build|candidate` discriminator.",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "low",
	},
	"site_schedule_update": {
		"method": "press.mcp_server.deploy_flow.site_schedule_update",
		"description": "Schedule a Site Update (migrate to latest bench in same Release Group)",
		"required_args": ["site_name"],
		"args_schema": _schema(["site_name"]),
		"risk": "medium",
	},
	"site_status": {
		"method": "press.mcp_server.deploy_flow.site_status",
		"description": "Current site bench + status + recent agent jobs (polling primitive)",
		"required_args": ["site_name"],
		"args_schema": _schema(["site_name"]),
		"risk": "low",
	},
	"agent_job_list": {
		"method": "press.mcp_server.deploy_flow.agent_job_list",
		"description": "List recent Agent Jobs filtered by site/status/window",
		"required_args": [],
		"args_schema": _schema([],
			{
				"site": {"type": "string", "description": "Site name (FQDN) — filter to jobs for this site only"},
				"status": {"type": "string", "enum": ["Pending", "Running", "Success", "Failure", "Undelivered"],
					"description": "Filter by job status"},
				"since_minutes": {"type": "integer", "minimum": 1, "maximum": 10080,
					"description": "Window in minutes to look back (default 1440 = 24h, max 10080 = 7d)"},
				"limit": {"type": "integer", "minimum": 1, "maximum": 200,
					"description": "Max rows to return (default 50)"},
			}),
		"risk": "low",
	},
	"wait_for_bench_flip": {
		"method": "press.mcp_server.deploy_flow.wait_for_bench_flip",
		"description": "Single-shot poll (NOT a blocking wait — call it again to re-poll). Returns {status: 'flipped'|'pending'|'no_build'|'flip_not_triggered'|'flip_failed', current_bench, current_candidate, target_candidate, site, hint?}. Args: site_name (site FQDN, NOT the bench docname); target_candidate (Deploy Candidate docname returned by bench_deploy). NO timeout arg — caller decides cadence. SAFETY GATES: 'no_build' = the candidate has no Deploy Candidate Build, STOP polling. 'flip_not_triggered' = build succeeded but no Update Site Migrate job exists, STOP polling and call site_update_and_wait. 'flip_failed' = the Update Site Migrate FAILED and was rolled back; call agent_job_traceback on the failed_migrate_job to see the error. Returned hint tells you exactly what to do next.",
		"required_args": ["site_name", "target_candidate"],
		"args_schema": _schema(["site_name", "target_candidate"]),
		"risk": "low",
	},
	"bench_deploy_and_wait": {
		"method": "press.mcp_server.deploy_flow.bench_deploy_and_wait",
		"description": "ONE-SHOT deploy + wait. Triggers bench_deploy and BLOCKS until the site flips to the new Deploy Candidate, or until max_wait_seconds expires (default 25 min). Use this instead of bench_deploy + a manual wait_for_bench_flip loop. Returns {candidate, status: 'flipped'|'timeout', elapsed_seconds, ...}. Args: name (Release Group docname); apps (list of {app, release, hash} dicts from bench_deploy_information); site_name (one site on the RG to watch — multiple sites can be on the RG but this only waits for the named one).",
		"required_args": ["name", "apps", "site_name"],
		"args_schema": _schema(
			["name", "apps", "site_name"],
			{
				"max_wait_seconds": {
					"type": "integer",
					"minimum": 30,
					"maximum": 1700,
					"description": "Hard cap on the wait (default 1500 = 25 min; max 1700 to stay under Press's 1800s gunicorn timeout)",
				},
				"poll_interval_seconds": {
					"type": "integer",
					"minimum": 5,
					"maximum": 300,
					"description": "How often to re-check (default 30s, min 5s)",
				},
			},
		),
		"risk": "medium",
	},
	"host_memory_pressure": {
		"method": "press.mcp_server.deploy_flow.host_memory_pressure",
		"description": "Snapshot of memory pressure on an app server (SSH-based, no Prometheus needed). Verdict 'ok' / 'elevated' / 'critical' / 'unknown' + memory_total_mb + memory_available_mb + swap_used_pct + recent OOM-kills + actionable hint. Results CACHED for 60s per server — repeated polls return cached data in <100ms (look at _cached:true in the response). Pass force_refresh=true to bypass cache. Use BEFORE memory-heavy ops, FIRST when multiple sites on a server 500. Shipped 2026-05-23 after press-f1 OOM incident.",
		"required_args": ["server"],
		"args_schema": _schema(["server"], {
			"force_refresh": {"type": "boolean", "description": "Bypass 60s cache and SSH fresh"},
		}),
		"risk": "low",
	},
	"agent_health": {
		"method": "press.mcp_server.deploy_flow.agent_health",
		"description": "Diagnose whether an app server's agent is healthy/slow/stuck/no_activity from Press-side Agent Job records. Use BEFORE recommending an agent restart — restarting a busy worker mid-migrate can corrupt the live DB. Verdict 'slow' = worker is on a long job, DO NOT restart. Verdict 'stuck' = Undelivered jobs piling up with no recent activity, investigate. Returns {verdict, reason, recent_jobs, last_success_seconds_ago, running_jobs, undelivered_jobs}. Args: server (app server docname); lookback_minutes (default 10, max 60).",
		"required_args": ["server"],
		"args_schema": _schema(
			["server"],
			{
				"lookback_minutes": {
					"type": "integer",
					"minimum": 1,
					"maximum": 60,
					"description": "Window in minutes to consider for activity (default 10, max 60)",
				},
			},
		),
		"risk": "low",
	},
	"agent_job_traceback": {
		"method": "press.mcp_server.deploy_flow.agent_job_traceback",
		"description": "One-shot diagnostic: returns {status, job_type, site, output_tail, traceback_tail, age_seconds} for an Agent Job. Use this whenever a job lands in Failure/Pending/Undelivered for >2 min and you need to see the actual error before deciding to restart anything. Replaces the 4-roundtrip ssh+console+get_doc dance.",
		"required_args": ["job_name"],
		"args_schema": _schema(
			["job_name"],
			{
				"output_chars": {
					"type": "integer",
					"minimum": 500,
					"maximum": 20000,
					"description": "Chars of output + traceback tail to return (default 4000, max 20000)",
				},
			},
		),
		"risk": "low",
	},
	"mint_dashboard_login_url": {
		"method": "press.mcp_server.deploy_flow.mint_dashboard_login_url",
		"description": "Mint a one-shot ?sid= URL that logs the browser in as the MCP token's user on the Press dashboard. Designed for Playwright / E2E tests — no password typing, no password rotation. Default redirect is /dashboard; pass redirect_to for any other path. The login is audit-logged.",
		"required_args": [],
		"args_schema": _schema(
			[],
			{
				"redirect_to": {
					"type": "string",
					"description": "Dashboard path to land on (default '/dashboard'). Examples: '/dashboard/devtools/mcp', '/dashboard/sites/<site>/overview'",
				},
			},
		),
		"risk": "medium",
	},
	"bench_provision_progress": {
		"method": "press.mcp_server.deploy_flow.bench_provision_progress",
		"description": "Aggregate progress for a bench going through Press's provision chain (Build → New Bench → Setup Bench → Site Migrate → Ready). Replaces the 'is the filesystem populated yet?' polling pattern. Returns {bench, candidate, bench_status, stage, stage_label, elapsed_seconds, chain[], dashboard_url}. Stage is one of: queued | build | new_bench | setup_bench | site_migrate | ready | failed | archived — each with a human label. Poll this every 10s instead of checking the filesystem; it tells you WHICH phase is running so you know the expected duration.",
		"required_args": ["bench_name"],
		"args_schema": _schema(["bench_name"]),
		"risk": "low",
	},
	"agent_job_progress": {
		"method": "press.mcp_server.deploy_flow.agent_job_progress",
		"description": "LIVE in-flight progress for an Agent Job — Cursor-style streaming. Returns {status, current_step, steps[], steps_summary, output_tail, dashboard_url}. Each step has its own status + output_tail + duration. Mirrors the dashboard's /dashboard/sites/<site>/jobs/<job> page. Call this in a loop (every 3-10s) while a deploy/migrate is in-flight to see exactly which step is running and what it's printing. Use agent_job_traceback for post-mortem on Failure rows; use THIS for live watching.",
		"required_args": ["job_name"],
		"args_schema": _schema(
			["job_name"],
			{
				"step_output_chars": {
					"type": "integer",
					"minimum": 200,
					"maximum": 5000,
					"description": "Chars of each step's output tail (default 1500, max 5000 — keeps response under cap)",
				},
				"job_output_chars": {
					"type": "integer",
					"minimum": 500,
					"maximum": 20000,
					"description": "Chars of the parent job's output/traceback tail (default 4000, max 20000)",
				},
			},
		),
		"risk": "low",
	},
	"site_update_and_wait": {
		"method": "press.mcp_server.deploy_flow.site_update_and_wait",
		"description": "ONE-SHOT site_update + wait. Triggers Site Update Migrate and BLOCKS until the site flips onto target_candidate or max_wait_seconds expires. Use AFTER bench_deploy_and_wait reports build Success but the site still hasn't flipped (standalone Press doesn't auto-flip — each site needs an explicit site_update). Returns {site, status: 'flipped'|'timeout', site_update_job, elapsed_seconds, current_bench, current_candidate}. Args: site_name (site FQDN); target_candidate (Deploy Candidate the site should end up on).",
		"required_args": ["site_name", "target_candidate"],
		"args_schema": _schema(
			["site_name", "target_candidate"],
			{
				"skip_failing_patches": {
					"type": "boolean",
					"description": "Pass through to schedule_update; rarely needed (default false)",
				},
				"skip_backups": {
					"type": "boolean",
					"description": "Pass through to schedule_update; speeds up dev flips (default false)",
				},
				"max_wait_seconds": {
					"type": "integer",
					"minimum": 30,
					"maximum": 1700,
					"description": "Hard cap on the wait (default 1500 = 25 min; max 1700 to stay under Press's 1800s gunicorn timeout)",
				},
				"poll_interval_seconds": {
					"type": "integer",
					"minimum": 5,
					"maximum": 300,
					"description": "How often to re-check (default 30s, min 5s)",
				},
			},
		),
		"risk": "medium",
	},
	"bench_run_repo_script": {
		"method": "press.mcp_server.script_runner.bench_run_repo_script",
		"description": "Fetch a Python script from an allowlisted GitHub repo and run it in a bench (high-risk; gated)",
		"required_args": ["bench_name", "repo", "branch", "script_path"],
		"args_schema": _schema(["bench_name", "repo", "branch", "script_path"]),
		"risk": "high",
	},
	"audit_verify_chain": {
		"method": "press.mcp_server.audit.verify_chain",
		"description": "System-User-only: walk the MCP Call Log hash chain and report any tampering/missing rows",
		"required_args": [],
		"args_schema": _schema([]),
		"risk": "low",
	},
	# Source-code reads — agents need to inspect app source for bug investigation
	# (e.g. read erpnext/.../general_ledger.py before proposing a fix). Read-only,
	# path-validated to stay under apps/<app>/, 1 MB cap per file.
	"bench_read_app_file": {
		"method": "press.press.doctype.bench.bench_dev_overview.bench_read_app_file",
		"description": "Read a source file from an app installed in the bench (e.g. erpnext/accounts/report/general_ledger/general_ledger.py). Read-only, 1 MB cap.",
		"required_args": ["bench_name", "app", "relative_path"],
		"args_schema": _schema(["bench_name", "app", "relative_path"]),
		"risk": "low",
	},
	"bench_list_app_files": {
		"method": "press.press.doctype.bench.bench_dev_overview.bench_list_app_files",
		"description": "List files under apps/<app>/<relative_path>/ in the bench container. Optional glob pattern. Capped at 200 entries.",
		"required_args": ["bench_name", "app"],
		"args_schema": _schema(["bench_name", "app"],
			{
				"relative_path": None,
				"pattern": {"type": "string", "description": "Optional glob pattern, e.g. '*.py'"},
			}),
		"risk": "low",
	},
	"bench_ssh_connect": {
		"method": "press.press.doctype.bench.bench_dev_overview.bench_ssh_connect",
		"description": "One call: SSH instructions + freshly-minted cert + a ready-to-run ssh command with the LIVE port (which changes on every redeploy). Re-call after a redeploy instead of reusing an old port.",
		"required_args": ["bench_name"],
		"args_schema": _schema(["bench_name"]),
		"risk": "medium",
	},
	"bench_ssh_instructions": {
		"method": "press.press.doctype.bench.bench_dev_overview.bench_ssh_instructions",
		"description": "Get SSH connection instructions for a bench (real port, paths, do/don't, prerequisite). Does NOT grant access — see bench_ssh_register_key + bench_ssh_cert_generate for that.",
		"required_args": ["bench_name"],
		"args_schema": _schema(["bench_name"]),
		"risk": "low",
	},
	"bench_ssh_register_key": {
		"method": "press.press.doctype.bench.bench_dev_overview.bench_ssh_register_key",
		"description": "Register your SSH public key with Press so bench_ssh_cert_generate can sign it. One-time setup; idempotent on re-call.",
		"required_args": ["public_key"],
		"args_schema": _schema(["public_key"]),
		"risk": "medium",
	},
	# ── Bench (Release Group) composition + lifecycle ──────────────────────
	# Full bench-control surface so an agent never has to fall back to the
	# Desk for add/remove app, switch source, rename, redeploy, archive,
	# rebuild, or create-fresh. Backed by press.api.bench.* via bench_ops.py.
	"release_group_add_app": {
		"method": "press.mcp_server.bench_ops.release_group_add_app",
		"description": "Add an app to a Release Group (bench). 'source' is an App Source docname (create one first with register_existing_app if the repo isn't registered). After this, trigger release_group_create_deploy_candidate + deploy to apply. To SWITCH an app's repo: add the new source, then release_group_remove_app the old app.",
		"required_args": ["name", "source", "app"],
		"args_schema": _schema(["name", "source", "app"]),
		"risk": "medium",
	},
	"release_group_remove_app": {
		"method": "press.mcp_server.bench_ops.release_group_remove_app",
		"description": "Remove an app from a Release Group (bench). The app stays on running benches until the next deploy — trigger release_group_create_deploy_candidate + deploy to drop it. Cannot remove 'frappe'. This is the tool to use instead of the Desk's 'Remove app' action.",
		"required_args": ["name", "app"],
		"args_schema": _schema(["name", "app"]),
		"risk": "high",
	},
	"release_group_list_branches": {
		"method": "press.mcp_server.bench_ops.release_group_list_branches",
		"description": "List git branches available for an app in a Release Group (from the configured GitHub repo). Use before bench_set_app_branch to discover valid branch names.",
		"required_args": ["name", "app"],
		"args_schema": _schema(["name", "app"]),
		"risk": "low",
	},
	"release_group_versions": {
		"method": "press.mcp_server.bench_ops.release_group_versions",
		"description": "List the deployed benches (versions) of a Release Group plus the sites on each. Use to see what would be touched by a rebuild/deploy and which bench a site currently runs on.",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "low",
	},
	"release_group_installable_apps": {
		"method": "press.mcp_server.bench_ops.release_group_installable_apps",
		"description": "List apps that can be added to a Release Group (available App Sources for the team/version). Use to find the 'source' value for release_group_add_app.",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "low",
	},
	"release_group_rename": {
		"method": "press.mcp_server.bench_ops.release_group_rename",
		"description": "Rename a Release Group (changes its display title only, not the docname).",
		"required_args": ["name", "title"],
		"args_schema": _schema(["name", "title"]),
		"risk": "medium",
	},
	"release_group_redeploy": {
		"method": "press.mcp_server.bench_ops.release_group_redeploy",
		"description": "Redeploy a Release Group from an existing Deploy Candidate (dc_name) — rebuilds without creating a new candidate. Get dc_name from deploy_candidate_status or bench_deploy_information. Returns the new candidate name.",
		"required_args": ["name", "dc_name"],
		"args_schema": _schema(["name", "dc_name"]),
		"risk": "medium",
	},
	"release_group_archive": {
		"method": "press.mcp_server.bench_ops.release_group_archive",
		"description": "DESTRUCTIVE: archive a Release Group — archives ALL its active benches and disables the group (title suffixed '.archived'). Sites must already be moved/archived. High-risk; requires a risky-enabled token.",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "high",
	},
	"bench_rebuild_assets": {
		"method": "press.mcp_server.bench_ops.bench_rebuild_assets",
		"description": "Rebuild a Bench's assets via the supported Press agent job (NOT a raw in-container 'bench build', which desyncs the edge asset snapshot). 'name' is a Bench docname (from release_group_versions), not a Release Group. High-risk: rebuilds assets for the bench.",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "high",
	},
	"release_group_create": {
		"method": "press.mcp_server.bench_ops.release_group_create",
		"description": "Create a fresh Release Group (bench). 'new_apps' is a list of {name, source} dicts (name = app name, source = App Source docname); must include frappe. 'server' optional ('' lets Press auto-pick). Returns the new Release Group docname. Use clone_bench instead if you want a copy of an existing group.",
		"required_args": ["title", "version", "new_apps", "cluster"],
		"args_schema": _schema(
			["title", "version", "new_apps", "cluster"],
			{"server": None, "saas_app": None},
		),
		"risk": "medium",
	},
}


def _assert_schema_covers_required_args() -> None:
	"""Import-time consistency check: every required_arg must appear in args_schema.

	Catches mismatches at server start instead of when a client first calls the
	tool. Without this check, a tool whose `required_args` list grew but whose
	`args_schema` didn't update would publish a misleading schema to clients.
	"""
	for tool_name, spec in TOOLS.items():
		required = spec.get("required_args", [])
		schema = spec.get("args_schema", {})
		props = schema.get("properties", {})
		missing = [a for a in required if a not in props]
		if missing:
			raise RuntimeError(
				f"tool {tool_name!r}: required_args {missing!r} are not declared "
				f"in args_schema.properties (keys: {sorted(props.keys())}). "
				f"Add them to args_schema or remove from required_args."
			)


_assert_schema_covers_required_args()


def get_tool_spec(tool_name: str) -> dict | None:
	return TOOLS.get(tool_name)


def list_tool_names() -> list[str]:
	return sorted(TOOLS.keys())


def get_tool_risk(tool_name: str) -> str:
	"""Return 'low', 'medium', or 'high'. Defaults to 'medium' for unclassified."""
	spec = TOOLS.get(tool_name)
	if not spec:
		return "high"  # unknown tool → fail-closed
	return spec.get("risk", "medium")


def list_risky_tools() -> list[str]:
	"""All tools classified as 'high' risk."""
	return sorted(name for name, spec in TOOLS.items() if spec.get("risk") == "high")
