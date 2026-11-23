# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Catalog part: the deploy and release flow (candidates, builds, waits, agent jobs, app sources). Merged into press/mcp_server/tools.py TOOLS (split 0.7.54)."""

from __future__ import annotations

from press.mcp_server.tool_catalog._schema import _schema

DEPLOY_TOOLS: dict[str, dict] = {
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
		"description": "ONE-SHOT deploy + wait. Triggers bench_deploy and BLOCKS until the site flips to the new Deploy Candidate, or for at most 30 s (then call again). OLDER and BLOCKING: it holds a web worker while it waits. Use bench_deploy_and_update, which returns at once and updates the sites too. Returns {candidate, status: 'flipped'|'timeout', elapsed_seconds, ...}. Args: name (Release Group docname); apps (list of {app, release, hash} dicts from bench_deploy_information); site_name (one site on the RG to watch — multiple sites can be on the RG but this only waits for the named one).",
		"required_args": ["name", "apps", "site_name"],
		"args_schema": _schema(
			["name", "apps", "site_name"],
			{
				"max_wait_seconds": {
					"type": "integer",
					"minimum": 30,
					"maximum": 30,
					"description": "Wait at most this long (max 30 s), then status 'timeout': call again, or use bench_deploy_and_update",
				},
				"poll_interval_seconds": {
					"type": "integer",
					"minimum": 5,
					"maximum": 300,
					"description": "How often to re-check (default 5s, the minimum)",
				},
			},
		),
		"risk": "medium",
	},
	"bench_deploy_and_update": {
		"method": "press.mcp_server.deploy_update.bench_deploy_and_update",
		"description": "ONE call for a whole deploy, the dashboard's Deploy and update: builds the apps, starts the new bench and updates the sites on it once the bench is ready. Returns at once with {build, candidate, sites, next}; then call deploy_update_status(name=<build>) about every 30 s until done is true. Replaces bench_deploy + wait_for_bench_flip + deploy_candidate_status + site_update. Args: name (Release Group docname); apps (list of {app, release, hash} from bench_deploy_information); sites (optional list of Active site names on this Release Group; default: your team's Active sites on it).",
		"required_args": ["name", "apps"],
		"args_schema": _schema(
			["name", "apps"],
			{
				"sites": {
					"type": "array",
					"items": {"type": "string"},
					"description": "Active sites on this Release Group to update (default: all of them)",
				},
			},
		),
		"risk": "medium",
	},
	"deploy_update_status": {
		"method": "press.mcp_server.deploy_update.deploy_update_status",
		"description": "Single-shot status of a bench_deploy_and_update (NOT a blocking wait). Returns {stage: build|bench|sites|done, done, ok, build_status, benches: [{bench, status}], sites: [{site, status, site_update, update_job}], hint?}. Call about every 30 s until done is true; on ok=false follow the hint. Args: name (the build returned by bench_deploy_and_update).",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "low",
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
		"description": "OLDER and BLOCKING (holds a web worker up to 30 s; prefer bench_deploy_and_update, which updates the sites itself). ONE-SHOT site_update + wait. Triggers Site Update Migrate and BLOCKS until the site flips onto target_candidate or max_wait_seconds (max 30 s) expires. Use AFTER bench_deploy_and_wait reports build Success but the site still hasn't flipped (standalone Press doesn't auto-flip — each site needs an explicit site_update). Returns {site, status: 'flipped'|'timeout', site_update_job, elapsed_seconds, current_bench, current_candidate}. Args: site_name (site FQDN); target_candidate (Deploy Candidate the site should end up on).",
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
					"maximum": 30,
					"description": "Wait at most this long (max 30 s), then status 'timeout': call again, or use bench_deploy_and_update",
				},
				"poll_interval_seconds": {
					"type": "integer",
					"minimum": 5,
					"maximum": 300,
					"description": "How often to re-check (default 5s, the minimum)",
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
}
