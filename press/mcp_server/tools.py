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
from press.mcp_server.tool_catalog._schema import (  # noqa: F401  re-exported: dotted paths and imports of this module keep working
	_ARG_FRAGMENTS,
	_schema,
)
from press.mcp_server.tool_catalog.core import CORE_TOOLS
from press.mcp_server.tool_catalog.bench_code import BENCH_CODE_TOOLS
from press.mcp_server.tool_catalog.sites_benches import SITES_BENCHES_TOOLS


# Tool name -> spec
TOOLS: dict[str, dict] = {
	**CORE_TOOLS,
	**BENCH_CODE_TOOLS,
	**SITES_BENCHES_TOOLS,
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
		"required_args": ["new_subdomain", "release_group"],
		"args_schema": _schema(
			["new_subdomain", "release_group"],
			{
				"apps": {
					"type": "array",
					"items": {"type": "string"},
					"description": "App names to install, e.g. ['frappe','erpnext']. Defaults to ['frappe'].",
				},
				"plan": {"type": "string", "description": "Site Plan docname ('' lets Press pick)"},
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
