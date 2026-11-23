# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Catalog part: bench and site lifecycle, SSH access, site config, site files, domains and bench config. Merged into press/mcp_server/tools.py TOOLS (split 0.7.54)."""

from __future__ import annotations

from press.mcp_server.tool_catalog._schema import _schema

SITES_BENCHES_TOOLS: dict[str, dict] = {
	# Bench / Release Group lifecycle
	"bench_deploy": {
		"method": "press.api.bench.deploy",
		"description": "Trigger a deploy for a Release Group. Args: name (Release Group docname, e.g. 'bench-0005'); apps (list of DICTS, NOT strings — each item {app, release, hash}). Get release+hash from bench_deploy_information(name).apps[*].releases[0]. Returns the Deploy Candidate docname — pass it to wait_for_bench_flip's target_candidate.",
		"required_args": ["name", "apps"],
		"args_schema": _schema(["name", "apps"]),
		"risk": "medium",
	},
	"bench_deploy_information": {
		"method": "press.api.bench.deploy_information",
		"description": "Get deploy candidate / pending updates info for a Release Group",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "low",
	},
	"bench_restart": {
		"method": "press.api.bench.restart",
		"description": "Restart a Bench (gunicorn + workers)",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "medium",
	},
	"bench_update": {
		"method": "press.api.bench.update",
		"description": "Update a Bench to the latest deploy",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "high",
	},
	# Site lifecycle
	"site_migrate": {
		"method": "press.api.site.migrate",
		"description": "Run `bench --site X migrate` on the site",
		"required_args": ["name"],
		"args_schema": _schema(["name"],
			{"skip_failing_patches": {"type": "boolean",
				"description": "Skip patches that fail during migration (not recommended)"}}),
		"risk": "medium",
	},
	"site_backup": {
		"method": "press.api.site.backup",
		"description": "Trigger a site backup. Note: this endpoint does NOT take an `offsite` flag — site backups via this API are always local + offsite per the team's configured backup schedule. For an explicit offsite-only backup, use Site.backup() directly via console.",
		"required_args": ["name"],
		"args_schema": _schema(["name"],
			{
				"with_files": {"type": "boolean", "description": "Include public + private files in the backup"},
			}),
		"risk": "medium",
	},
	"site_install_app": {
		"method": "press.api.site.install_app",
		"description": "Install an app on a site",
		"required_args": ["name", "app"],
		"args_schema": _schema(["name", "app"]),
		"risk": "medium",
	},
	"site_uninstall_app": {
		"method": "press.api.site.uninstall_app",
		"description": "Uninstall an app from a site",
		"required_args": ["name", "app"],
		"args_schema": _schema(["name", "app"]),
		"risk": "high",
	},
	"site_activate": {
		"method": "press.api.site.activate",
		"description": "Activate a previously deactivated site",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "medium",
	},
	"site_deactivate": {
		"method": "press.api.site.deactivate",
		"description": "Deactivate a site (puts it in maintenance mode)",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "high",
	},
	"site_update": {
		"method": "press.mcp_server.deploy_flow.site_update_with_hint",
		"description": "Update a site to the latest bench deploy. Wraps press.api.site.update with pre-flight checks. If no newer Deploy Candidate exists yet, returns {ok:false, reason:'no_destination_candidate', hint:'...'} instead of throwing the misleading 'Could not find suitable Destination Bench' error. Args: name (site FQDN). Optional: skip_failing_patches (bool).",
		"required_args": ["name"],
		"args_schema": _schema(["name"], {
			"skip_failing_patches": {"type": "boolean",
				"description": "Skip failing patches during migrate (default false)"},
		}),
		"risk": "high",
	},
	# SSH access (cert generation lets agents SSH into bench container)
	"bench_ssh_cert_get": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_ssh_certificate",
		"description": "Get the existing SSH certificate for a bench (returns None if not yet generated)",
		"required_args": ["bench_name"],
		"args_schema": _schema(["bench_name"]),
		"risk": "medium",
	},
	"bench_ssh_cert_generate": {
		"method": "press.press.doctype.bench.bench_dev_overview.generate_ssh_certificate",
		"description": "Generate an SSH certificate for a bench so the agent can SSH into the bench container",
		"required_args": ["bench_name"],
		"args_schema": _schema(["bench_name"]),
		"risk": "high",
	},
	"bench_dev_info": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_bench_dev_info",
		"description": "Get bench dev connection info: server IP, SSH port, is_development_bench flag",
		"required_args": ["bench_name"],
		"args_schema": _schema(["bench_name"]),
		"risk": "low",
	},
	# Site config (medium-risk — structured replacement for site_run_python config edits)
	"site_config_get": {
		"method": "press.mcp_server.file_ops.site_config_get",
		"description": "Read site_config.json keys (sensitive keys redacted)",
		"required_args": ["site_name"],
		"args_schema": _schema(["site_name"]),
		"risk": "medium",
	},
	"site_config_set": {
		"method": "press.mcp_server.file_ops.site_config_set",
		"description": "Set a single site_config.json key (sensitive keys forbidden)",
		"required_args": ["site_name", "key", "value"],
		"args_schema": _schema(["site_name", "key", "value"]),
		"risk": "medium",
	},
	# File ops (medium-risk — constrained to public/private folders)
	"site_file_read": {
		"method": "press.mcp_server.file_ops.site_file_read",
		"description": "Read a file from the site's public/files/ or private/files/ folder",
		"required_args": ["site_name", "relative_path"],
		"args_schema": _schema(["site_name", "relative_path"]),
		"risk": "medium",
	},
	"site_file_write": {
		"method": "press.mcp_server.file_ops.site_file_write",
		"description": "Write a file to the site's public/files/ or private/files/ folder",
		"required_args": ["site_name", "relative_path", "content"],
		"args_schema": _schema(["site_name", "relative_path", "content"]),
		"risk": "medium",
	},
	# Domains (Obj 8)
	"site_domains_list": {
		"method": "press.api.site.domains",
		"description": "List domains attached to a site",
		"required_args": ["name"],
		"args_schema": _schema(["name"]),
		"risk": "low",
	},
	"site_add_domain": {
		"method": "press.api.site.add_domain",
		"description": "Attach a custom domain to a site",
		"required_args": ["name", "domain"],
		"args_schema": _schema(["name", "domain"]),
		"risk": "medium",
	},
	"site_remove_domain": {
		"method": "press.api.site.remove_domain",
		"description": "Detach a custom domain from a site",
		"required_args": ["name", "domain"],
		"args_schema": _schema(["name", "domain"]),
		"risk": "medium",
	},
	"site_set_host_name": {
		"method": "press.api.site.set_host_name",
		"description": "Set the primary domain (host name) for a site",
		"required_args": ["name", "domain"],
		"args_schema": _schema(["name", "domain"]),
		"risk": "medium",
	},
	"site_update_config_bulk": {
		"method": "press.api.site.update_config",
		"description": "Bulk-update site_config.json keys (passes through Press's update_config — uses Press internal allow-list)",
		"required_args": ["name", "config"],
		"args_schema": _schema(["name", "config"]),
		"risk": "medium",
	},
	# Bench config (Obj 8)
	"bench_update_config": {
		"method": "press.api.bench.update_config",
		"description": "Bulk-update bench common_site_config keys",
		"required_args": ["name", "config"],
		"args_schema": _schema(["name", "config"]),
		"risk": "medium",
	},
	"bench_update_dependencies": {
		"method": "press.api.bench.update_dependencies",
		"description": "Update bench dependency versions (Python/Node/etc) — triggers rebuild",
		"required_args": ["name", "dependencies"],
		"args_schema": _schema(["name", "dependencies"]),
		"risk": "high",
	},
}
