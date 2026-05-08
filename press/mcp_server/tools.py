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
		"risk": "medium",
	},
	"clone_site": {
		"method": "press.press.doctype.site.site_clone.clone_site",
		"description": "Clone a Site onto a target bench (3 modes)",
		"required_args": ["site", "target_bench", "new_subdomain"],
		"risk": "medium",
	},
	# Move (Obj 2)
	"move_site_to_release_group": {
		"method": "press.api.site_move.move_to_release_group",
		"description": "Move a Site to a different Release Group",
		"required_args": ["site", "target_release_group"],
		"risk": "medium",
	},
	# Locks (Obj 3)
	"lock_acquire": {
		"method": "press.api.lock.acquire",
		"description": "Acquire an advisory lock on Site or Release Group",
		"required_args": ["target_doctype", "target_name", "reason"],
		"risk": "medium",
	},
	"lock_release": {
		"method": "press.api.lock.release",
		"description": "Release an advisory lock you hold",
		"required_args": ["target_doctype", "target_name"],
		"risk": "medium",
	},
	"lock_status": {
		"method": "press.api.lock.status",
		"description": "Inspect lock state of Site or Release Group",
		"required_args": ["target_doctype", "target_name"],
		"risk": "low",
	},
	# Read-only (4b additions)
	"list_release_groups": {
		"method": "press.api.bench.all",
		"description": "List Release Groups visible to the calling user",
		"required_args": [],
		"risk": "low",
	},
	"list_sites": {
		"method": "press.api.site.all",
		"description": "List Sites visible to the calling user",
		"required_args": [],
		"risk": "low",
	},
	# Token self-management
	"list_my_tokens": {
		"method": "press.mcp_server.dashboard.list_my_tokens",
		"description": "List active MCP tokens for the calling user",
		"required_args": [],
		"risk": "low",
	},
	"revoke_my_token": {
		"method": "press.mcp_server.auth.revoke_token",
		"description": "Revoke an MCP token by docname",
		"required_args": ["token_id"],
		"risk": "medium",
	},
	# Git ops
	"app_git_status": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_app_git_status",
		"description": "Get git branch/commit/dirty status for apps in a bench (per-site)",
		"required_args": ["bench_name"],
		"risk": "low",
	},
	"app_git_push": {
		"method": "press.press.doctype.bench.bench_dev_overview.push_app_to_github",
		"description": "Commit + push an app's working tree to GitHub from inside the bench container",
		"required_args": ["bench_name", "app", "message"],
		"risk": "high",
	},
	"app_create_locally": {
		"method": "press.press.doctype.bench.bench_app_management.create_app_locally",
		"description": "Run `bench new-app` inside a bench container",
		"required_args": ["bench_name", "app_name", "app_title"],
		"risk": "medium",
	},
	"app_init_github": {
		"method": "press.press.doctype.bench.bench_app_management.init_github_for_app",
		"description": "Create a GitHub repo for an existing local app and register it in Press",
		"required_args": ["bench_name", "app_name", "github_owner"],
		"risk": "medium",
	},
	# Console / shell (run code inside bench container)
	"site_run_python": {
		"method": "press.press.doctype.bench.bench_dev_overview.run_python_on_site",
		"description": "Run a Python snippet on a site in the bench console (full power, system-manager only)",
		"required_args": ["site_name", "code"],
		"risk": "high",
	},
	"site_run_sql": {
		"method": "press.press.doctype.bench.bench_dev_overview.run_sql_on_site",
		"description": "Run SQL on the site database (default read-only; commit=true for writes)",
		"required_args": ["site_name", "query"],
		"risk": "high",
	},
	# Logs + diagnostics
	"bench_recent_logs": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_recent_logs",
		"description": "Tail recent bench logs (frappe.log, scheduler.log, error.log, etc.)",
		"required_args": ["bench_name"],
		"risk": "low",
	},
	"site_db_processlist": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_db_processlist",
		"description": "MariaDB SHOW PROCESSLIST for the site DB",
		"required_args": ["site_name"],
		"risk": "low",
	},
	"deploy_failure_details": {
		"method": "press.press.doctype.deploy_candidate_build.build_diagnostics.get_failure_details",
		"description": "Inspect a failed Deploy Candidate Build (failed step, stage, output)",
		"required_args": ["dn"],
		"risk": "low",
	},
	# Bench / Release Group lifecycle
	"bench_deploy": {
		"method": "press.api.bench.deploy",
		"description": "Trigger a deploy for a Release Group's apps",
		"required_args": ["name", "apps"],
		"risk": "medium",
	},
	"bench_deploy_information": {
		"method": "press.api.bench.deploy_information",
		"description": "Get deploy candidate / pending updates info for a Release Group",
		"required_args": ["name"],
		"risk": "low",
	},
	"bench_restart": {
		"method": "press.api.bench.restart",
		"description": "Restart a Bench (gunicorn + workers)",
		"required_args": ["name"],
		"risk": "medium",
	},
	"bench_update": {
		"method": "press.api.bench.update",
		"description": "Update a Bench to the latest deploy",
		"required_args": ["name"],
		"risk": "high",
	},
	# Site lifecycle
	"site_migrate": {
		"method": "press.api.site.migrate",
		"description": "Run `bench --site X migrate` on the site",
		"required_args": ["name"],
		"risk": "medium",
	},
	"site_backup": {
		"method": "press.api.site.backup",
		"description": "Trigger a site backup",
		"required_args": ["name"],
		"risk": "medium",
	},
	"site_install_app": {
		"method": "press.api.site.install_app",
		"description": "Install an app on a site",
		"required_args": ["name", "app"],
		"risk": "medium",
	},
	"site_uninstall_app": {
		"method": "press.api.site.uninstall_app",
		"description": "Uninstall an app from a site",
		"required_args": ["name", "app"],
		"risk": "high",
	},
	"site_activate": {
		"method": "press.api.site.activate",
		"description": "Activate a previously deactivated site",
		"required_args": ["name"],
		"risk": "medium",
	},
	"site_deactivate": {
		"method": "press.api.site.deactivate",
		"description": "Deactivate a site (puts it in maintenance mode)",
		"required_args": ["name"],
		"risk": "high",
	},
	"site_update": {
		"method": "press.api.site.update",
		"description": "Update a site to the latest bench deploy",
		"required_args": ["name"],
		"risk": "high",
	},
	# SSH access (cert generation lets agents SSH into bench container)
	"bench_ssh_cert_get": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_ssh_certificate",
		"description": "Get the existing SSH certificate for a bench (returns None if not yet generated)",
		"required_args": ["bench_name"],
		"risk": "medium",
	},
	"bench_ssh_cert_generate": {
		"method": "press.press.doctype.bench.bench_dev_overview.generate_ssh_certificate",
		"description": "Generate an SSH certificate for a bench so the agent can SSH into the bench container",
		"required_args": ["bench_name"],
		"risk": "high",
	},
	"bench_dev_info": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_bench_dev_info",
		"description": "Get bench dev connection info: server IP, SSH port, is_development_bench flag",
		"required_args": ["bench_name"],
		"risk": "low",
	},
	# Site config (medium-risk — structured replacement for site_run_python config edits)
	"site_config_get": {
		"method": "press.mcp_server.file_ops.site_config_get",
		"description": "Read site_config.json keys (sensitive keys redacted)",
		"required_args": ["site_name"],
		"risk": "medium",
	},
	"site_config_set": {
		"method": "press.mcp_server.file_ops.site_config_set",
		"description": "Set a single site_config.json key (sensitive keys forbidden)",
		"required_args": ["site_name", "key", "value"],
		"risk": "medium",
	},
	# File ops (medium-risk — constrained to public/private folders)
	"site_file_read": {
		"method": "press.mcp_server.file_ops.site_file_read",
		"description": "Read a file from the site's public/files/ or private/files/ folder",
		"required_args": ["site_name", "relative_path"],
		"risk": "medium",
	},
	"site_file_write": {
		"method": "press.mcp_server.file_ops.site_file_write",
		"description": "Write a file to the site's public/files/ or private/files/ folder",
		"required_args": ["site_name", "relative_path", "content"],
		"risk": "medium",
	},
	# Domains (Obj 8)
	"site_domains_list": {
		"method": "press.api.site.domains",
		"description": "List domains attached to a site",
		"required_args": ["name"],
		"risk": "low",
	},
	"site_add_domain": {
		"method": "press.api.site.add_domain",
		"description": "Attach a custom domain to a site",
		"required_args": ["name", "domain"],
		"risk": "medium",
	},
	"site_remove_domain": {
		"method": "press.api.site.remove_domain",
		"description": "Detach a custom domain from a site",
		"required_args": ["name", "domain"],
		"risk": "medium",
	},
	"site_set_host_name": {
		"method": "press.api.site.set_host_name",
		"description": "Set the primary domain (host name) for a site",
		"required_args": ["name", "domain"],
		"risk": "medium",
	},
	"site_update_config_bulk": {
		"method": "press.api.site.update_config",
		"description": "Bulk-update site_config.json keys (passes through Press's update_config — uses Press internal allow-list)",
		"required_args": ["name", "config"],
		"risk": "medium",
	},
	# Bench config (Obj 8)
	"bench_update_config": {
		"method": "press.api.bench.update_config",
		"description": "Bulk-update bench common_site_config keys",
		"required_args": ["name", "config"],
		"risk": "medium",
	},
	"bench_update_dependencies": {
		"method": "press.api.bench.update_dependencies",
		"description": "Update bench dependency versions (Python/Node/etc) — triggers rebuild",
		"required_args": ["name", "dependencies"],
		"risk": "high",
	},
	# Deploy / release flow (Obj 10)
	"app_release_approve": {
		"method": "press.mcp_server.deploy_flow.app_release_approve",
		"description": "Approve a Draft App Release for inclusion in Deploy Candidates",
		"required_args": ["release_name"],
		"risk": "medium",
	},
	"release_group_create_deploy_candidate": {
		"method": "press.mcp_server.deploy_flow.release_group_create_deploy_candidate",
		"description": "Create a new Deploy Candidate for a Release Group",
		"required_args": ["name"],
		"risk": "medium",
	},
	"deploy_candidate_schedule_build": {
		"method": "press.mcp_server.deploy_flow.deploy_candidate_schedule_build",
		"description": "Schedule build + deploy for a Deploy Candidate; returns the build job name",
		"required_args": ["candidate_name"],
		"risk": "medium",
	},
	"deploy_candidate_status": {
		"method": "press.mcp_server.deploy_flow.deploy_candidate_status",
		"description": "Status of a Deploy Candidate Build OR a Deploy Candidate",
		"required_args": ["name"],
		"risk": "low",
	},
	"site_schedule_update": {
		"method": "press.mcp_server.deploy_flow.site_schedule_update",
		"description": "Schedule a Site Update (migrate to latest bench in same Release Group)",
		"required_args": ["site_name"],
		"risk": "medium",
	},
	"site_status": {
		"method": "press.mcp_server.deploy_flow.site_status",
		"description": "Current site bench + status + recent agent jobs (polling primitive)",
		"required_args": ["site_name"],
		"risk": "low",
	},
	"agent_job_list": {
		"method": "press.mcp_server.deploy_flow.agent_job_list",
		"description": "List recent Agent Jobs filtered by site/status/window",
		"required_args": [],
		"risk": "low",
	},
	"wait_for_bench_flip": {
		"method": "press.mcp_server.deploy_flow.wait_for_bench_flip",
		"description": "Async-style poll: returns flipped|pending for a site against a target Deploy Candidate",
		"required_args": ["site_name", "target_candidate"],
		"risk": "low",
	},
	"bench_run_repo_script": {
		"method": "press.mcp_server.script_runner.bench_run_repo_script",
		"description": "Fetch a Python script from an allowlisted GitHub repo and run it in a bench (high-risk; gated)",
		"required_args": ["bench_name", "repo", "branch", "script_path"],
		"risk": "high",
	},
}


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
