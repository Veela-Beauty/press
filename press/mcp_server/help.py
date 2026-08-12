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
			"1. mcp('mint_dashboard_login_url', {redirect_to: '/dashboard/dev-tools/mcp'})",
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
			"0. (if upstream pushed new commits) app_source_fetch_latest(app=<app>, release_group=<RG>) — polls GitHub + creates a Draft App Release. Skip if bench_deploy_information already shows a Draft.",
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
			"Approved (would have shipped old code without step 2). "
			"Step 0 (app_source_fetch_latest) is what replaces the dashboard's "
			"'Fetch Latest' button — call it FIRST when an upstream commit "
			"hasn't appeared in Press's release list yet."
		),
	},
	{
		"id": "host_memory_pressure_check",
		"title": "Catch host OOM before it strikes (memory pressure check)",
		"purpose": (
			"On 2026-05-23, press-f1 MariaDB was OOM-killed by Linux because "
			"RAM + swap were exhausted. 32 sites 500ed for 25 minutes. The fix "
			"is to monitor BEFORE the OOM. Call this in any flow that creates / "
			"migrates a site, OR when a user reports 'multiple sites are slow'."
		),
		"steps": [
			"1. host_memory_pressure({server: '<server-docname>'})",
			"2. Read .verdict:",
			"   - ok        → safe to proceed",
			"   - elevated  → warn user, avoid concurrent backups/big reports",
			"   - critical  → STOP. Surface .hint to user. Contact admin to scale RAM, OR free memory by deactivating idle sites.",
			"   - unknown   → SSH check failed; verify Press can reach this server",
			"3. Results are cached 60s; pass force_refresh=true after a worker restart to confirm memory dropped.",
			"4. Bonus: .swap_used_pct >= 80% is itself an 'elevated' signal even when memory_available_mb still looks OK — swap exhaustion is the canary.",
		],
		"caveats": (
			"This tool uses SSH/Ansible (no Prometheus dependency). First call "
			"to a server takes 3-10s; subsequent calls within 60s return cached "
			"data in <100ms. Designed for polling — don't be shy about calling it. "
			"Phase 2 will add a cron that records pressure events to tabBench so "
			"admins see chronic offenders in the dashboard. For now this is a "
			"pull-based check."
		),
	},
	{
		"id": "watch_bench_provision",
		"title": "Watch a bench provision from build → ready (no filesystem polling)",
		"purpose": (
			"After release_group_create_deploy_candidate + "
			"deploy_candidate_schedule_build, a new Bench row is created and "
			"goes through Build → New Bench → Setup Bench → Site Migrate → "
			"Ready. Each phase has a typical duration; the WRONG thing to do "
			"is poll `ls /home/frappe/benches/<bench>/apps` because the dir "
			"is empty for the first 5-10 min while agent clones repos one at "
			"a time. The RIGHT thing is to poll bench_provision_progress."
		),
		"steps": [
			"1. After release_group_create_deploy_candidate, you have a candidate name (e.g. 'deploy-0028-000006').",
			"2. Find the new Bench: list_release_groups + look at the latest bench, OR query Bench where candidate=<candidate>.",
			"3. Loop: bench_provision_progress(bench_name=<bench>) every 10s.",
			"4. Read .stage + .stage_label. Stage tells you which phase is running:",
			"   - build       → Docker image build (~3 min)",
			"   - new_bench   → starting container (~30s)",
			"   - setup_bench → cloning apps into bench (5-10 min — looks 'empty' if you check filesystem!)",
			"   - site_migrate→ flipping a site onto the new bench (~30s-3min)",
			"   - ready       → done, bench is Active",
			"   - failed      → check .chain[] for the failed step, then agent_job_traceback(job_name=<that step's job>)",
			"5. Total expected: ~10-15 min on a heavy bench. Stop watching when stage=='ready'.",
		],
		"caveats": (
			"setup_bench can show 'Running' for 5-10 min with no filesystem "
			"signal — that's NORMAL (sequential git clones). Do NOT restart "
			"the agent based on filesystem emptiness. If stage stays "
			"'setup_bench' for >20 min with no agent_job_progress.current_step "
			"changes, THEN it's actually stuck (call agent_job_progress on the "
			"Setup Bench job_name to see which app is hanging)."
		),
	},
	{
		"id": "app_lifecycle",
		"title": "Onboard a new app OR pull a new upstream commit (no UI)",
		"purpose": (
			"Two related workflows: (a) register an existing GitHub repo so "
			"Press tracks it, (b) pull new upstream commits into Draft App "
			"Release rows. Both replace dashboard clicks that used to block "
			"agent automation."
		),
		"steps": [
			"# (a) Onboard an existing GitHub repo as an App Source",
			"1. register_existing_app(repository_url='https://github.com/owner/repo', branch='main', app_name='my_app')",
			"2. Optional: add the new App Source to a Release Group via the Desk, then proceed with canonical_deploy.",
			"",
			"# (b) Pull latest upstream commits into Draft App Releases",
			"1. list_pending_releases(app='my_app', release_group='bench-XYZ')  # see what's already Draft",
			"2. app_source_fetch_latest(app='my_app', release_group='bench-XYZ')  # poll GitHub, creates new Draft if upstream has new commits",
			"3. Returned new_release.name → feed into app_release_approve in canonical_deploy step 2.",
		],
		"caveats": (
			"register_existing_app is for repos ALREADY ON GitHub — use "
			"app_create_locally instead when scaffolding a brand-new empty app. "
			"app_source_fetch_latest can return no_new_release=true (upstream "
			"unchanged); that's not an error. Pass force=true to retry after "
			"a last_github_poll_failed."
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
	"bench_provision_progress": "readonly",
	"host_memory_pressure": "readonly",
	"audit_verify_chain": "readonly",
	"bench_read_app_file": "readonly",
	"bench_list_app_files": "readonly",
	"bench_ssh_connect": "bench_rg",
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
	"app_source_fetch_latest": "readonly",
	"list_pending_releases": "readonly",
	"register_existing_app": "bench_rg",
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
	"site_create": "site_lifecycle",
	"site_restore": "site_lifecycle",
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
		# Lightweight discovery nudge so single-tool lookups still surface new tools.
		recent_tools = [
			"app_source_fetch_latest", "list_pending_releases", "register_existing_app",
			"bench_provision_progress",
		]
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
			"recently_shipped_tools": recent_tools,
			"recently_shipped_hint": (
				"Three new tools shipped 2026-05-22: app_source_fetch_latest "
				"(replaces dashboard 'Fetch Latest'), list_pending_releases, "
				"register_existing_app. Call help() with no args for the "
				"whats_new field + recipes."
			),
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

	# Recently shipped tools — keep this list trimmed to the last ~3 batches.
	# Agents see this on every help call so new capabilities surface fast.
	whats_new = [
		{
			"date": "2026-05-22",
			"tools": [
				"app_source_fetch_latest",
				"list_pending_releases",
				"register_existing_app",
				"bench_provision_progress",
				"site_update (rewrapped)",
			],
			"summary": (
				"App lifecycle + bench-stage rollup + site_update rewrap. "
				"'Fetch Latest' polls GitHub. 'List Pending Releases' audits "
				"Drafts. 'Register Existing App' onboards a GitHub repo. "
				"'Bench Provision Progress' returns a single dict with the "
				"current stage (build / new_bench / setup_bench / "
				"site_migrate / ready / failed) so you stop polling the "
				"filesystem and start polling a meaningful signal. "
				"site_update now PRE-CHECKS for a destination candidate and "
				"returns ok:false with a structured hint instead of throwing "
				"the misleading 'Could not find suitable Destination Bench'. "
				"Also fixed today: list_pending_releases + app_source_fetch_latest "
				"no longer reference the non-existent 'tag' column. See "
				"app_lifecycle + watch_bench_provision recipes."
			),
		},
		{
			"date": "2026-05-20",
			"tools": [
				"agent_health",
				"agent_job_traceback",
				"agent_job_progress",
				"site_update_and_wait",
				"wait_for_bench_flip",
			],
			"summary": (
				"Deploy workflow + 4 safety gates. See canonical_deploy and "
				"agent_diagnostics recipes."
			),
		},
	]

	return {
		"categories": categories_out,
		"total_in_index": total_in_index,
		"in_scope_count": in_scope_count,
		"full_total": full_total,
		"scope_only_filter": scope_only,
		"recipes": SERVER_RECIPES,
		"whats_new": whats_new,
		"hint": (
			"For full detail on one tool: {tool: 'help', args: {tool: '<name>'}}. "
			"Pass scope_only=false to also see tools your token CANNOT call "
			"(useful when planning a request for additional scope). The recipes "
			"array shows the canonical call orderings — read them BEFORE building "
			"your own multi-tool flow. The whats_new array highlights tools "
			"shipped recently — check this on first help call to discover new "
			"capabilities."
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


@frappe.whitelist()
def get_tool_catalog_for_guide() -> dict[str, Any]:
	"""Return the full MCP tool catalog grouped by category for the
	dashboard's MCP Guide tab.

	Catalog-driven docs — every tool's title, description, args_schema, risk
	level, and a copy-pasteable example call. Reading this is equivalent to
	reading tools.py. Updates automatically when tools.py changes.

	Different from `get_tool_help` (called via MCP token dispatch) because:
	- No token required (dashboard guide is for browsing, not calling).
	- Always returns ALL tools (not scope-filtered) — humans want to see the
	  full menu, including tools they'd need to request scope for.
	- Returns example_call inline for every tool, not just on detail requests.
	"""
	categories_out = []
	for cid, meta in CATEGORIES.items():
		tools_in_cat = []
		for tool_name in list_tool_names():
			if TOOL_CATEGORY.get(tool_name, "readonly") != cid:
				continue
			spec = TOOLS[tool_name]
			tools_in_cat.append({
				"name": tool_name,
				"description": spec.get("description", ""),
				"risk": spec.get("risk", "medium"),
				"required_args": spec.get("required_args", []),
				"args_schema": spec.get("args_schema", {"type": "object", "properties": {}, "required": []}),
				"method": spec.get("method"),
				"example_call": _example_call(tool_name, spec),
			})
		if not tools_in_cat:
			continue
		# Stable alpha order within each category
		tools_in_cat.sort(key=lambda t: t["name"])
		categories_out.append({
			"id": cid,
			"label": meta["label"],
			"tone": meta["tone"],
			"tools": tools_in_cat,
			"count": len(tools_in_cat),
		})
	return {
		"categories": categories_out,
		"total": sum(c["count"] for c in categories_out),
		"recipes": SERVER_RECIPES,
	}
