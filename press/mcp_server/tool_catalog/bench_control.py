# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Catalog part: app source reads, release group composition and lifecycle, and site provisioning. Merged into press/mcp_server/tools.py TOOLS (split 0.7.54)."""

from __future__ import annotations

from press.mcp_server.tool_catalog._schema import _schema

BENCH_CONTROL_TOOLS: dict[str, dict] = {
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
	# Site provisioning (site_ops) — the two gaps in the site_* family.
	"site_create": {
		"method": "press.mcp_server.site_ops.site_create",
		"description": "Create a site on a specific Release Group. 'new_subdomain' is the subdomain ONLY (no dots) — Press appends the root domain. Pass 'database' (a Remote File docname) to restore a backup AT CREATION instead of creating empty then restoring; upload the backup first via POST press.api.site.upload_backup_file with a sid from mint_dashboard_login_url. 'apps' is a list of app NAME strings and must include frappe.",
		"required_args": ["new_subdomain", "release_group", "plan"],
		"args_schema": _schema(
			["new_subdomain", "release_group", "plan"],
			{
				"apps": {
					"type": "array",
					"items": {"type": "string"},
					"description": "App names to install, e.g. ['frappe','erpnext']. Defaults to ['frappe'].",
				},
				"cluster": None,
				"server": None,
				"root_domain": {
					"type": "string",
					"description": "Root domain for the site ('' uses Press Settings default)",
				},
				"database": {"type": "string", "description": "Remote File docname of the database backup"},
				"public": {"type": "string", "description": "Remote File docname of the public files archive"},
				"private": {"type": "string", "description": "Remote File docname of the private files archive"},
				"config": {"type": "string", "description": "Remote File docname of the site_config backup"},
			},
		),
		"risk": "medium",
	},
	"site_restore": {
		"method": "press.mcp_server.site_ops.site_restore",
		"description": "Restore backup files into an EXISTING site. OVERWRITES its database — there is no undo. Each of database/public/private/config takes a Remote File docname (upload via POST press.api.site.upload_backup_file first); at least one is required. Runs as an agent job: poll site_status or agent_job_list. For a fresh site use site_create with 'database' instead.",
		"required_args": ["site"],
		"args_schema": _schema(
			["site"],
			{
				"database": {"type": "string", "description": "Remote File docname of the database backup"},
				"public": {"type": "string", "description": "Remote File docname of the public files archive"},
				"private": {"type": "string", "description": "Remote File docname of the private files archive"},
				"config": {"type": "string", "description": "Remote File docname of the site_config backup"},
				"skip_failing_patches": {
					"type": "boolean",
					"description": "Continue the post-restore migrate past a failing patch",
				},
				"skip_tables": {
					"type": "array",
					"items": {"type": "string"},
					"description": "Table names to exclude from the restore",
				},
			},
		),
		"risk": "high",
	},
	"site_archive": {
		"method": "press.mcp_server.site_ops.site_archive",
		"description": "Archive a site, only after a healthy offsite backup of it. Refuses any site that is not Inactive (run site_deactivate first). When the site has no healthy offsite backup with files taken after it was switched off, starts one and returns stage 'backup_started' or 'backup_running': call again until stage is 'archive_queued'. Press then drops the database and files as an agent job; poll site_status until Archived.",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "high",
	},
}
