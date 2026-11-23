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
from press.mcp_server.tool_catalog.deploy import DEPLOY_TOOLS


# Tool name -> spec
TOOLS: dict[str, dict] = {
	**CORE_TOOLS,
	**BENCH_CODE_TOOLS,
	**SITES_BENCHES_TOOLS,
	**DEPLOY_TOOLS,
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
