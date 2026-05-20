// Frontend mirror of press/mcp_server/tools.py — tool name → category + risk + description.
// Single source of truth for the IssueTokenDialog scope picker UX.
// When a new tool is added to tools.py, add an entry here too.

export const TOOL_CATEGORIES = [
	{ id: 'readonly', label: 'Read-only', icon: 'eye', tone: 'green' },
	{ id: 'bench_rg', label: 'Bench / Release Group', icon: 'box', tone: 'blue' },
	{ id: 'site_lifecycle', label: 'Site lifecycle', icon: 'globe', tone: 'blue' },
	{ id: 'file_config', label: 'File / Config', icon: 'file-text', tone: 'amber' },
	{ id: 'dangerous', label: 'Dangerous (high-risk)', icon: 'alert-triangle', tone: 'red' },
];

// risk: 'low' | 'medium' | 'high'  — must match tools.py
// category: id from TOOL_CATEGORIES above
// label: human-friendly display name (recipients see this in the dialog)
//
// Built-in virtual tools `help` and `list_tools` are ALWAYS callable by any
// valid token (server.py BUILTIN_TOOLS) — they are not in this catalog and
// don't need to appear in the scope picker.
export const TOOL_CATALOG = {
	// READ-ONLY (low risk)
	lock_status:              { category: 'readonly', risk: 'low', label: 'Lock — Status',                desc: 'Inspect lock state of Site or Release Group' },
	list_release_groups:      { category: 'readonly', risk: 'low', label: 'List Release Groups',           desc: 'List Release Groups visible to caller' },
	list_sites:               { category: 'readonly', risk: 'low', label: 'List Sites',                    desc: 'List Sites visible to caller' },
	list_sites_on_release_group: { category: 'readonly', risk: 'low', label: 'List Sites on RG',           desc: "Sites belonging to a specific Release Group (team-scoped)" },
	list_my_tokens:           { category: 'readonly', risk: 'low', label: 'List My Tokens',                desc: 'List your own MCP tokens' },
	app_git_status:           { category: 'readonly', risk: 'low', label: 'App — Git Status',              desc: 'Git branch / commit / dirty status for apps in a bench' },
	bench_recent_logs:        { category: 'readonly', risk: 'low', label: 'Bench — Recent Logs',           desc: 'Tail recent bench logs (frappe.log, error.log, etc.)' },
	site_db_processlist:      { category: 'readonly', risk: 'low', label: 'Site — DB Process List',        desc: 'MariaDB SHOW PROCESSLIST for the site DB' },
	deploy_failure_details:   { category: 'readonly', risk: 'low', label: 'Deploy — Failure Details',      desc: 'Inspect a failed Deploy Candidate Build' },
	bench_deploy_information: { category: 'readonly', risk: 'low', label: 'Bench — Deploy Information',    desc: 'Pending updates / deploy candidate info for an RG' },
	bench_dev_info:           { category: 'readonly', risk: 'low', label: 'Bench — Dev Info',              desc: 'Bench dev connection info: server IP, SSH port, dev flag' },
	site_domains_list:        { category: 'readonly', risk: 'low', label: 'Site — Domains List',           desc: 'List domains attached to a site' },
	deploy_candidate_status:  { category: 'readonly', risk: 'low', label: 'Deploy — Candidate Status',     desc: 'Status of a Deploy Candidate Build OR Candidate' },
	site_status:              { category: 'readonly', risk: 'low', label: 'Site — Status',                 desc: 'Site bench + status + recent agent jobs' },
	agent_job_list:           { category: 'readonly', risk: 'low', label: 'Agent Jobs — List',             desc: 'List recent Agent Jobs filtered by site / status / window' },
	agent_job_traceback:      { category: 'readonly', risk: 'low', label: 'Agent Job — Traceback',         desc: 'One-shot diagnostic: returns status + output_tail + traceback_tail for an Agent Job. Use before deciding to restart anything.' },
	agent_health:             { category: 'readonly', risk: 'low', label: 'Agent — Health Verdict',         desc: 'Derive healthy/slow/stuck/no_activity verdict for an app server. Check BEFORE recommending an agent restart.' },
	wait_for_bench_flip:      { category: 'readonly', risk: 'low', label: 'Wait for Bench Flip',           desc: 'Async-style poll: returns flipped|pending|no_build|flip_not_triggered|flip_failed. Safety gates B/C/D/E embedded — never poll forever on a phantom build, skipped site_update, or rolled-back migrate.' },
	audit_verify_chain:       { category: 'readonly', risk: 'low', label: 'Audit — Verify Hash Chain',     desc: 'System-User-only: verify MCP Call Log hash chain' },
	bench_read_app_file:      { category: 'readonly', risk: 'low', label: 'Bench — Read App Source File',  desc: 'Read a file from apps/<app>/ inside the bench (1 MB cap, path-validated)' },
	bench_list_app_files:     { category: 'readonly', risk: 'low', label: 'Bench — List App Files',        desc: 'List files under apps/<app>/<dir>/ in the bench (optional glob pattern, capped at 200)' },
	bench_ssh_instructions:   { category: 'readonly', risk: 'low', label: 'Bench — SSH Instructions',      desc: 'Get SSH connection instructions for a bench (server/port/paths/do-and-dont). Does NOT grant access.' },
	bench_ssh_register_key:   { category: 'bench_rg', risk: 'medium', label: 'Bench — Register SSH Pubkey',  desc: 'Upload your SSH public key so bench_ssh_cert_generate can sign it. One-time setup, idempotent.' },

	// BENCH / RELEASE GROUP (medium risk)
	clone_bench:                            { category: 'bench_rg', risk: 'medium', label: 'Clone Bench',                          desc: 'Clone a Release Group on the same server with the same apps' },
	bench_deploy:                           { category: 'bench_rg', risk: 'medium', label: 'Bench — Deploy',                       desc: "Trigger a deploy for a Release Group's apps" },
	bench_deploy_and_wait:                  { category: 'bench_rg', risk: 'medium', label: 'Bench — Deploy and Wait',              desc: 'One-shot deploy + block until site flips to new candidate (or timeout)' },
	bench_set_app_branch:                   { category: 'bench_rg', risk: 'medium', label: 'Bench — Set App Branch',               desc: "Change an App Source's git branch before triggering a deploy" },
	bench_restart:                          { category: 'bench_rg', risk: 'medium', label: 'Bench — Restart',                      desc: 'Restart a Bench (gunicorn + workers)' },
	bench_update_config:                    { category: 'bench_rg', risk: 'medium', label: 'Bench — Update Config',                desc: 'Bulk-update bench common_site_config keys' },
	bench_ssh_cert_get:                     { category: 'bench_rg', risk: 'medium', label: 'Bench — Get SSH Certificate',          desc: 'Get the existing SSH certificate for a bench' },
	app_create_locally:                     { category: 'bench_rg', risk: 'medium', label: 'App — Create Locally',                 desc: 'Run `bench new-app` inside a bench container' },
	app_init_github:                        { category: 'bench_rg', risk: 'medium', label: 'App — Init GitHub Repo',               desc: 'Create a GitHub repo for an existing local app' },
	app_release_approve:                    { category: 'bench_rg', risk: 'medium', label: 'App Release — Approve',                desc: 'Approve a Draft App Release for inclusion in candidates' },
	release_group_create_deploy_candidate:  { category: 'bench_rg', risk: 'medium', label: 'Release Group — Create Deploy Candidate', desc: 'Create a new Deploy Candidate for a Release Group' },
	deploy_candidate_schedule_build:        { category: 'bench_rg', risk: 'medium', label: 'Deploy — Schedule Build',              desc: 'Schedule build + deploy for a Deploy Candidate' },

	// SITE LIFECYCLE (medium risk)
	clone_site:                  { category: 'site_lifecycle', risk: 'medium', label: 'Clone Site',                       desc: 'Clone a Site onto a target bench (3 modes)' },
	move_site_to_release_group:  { category: 'site_lifecycle', risk: 'medium', label: 'Move Site to Release Group',       desc: 'Move a Site to a different Release Group' },
	lock_acquire:                { category: 'site_lifecycle', risk: 'medium', label: 'Lock — Acquire',                   desc: 'Acquire an advisory lock on Site or Release Group' },
	lock_release:                { category: 'site_lifecycle', risk: 'medium', label: 'Lock — Release',                   desc: 'Release an advisory lock you hold' },
	site_migrate:                { category: 'site_lifecycle', risk: 'medium', label: 'Site — Migrate',                   desc: 'Run `bench --site X migrate` on the site' },
	site_backup:                 { category: 'site_lifecycle', risk: 'medium', label: 'Site — Backup',                    desc: 'Trigger a site backup' },
	site_install_app:            { category: 'site_lifecycle', risk: 'medium', label: 'Site — Install App',               desc: 'Install an app on a site' },
	site_activate:               { category: 'site_lifecycle', risk: 'medium', label: 'Site — Activate',                  desc: 'Activate a previously deactivated site' },
	site_add_domain:             { category: 'site_lifecycle', risk: 'medium', label: 'Site — Add Domain',                desc: 'Attach a custom domain to a site' },
	site_remove_domain:          { category: 'site_lifecycle', risk: 'medium', label: 'Site — Remove Domain',             desc: 'Detach a custom domain from a site' },
	site_set_host_name:          { category: 'site_lifecycle', risk: 'medium', label: 'Site — Set Host Name',             desc: 'Set the primary domain (host name) for a site' },
	site_schedule_update:        { category: 'site_lifecycle', risk: 'medium', label: 'Site — Schedule Update',           desc: 'Schedule a Site Update (migrate to latest bench)' },
	site_update_and_wait:        { category: 'site_lifecycle', risk: 'medium', label: 'Site — Update and Wait',           desc: 'One-shot site_update + block until site flips onto target_candidate (or timeout). Companion to bench_deploy_and_wait.' },
	revoke_my_token:             { category: 'site_lifecycle', risk: 'medium', label: 'Revoke My Token',                  desc: 'Revoke an MCP token by docname' },

	// FILE / CONFIG (medium risk)
	site_config_get:           { category: 'file_config', risk: 'medium', label: 'Site Config — Get',               desc: 'Read site_config.json keys (sensitive keys redacted)' },
	site_config_set:           { category: 'file_config', risk: 'medium', label: 'Site Config — Set Key',           desc: 'Set a single site_config.json key (no sensitive keys)' },
	site_file_read:            { category: 'file_config', risk: 'medium', label: 'Site File — Read',                desc: 'Read a file from public/files/ or private/files/' },
	site_file_write:           { category: 'file_config', risk: 'medium', label: 'Site File — Write',               desc: 'Write a file to public/files/ or private/files/' },
	site_update_config_bulk:   { category: 'file_config', risk: 'medium', label: 'Site Config — Bulk Update',       desc: 'Bulk-update site_config.json keys (Press internal allow-list)' },

	// DANGEROUS (high risk — requires risky_tools_enabled=true on token)
	site_run_python:           { category: 'dangerous', risk: 'high', label: 'Site — Run Python (RCE)',         desc: 'Run a Python snippet on a site (full power, remote code execution)' },
	site_run_sql:              { category: 'dangerous', risk: 'high', label: 'Site — Run SQL',                  desc: 'Run SQL on the site database (default read-only; commit=true for writes)' },
	app_git_push:              { category: 'dangerous', risk: 'high', label: 'App — Git Push to GitHub',        desc: 'Commit + push an app to GitHub from inside the bench' },
	site_uninstall_app:        { category: 'dangerous', risk: 'high', label: 'Site — Uninstall App',            desc: 'Uninstall an app from a site' },
	site_deactivate:           { category: 'dangerous', risk: 'high', label: 'Site — Deactivate',               desc: 'Deactivate a site (maintenance mode)' },
	bench_update:              { category: 'dangerous', risk: 'high', label: 'Bench — Update',                  desc: 'Update a Bench to the latest deploy' },
	site_update:               { category: 'dangerous', risk: 'high', label: 'Site — Update',                   desc: 'Update a site to the latest bench deploy' },
	bench_ssh_cert_generate:   { category: 'dangerous', risk: 'high', label: 'Bench — Generate SSH Certificate', desc: 'Generate SSH cert (grants shell access to bench)' },
	bench_update_dependencies: { category: 'dangerous', risk: 'high', label: 'Bench — Update Dependencies',     desc: 'Update bench dependency versions (Python / Node / etc)' },
	bench_run_repo_script:     { category: 'dangerous', risk: 'high', label: 'Bench — Run Repo Script',         desc: 'Fetch + run a Python script from an allowlisted GitHub repo' },
};

// All tool names sorted alphabetically — useful for stable iteration
export const ALL_TOOLS = Object.keys(TOOL_CATALOG).sort();

// Preset bundles: name → list of tool names. Used by the preset buttons.
export const PRESETS = {
	'Read-only': ALL_TOOLS.filter((t) => TOOL_CATALOG[t].risk === 'low'),
	'Standard agent': [
		'list_release_groups', 'list_sites', 'list_my_tokens',
		'site_status', 'lock_status', 'agent_job_list',
		'clone_site', 'lock_acquire', 'lock_release',
		'site_migrate', 'site_backup',
	],
	'All clone': ['clone_bench', 'clone_site'],
	'All deploy': [
		'app_release_approve', 'release_group_create_deploy_candidate',
		'deploy_candidate_schedule_build', 'deploy_candidate_status',
		'site_schedule_update', 'wait_for_bench_flip', 'site_status',
		'agent_job_list', 'bench_deploy_information', 'bench_deploy',
	],
};

// Risk -> display style helper used by the dialog
export function riskBadgeClass(risk) {
	if (risk === 'high') return 'inline-flex items-center rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-800';
	if (risk === 'medium') return 'inline-flex items-center rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800';
	return 'inline-flex items-center rounded-full bg-green-100 px-1.5 py-0.5 text-[10px] font-medium text-green-800';
}

export function categoryBorderClass(tone) {
	if (tone === 'red') return 'border-red-200 bg-red-50/30';
	if (tone === 'amber') return 'border-amber-200 bg-amber-50/30';
	if (tone === 'blue') return 'border-blue-200 bg-blue-50/30';
	if (tone === 'green') return 'border-green-200 bg-green-50/30';
	return 'border-gray-200';
}

// Friendly tool label for a single tool name. Falls back to the raw name for
// unknown tools (older logs / forward-compatible with new tools added server-side).
export function toolLabel(toolName) {
	if (!toolName) return '';
	return TOOL_CATALOG[toolName]?.label || toolName;
}

// Format a scope array for display in token list rows.
// Returns 'all' for empty scope, otherwise comma-separated friendly labels.
export function formatScope(scope) {
	if (!scope || !scope.length) return 'all';
	return scope.map(toolLabel).join(', ');
}
