# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Catalog part: git, running code inside a bench container, logs and diagnostics. Merged into press/mcp_server/tools.py TOOLS (split 0.7.54)."""

from __future__ import annotations

from press.mcp_server.tool_catalog._schema import _schema

BENCH_CODE_TOOLS: dict[str, dict] = {
	# Git ops
	"app_git_status": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_app_git_status",
		"description": "Get git branch/commit/dirty status for apps in a bench (per-site)",
		"required_args": ["bench_name"],
		"args_schema": _schema(["bench_name"],
			{"site_name": None}),
		"risk": "low",
	},
	"app_git_push": {
		"method": "press.press.doctype.bench.bench_dev_overview.push_app_to_github",
		"description": "Commit + push an app's working tree to GitHub from inside the bench container",
		"required_args": ["bench_name", "app", "message"],
		"args_schema": _schema(["bench_name", "app", "message"]),
		"risk": "high",
	},
	"app_create_locally": {
		"method": "press.press.doctype.bench.bench_app_management.create_app_locally",
		"description": "Run `bench new-app` inside a bench container",
		"required_args": ["bench_name", "app_name", "app_title"],
		"args_schema": _schema(["bench_name", "app_name", "app_title"]),
		"risk": "medium",
	},
	"app_init_github": {
		"method": "press.press.doctype.bench.bench_app_management.init_github_for_app",
		"description": "Create a GitHub repo for an existing local app and register it in Press",
		"required_args": ["bench_name", "app_name", "github_owner"],
		"args_schema": _schema(["bench_name", "app_name", "github_owner"]),
		"risk": "medium",
	},
	# Console / shell (run code inside bench container)
	"site_run_python": {
		"method": "press.press.doctype.bench.bench_dev_overview.run_python_on_site",
		"description": "Run a Python snippet on a site in the bench console (full power, system-manager only)",
		"required_args": ["site_name", "code"],
		"args_schema": _schema(["site_name", "code"]),
		"risk": "high",
	},
	"site_run_sql": {
		"method": "press.press.doctype.bench.bench_dev_overview.run_sql_on_site",
		"description": "Run SQL on the site database (default read-only; commit=true for writes)",
		"required_args": ["site_name", "query"],
		"args_schema": _schema(["site_name", "query"],
			{"commit": {"type": "boolean", "description": "Allow writes (INSERT/UPDATE/DELETE/DDL). Default false (read-only)."}}),
		"risk": "high",
	},
	# Logs + diagnostics
	"bench_recent_logs": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_recent_logs",
		"description": "Tail recent bench logs (frappe.log, scheduler.log, error.log, etc.)",
		"required_args": ["bench_name"],
		"args_schema": _schema(["bench_name"],
			{
				"log_type": {"type": "string", "description": "Log file name, e.g. 'frappe.log', 'scheduler.log', 'error.log'"},
				"limit": {"type": "integer", "minimum": 1, "maximum": 5000,
					"description": "Number of trailing lines to return (default 200, max 5000)"},
			}),
		"risk": "low",
	},
	"site_db_processlist": {
		"method": "press.press.doctype.bench.bench_dev_overview.get_db_processlist",
		"description": "MariaDB SHOW PROCESSLIST for the site DB",
		"required_args": ["site_name"],
		"args_schema": _schema(["site_name"]),
		"risk": "low",
	},
	"deploy_failure_details": {
		"method": "press.press.doctype.deploy_candidate_build.build_diagnostics.get_failure_details",
		"description": "Inspect a failed Deploy Candidate Build (failed step, stage, output)",
		"required_args": ["dn"],
		"args_schema": _schema(["dn"]),
		"risk": "low",
	},
}
