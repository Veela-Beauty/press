# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""MCP discoverability — `help` and `list_tools` virtual tools.

Lets an agent connecting via MCP self-discover what tools it can call,
without prior knowledge of the catalog. Like `man` for the MCP server.

Two call shapes:

	1. Index — list every tool the caller's token can use, grouped by
	   category and risk. Lightweight; designed to fit in one response.

		{tool: "help"}                              -> full index (scoped)
		{tool: "help", args: {category: "readonly"}} -> filter to one category
		{tool: "help", args: {scope_only: true}}    -> only scoped tools (default)
		{tool: "help", args: {scope_only: false}}   -> ALL tools (incl. ones the
		                                                 token can't call — useful
		                                                 to know what to request)

	2. Detail — full spec for a single tool (description, required args,
	   risk, dotted method path).

		{tool: "help", args: {tool: "clone_bench"}}

Response shape mirrors the Vue catalog so AI agents can reason about
risk levels and categories without parsing snake_case tool names.
"""
from __future__ import annotations

from typing import Any

import frappe

from press.mcp_server.tools import TOOLS, get_tool_spec, list_tool_names

# Built-in virtual tools — handled inline by server.handle, not via the catalog.
# Always callable by any valid token, bypass scope check + rate limit.
BUILTIN_TOOLS = {"help", "list_tools"}

# Appended to every successful tool response unless caller passes args.suppress_hints=true.
DISCOVERABILITY_HINT = (
	"Tip: call {tool: 'help'} for the catalog + canonical recipes "
	"(deploy chain, Playwright passwordless login, agent diagnostics), "
	"or {tool: 'help', args: {tool: '<name>'}} for a single-tool detail. "
	"Pass args.suppress_hints=true to silence this."
)

# Canonical recipes — returned with every `help` index call so agents
# don't have to discover the right call ordering by trial and error.
# Each recipe is a short purpose + 2-6 line copy-paste flow. Keep these
# under ~120 chars per line so they render readably in any client.
SERVER_RECIPES: list[dict[str, Any]] = [
	{
		"id": "playwright_admin_login",
		"title": "Passwordless admin login for Playwright / E2E tests",
		"purpose": (
			"Login to /dashboard as the MCP token's user without typing a "
			"password. The token IS the auth — this bridges it into a real "
			"Frappe session cookie."
		),
		"steps": [
			"1. mcp('mint_dashboard_login_url', {redirect_to: '/dashboard/devtools/mcp'})",
			"2. Read .data.url from response (embeds ?sid=<sid>)",
			"3. mcp__playwright__browser_navigate(url=<that url>)",
			"4. You're authenticated. No login form, no rotation, no password.",
		],
		"caveats": (
			"sid cookie is HttpOnly — document.cookie won't show it. Verify "
			"auth by has_login_form==false + user name rendered in chrome. "
			"TTL inherits System Settings.session_expiry (default 6h)."
		),
	},
	{
		"id": "canonical_deploy",
		"title": "Canonical deploy chain (build → flip → verify, LLM-safe)",
		"purpose": (
			"Drive a full Release Group deploy from one MCP client without "
			"hitting the 'agent polls forever / restarts a busy worker' traps."
		),
		"steps": [
			"1. bench_deploy_information(name=<RG>) — see what's deployable",
			"2. app_release_approve(release_name=<r>) for every Draft release",
			"3. bench_deploy_and_wait(name=<RG>, apps=[{app,release,hash}...], site_name=<site>, max_wait_seconds=120)",
			"4. (optional) agent_job_progress(job_name=<build-job>) — live step stream",
			"5. deploy_candidate_status(name=<candidate>) — confirm Success",
			"6. site_update_and_wait(site_name=<site>, target_candidate=<candidate>) — per-site flip",
			"7. If status != 'flipped': read the hint. Gates B/C/D/E tell you exactly what to call next.",
			"8. On flip_failed: agent_job_traceback(job_name=<failed_migrate_job>) — see the real error.",
		],
		"caveats": (
			"Standalone Press doesn't auto-flip sites after build (Gate C fires). "
			"App Release rows default to status='Draft' and won't deploy until "
			"Approved (would have shipped old code without step 2)."
		),
	},
	{
		"id": "agent_diagnostics",
		"title": "Don't restart a busy agent — diagnose first",
		"purpose": (
			"BEFORE recommending an agent restart, check agent_health. "
			"Verdict 'slow' = mid-migrate, restart will corrupt the live DB. "
			"Gate A blocks bench_restart/bench_update when verdict='slow' "
			"unless force=true."
		),
		"steps": [
			"1. agent_health(server=<server>, lookback_minutes=10)",
			"2. verdict='healthy' → restart is safe.",
			"3. verdict='slow' → DO NOT restart. Wait or poll agent_job_progress on the running job.",
			"4. verdict='stuck' → run poll_pending_jobs ONCE (NOT restart).",
			"5. For a specific failed job: agent_job_traceback(job_name=<name>).",
		],
		"caveats": (
			"'many Undelivered jobs' is almost always a scheduler-callback hiccup, "
			"not a dead agent. Press's scheduler polls every 60s; Gate D auto-kicks "
			"poll_pending_jobs if needed."
		),
	},
]

# Category metadata — kept here, not in tools.py, because it's UX-only.
# Mirrors dashboard/src/components/mcp/_tool_catalog.js TOOL_CATEGORIES.
CATEGORIES: dict[str, dict[str, str]] = {
	"readonly": {"label": "Read-only", "tone": "green"},
	"bench_rg": {"label": "Bench / Release Group", "tone": "blue"},
	"site_lifecycle": {"label": "Site lifecycle", "tone": "blue"},
	"file_config": {"label": "File / Config", "tone": "amber"},
	"dangerous": {"label": "Dangerous (high-risk)", "tone": "red"},
}

# Tool -> category. Mirrors _tool_catalog.js TOOL_CATALOG[name].category.
# Single source of truth on the backend; the frontend mirror exists only
# to drive the issue-dialog scope picker. If you add a tool to TOOLS in
# tools.py, add a category mapping here too.
TOOL_CATEGORY: dict[str, str] = {
	# Read-only
	"lock_status": "readonly",
	"list_release_groups": "readonly",
	"list_sites": "readonly",
	"list_my_tokens": "readonly",
	"app_git_status": "readonly",
	"bench_recent_logs": "readonly",
	"site_db_processlist": "readonly",
	"deploy_failure_details": "readonly",
	"bench_deploy_information": "readonly",
	"bench_dev_info": "readonly",
	"site_domains_list": "readonly",
	"deploy_candidate_status": "readonly",
	"site_status": "readonly",
	"agent_job_list": "readonly",
	"wait_for_bench_flip": "readonly",
	"audit_verify_chain": "readonly",
	"bench_read_app_file": "readonly",
	"bench_list_app_files": "readonly",
	"bench_ssh_instructions": "readonly",
	"bench_ssh_register_key": "bench_rg",
	# Bench / Release Group
	"clone_bench": "bench_rg",
	"bench_deploy": "bench_rg",
	"bench_restart": "bench_rg",
	"bench_update_config": "bench_rg",
	"bench_ssh_cert_get": "bench_rg",
	"app_create_locally": "bench_rg",
	"app_init_github": "bench_rg",
	"app_release_approve": "bench_rg",
	"release_group_create_deploy_candidate": "bench_rg",
	"deploy_candidate_schedule_build": "bench_rg",
	# Site lifecycle
	"clone_site": "site_lifecycle",
	"move_site_to_release_group": "site_lifecycle",
	"lock_acquire": "site_lifecycle",
	"lock_release": "site_lifecycle",
	"site_migrate": "site_lifecycle",
	"site_backup": "site_lifecycle",
	"site_install_app": "site_lifecycle",
	"site_activate": "site_lifecycle",
	"site_add_domain": "site_lifecycle",
	"site_remove_domain": "site_lifecycle",
	"site_set_host_name": "site_lifecycle",
	"site_schedule_update": "site_lifecycle",
	"revoke_my_token": "site_lifecycle",
	# File / Config
	"site_config_get": "file_config",
	"site_config_set": "file_config",
	"site_file_read": "file_config",
	"site_file_write": "file_config",
	"site_update_config_bulk": "file_config",
	# Dangerous
	"site_run_python": "dangerous",
	"site_run_sql": "dangerous",
	"app_git_push": "dangerous",
	"site_uninstall_app": "dangerous",
	"site_deactivate": "dangerous",
	"bench_update": "dangerous",
	"site_update": "dangerous",
	"bench_ssh_cert_generate": "dangerous",
	"bench_update_dependencies": "dangerous",
	"bench_run_repo_script": "dangerous",
}


def get_tool_help(
	tool: str | None = None,
	category: str | None = None,
	scope_only: bool = True,
	caller_scope: list[str] | None = None,
) -> dict[str, Any]:
	"""Return MCP catalog metadata. Called by server.handle when tool='help'.

	Args:
		tool: optional single-tool name → return full detail for that tool only.
		category: optional category id → filter index to that category.
		scope_only: if True (default), only return tools the caller's token can
			call. If False, return all tools (useful for agents asking "what
			else exists that I'd need to request scope for?").
		caller_scope: list of tool names from the caller's token. Empty list ==
			"all" (no scope restriction). None == treat as empty (caller has
			no scope info — server is the caller).

	Returns:
		Single-tool form: {tool, description, required_args, risk, category, in_scope}
		Index form: {categories: [...], total, in_scope_count, hint}
	"""
	# Single-tool detail
	if tool:
		spec = get_tool_spec(tool)
		if not spec:
			return {
				"error": f"unknown tool {tool!r}",
				"available": list_tool_names(),
			}
		cat_id = TOOL_CATEGORY.get(tool, "readonly")
		return {
			"tool": tool,
			"description": spec.get("description", ""),
			"required_args": spec.get("required_args", []),
			"args_schema": spec.get("args_schema", {"type": "object", "properties": {}, "required": []}),
			"risk": spec.get("risk", "medium"),
			"category": cat_id,
			"category_label": CATEGORIES.get(cat_id, {}).get("label", cat_id),
			"in_scope": _is_in_scope(tool, caller_scope),
			"method": spec.get("method"),
			"example_call": _example_call(tool, spec),
		}

	# Index form — group by category
	caller_scope = caller_scope or []
	scope_set = set(caller_scope)
	all_in_scope = not caller_scope  # empty scope == all tools accessible

	# Filter pool
	tool_names = list_tool_names()
	if scope_only and not all_in_scope:
		tool_names = [t for t in tool_names if t in scope_set]

	# Group
	by_cat: dict[str, list[dict[str, Any]]] = {cid: [] for cid in CATEGORIES}
	for t in tool_names:
		spec = TOOLS[t]
		cat_id = TOOL_CATEGORY.get(t, "readonly")
		if category and cat_id != category:
			continue
		by_cat.setdefault(cat_id, []).append({
			"name": t,
			"description": spec.get("description", ""),
			"risk": spec.get("risk", "medium"),
			"required_args": spec.get("required_args", []),
			"in_scope": all_in_scope or t in scope_set,
		})

	categories_out = []
	for cid, meta in CATEGORIES.items():
		if category and cid != category:
			continue
		tools_in_cat = by_cat.get(cid, [])
		if not tools_in_cat:
			continue
		categories_out.append({
			"id": cid,
			"label": meta["label"],
			"tone": meta["tone"],
			"tools": tools_in_cat,
			"count": len(tools_in_cat),
		})

	in_scope_count = sum(
		1 for cat in categories_out for tl in cat["tools"] if tl["in_scope"]
	)
	total_in_index = sum(cat["count"] for cat in categories_out)
	full_total = len(list_tool_names())

	return {
		"categories": categories_out,
		"total_in_index": total_in_index,
		"in_scope_count": in_scope_count,
		"full_total": full_total,
		"scope_only_filter": scope_only,
		"recipes": SERVER_RECIPES,
		"hint": (
			"For full detail on one tool: {tool: 'help', args: {tool: '<name>'}}. "
			"Pass scope_only=false to also see tools your token CANNOT call "
			"(useful when planning a request for additional scope). The recipes "
			"array shows the canonical call orderings — read them BEFORE building "
			"your own multi-tool flow."
		),
	}


def _is_in_scope(tool: str, caller_scope: list[str] | None) -> bool:
	if not caller_scope:
		# Empty scope means "all tools" by convention (token issued without restriction)
		return True
	return tool in caller_scope


def _example_call(tool: str, spec: dict) -> dict[str, Any]:
	"""Build a minimal example call payload an agent can copy-paste."""
	args_template = {a: f"<{a}>" for a in spec.get("required_args", [])}
	return {"tool": tool, "args": args_template, "token": "<your-token>"}


@frappe.whitelist()
def get_server_recipes() -> list[dict]:
	"""Return SERVER_RECIPES for the dashboard MCPHowToBox UI panel.

	Same data the MCP `help` index returns to AI agents — exposing it as a
	standalone whitelisted method so the Vue UI can render the same canonical
	recipes without going through the MCP token dispatch path.
	"""
	return SERVER_RECIPES
