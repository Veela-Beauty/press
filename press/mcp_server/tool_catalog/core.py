# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Catalog part: cloning, moving a site, locks, the read-only basics and token self-management. Merged into press/mcp_server/tools.py TOOLS (split 0.7.54)."""

from __future__ import annotations

from press.mcp_server.tool_catalog._schema import _schema

CORE_TOOLS: dict[str, dict] = {
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
}
