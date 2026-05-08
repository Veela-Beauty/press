# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""MCP tool catalog — declarative mapping of tool name to whitelisted method.

Each entry:
	method: dotted-path to the underlying whitelisted Python function
	description: shown in tool list
	required_args: list of arg names the tool requires
"""
from __future__ import annotations

# Tool name -> spec
TOOLS: dict[str, dict] = {
	# Clone (Obj 1)
	"clone_bench": {
		"method": "press.press.doctype.release_group.release_group_clone.clone_release_group",
		"description": "Clone a Release Group on the same server with the same apps",
		"required_args": ["release_group", "new_title"],
	},
	"clone_site": {
		"method": "press.press.doctype.site.site_clone.clone_site",
		"description": "Clone a Site onto a target bench (3 modes)",
		"required_args": ["site", "target_bench", "new_subdomain"],
	},
	# Move (Obj 2)
	"move_site_to_release_group": {
		"method": "press.api.site_move.move_to_release_group",
		"description": "Move a Site to a different Release Group",
		"required_args": ["site", "target_release_group"],
	},
	# Locks (Obj 3)
	"lock_acquire": {
		"method": "press.api.lock.acquire",
		"description": "Acquire an advisory lock on Site or Release Group",
		"required_args": ["target_doctype", "target_name", "reason"],
	},
	"lock_release": {
		"method": "press.api.lock.release",
		"description": "Release an advisory lock you hold",
		"required_args": ["target_doctype", "target_name"],
	},
	"lock_status": {
		"method": "press.api.lock.status",
		"description": "Inspect lock state of Site or Release Group",
		"required_args": ["target_doctype", "target_name"],
	},
	# Read-only (4b additions)
	"list_release_groups": {
		"method": "press.api.bench.all",
		"description": "List Release Groups visible to the calling user",
		"required_args": [],
	},
	"list_sites": {
		"method": "press.api.site.all",
		"description": "List Sites visible to the calling user",
		"required_args": [],
	},
	# Token self-management
	"list_my_tokens": {
		"method": "press.mcp_server.dashboard.list_my_tokens",
		"description": "List active MCP tokens for the calling user",
		"required_args": [],
	},
	"revoke_my_token": {
		"method": "press.mcp_server.auth.revoke_token",
		"description": "Revoke an MCP token by docname",
		"required_args": ["token_id"],
	},
	# Git ops
	"app_git_status": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_app_git_status",
		"description": "Get git branch/commit/dirty status for apps in a bench (per-site)",
		"required_args": ["bench_name"],
	},
	"app_git_push": {
		"method": "press.press.doctype.bench.bench_dev_overview.push_app_to_github",
		"description": "Commit + push an app's working tree to GitHub from inside the bench container",
		"required_args": ["bench_name", "app", "message"],
	},
	"app_create_locally": {
		"method": "press.press.doctype.bench.bench_app_management.create_app_locally",
		"description": "Run `bench new-app` inside a bench container",
		"required_args": ["bench_name", "app_name", "app_title"],
	},
	"app_init_github": {
		"method": "press.press.doctype.bench.bench_app_management.init_github_for_app",
		"description": "Create a GitHub repo for an existing local app and register it in Press",
		"required_args": ["bench_name", "app_name", "github_owner"],
	},
	# Console / shell (run code inside bench container)
	"site_run_python": {
		"method": "press.press.doctype.bench.bench_dev_overview.run_python_on_site",
		"description": "Run a Python snippet on a site in the bench console (full power, system-manager only)",
		"required_args": ["site_name", "code"],
	},
	"site_run_sql": {
		"method": "press.press.doctype.bench.bench_dev_overview.run_sql_on_site",
		"description": "Run SQL on the site database (default read-only; commit=true for writes)",
		"required_args": ["site_name", "query"],
	},
	# Logs + diagnostics
	"bench_recent_logs": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_recent_logs",
		"description": "Tail recent bench logs (frappe.log, scheduler.log, error.log, etc.)",
		"required_args": ["bench_name"],
	},
	"site_db_processlist": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_db_processlist",
		"description": "MariaDB SHOW PROCESSLIST for the site DB",
		"required_args": ["site_name"],
	},
	"deploy_failure_details": {
		"method": "press.press.doctype.deploy_candidate_build.build_diagnostics.get_failure_details",
		"description": "Inspect a failed Deploy Candidate Build (failed step, stage, output)",
		"required_args": ["dn"],
	},
	# Bench / Release Group lifecycle
	"bench_deploy": {
		"method": "press.api.bench.deploy",
		"description": "Trigger a deploy for a Release Group's apps",
		"required_args": ["name", "apps"],
	},
	"bench_deploy_information": {
		"method": "press.api.bench.deploy_information",
		"description": "Get deploy candidate / pending updates info for a Release Group",
		"required_args": ["name"],
	},
	"bench_restart": {
		"method": "press.api.bench.restart",
		"description": "Restart a Bench (gunicorn + workers)",
		"required_args": ["name"],
	},
	"bench_update": {
		"method": "press.api.bench.update",
		"description": "Update a Bench to the latest deploy",
		"required_args": ["name"],
	},
	# Site lifecycle
	"site_migrate": {
		"method": "press.api.site.migrate",
		"description": "Run `bench --site X migrate` on the site",
		"required_args": ["name"],
	},
	"site_backup": {
		"method": "press.api.site.backup",
		"description": "Trigger a site backup",
		"required_args": ["name"],
	},
	"site_install_app": {
		"method": "press.api.site.install_app",
		"description": "Install an app on a site",
		"required_args": ["name", "app"],
	},
	"site_uninstall_app": {
		"method": "press.api.site.uninstall_app",
		"description": "Uninstall an app from a site",
		"required_args": ["name", "app"],
	},
	"site_activate": {
		"method": "press.api.site.activate",
		"description": "Activate a previously deactivated site",
		"required_args": ["name"],
	},
	"site_deactivate": {
		"method": "press.api.site.deactivate",
		"description": "Deactivate a site (puts it in maintenance mode)",
		"required_args": ["name"],
	},
	"site_update": {
		"method": "press.api.site.update",
		"description": "Update a site to the latest bench deploy",
		"required_args": ["name"],
	},
}


def get_tool_spec(tool_name: str) -> dict | None:
	return TOOLS.get(tool_name)


def list_tool_names() -> list[str]:
	return sorted(TOOLS.keys())
