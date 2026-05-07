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
}


def get_tool_spec(tool_name: str) -> dict | None:
	return TOOLS.get(tool_name)


def list_tool_names() -> list[str]:
	return sorted(TOOLS.keys())
