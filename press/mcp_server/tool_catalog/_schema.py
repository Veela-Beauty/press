# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""The shared argument schemas of the MCP tool catalog: one JSON Schema fragment per common argument, and
_schema() that builds a tool's args_schema from them (moved from tools.py in 0.7.54)."""

from __future__ import annotations

# Reusable JSON Schema fragments for args that appear across many tools.
# Reference these via _S("site_name") etc. when building per-tool schemas to
# keep arg descriptions consistent and the file scannable.
_ARG_FRAGMENTS: dict[str, dict] = {
	"site_name": {"type": "string", "description": "Site name (FQDN), e.g. 'example.sandbox.mvpstorm.com'"},
	"site": {"type": "string", "description": "Site name (FQDN), e.g. 'example.sandbox.mvpstorm.com'"},
	"bench_name": {"type": "string", "description": "Bench docname, e.g. 'bench-0011-000187-press-f1'"},
	"release_group": {"type": "string", "description": "Release Group docname"},
	"target_bench": {"type": "string", "description": "Target Bench docname to host the cloned/moved site"},
	"target_release_group": {"type": "string", "description": "Destination Release Group docname"},
	"new_subdomain": {"type": "string", "description": "Subdomain for the new site (without the root domain)"},
	"new_title": {"type": "string", "description": "Display title for the new doc"},
	"name": {"type": "string", "description": "Primary docname for the target object"},
	"target_doctype": {"type": "string", "enum": ["Site", "Release Group", "Bench"],
		"description": "DocType the lock targets"},
	"target_name": {"type": "string", "description": "Docname the lock targets (matches target_doctype)"},
	"reason": {"type": "string", "description": "Free-text reason; appears in audit log"},
	"token_id": {"type": "string", "description": "Press MCP Token docname"},
	"app": {"type": "string", "description": "App name, e.g. 'erpnext', 'frappe', 'press'"},
	"app_name": {"type": "string", "description": "App name (lowercase, underscores)"},
	"app_title": {"type": "string", "description": "Human-readable app title"},
	"github_owner": {"type": "string", "description": "GitHub user or org name that will own the new repo"},
	"message": {"type": "string", "description": "Git commit message"},
	"code": {"type": "string", "description": "Python source to execute in the site's bench console"},
	"query": {"type": "string", "description": "SQL query string. Default is read-only — pass commit=true to allow writes."},
	"dn": {"type": "string", "description": "Deploy Candidate Build docname (sometimes called 'dcb name')"},
	"apps": {
		"type": "array",
		"items": {
			"type": "object",
			"properties": {
				"app": {"type": "string", "description": "App name, e.g. 'accubuild_core'"},
				"release": {"type": "string", "description": "App Release docname (from bench_deploy_information next_release)"},
				"hash": {"type": "string", "description": "Commit hash for that release (from bench_deploy_information releases[].hash)"},
			},
			"required": ["app", "release", "hash"],
		},
		"description": "List of {app, release, hash} dicts. Get release+hash from bench_deploy_information(name).apps[*].releases[0] or .next_release + matching releases[] entry. NOT a flat list of app names — each entry must be a dict.",
	},
	"domain": {"type": "string", "description": "Custom domain name, e.g. 'app.example.com'"},
	"config": {"type": "object", "description": "Dict of config keys → values to merge"},
	"key": {"type": "string", "description": "site_config.json key to set"},
	"value": {"description": "Value for the site_config.json key (string/number/bool — type matches the key)"},
	"relative_path": {"type": "string", "description": "Path relative to the site's public/files or private/files folder"},
	"content": {"type": "string", "description": "File content to write (UTF-8)"},
	"dependencies": {"type": "object", "description": "Dict of dependency name → version"},
	"release_name": {"type": "string", "description": "App Release docname"},
	"candidate_name": {"type": "string", "description": "Deploy Candidate docname"},
	"target_candidate": {"type": "string", "description": "Deploy Candidate to wait for the site to flip onto"},
	"repo": {"type": "string", "description": "GitHub repo in 'owner/name' form (must be in the allowlist)"},
	"branch": {"type": "string", "description": "Git branch or commit SHA"},
	"script_path": {"type": "string", "description": "Repo-relative path to the Python script to execute"},
	"public_key": {"type": "string", "description": "OpenSSH-format public key (e.g. 'ssh-ed25519 AAAA... user@host')"},
	"server": {"type": "string", "description": "App server docname, e.g. 'press-f1.sandbox.mvpstorm.com'"},
	"job_name": {"type": "string", "description": "Agent Job docname (10-char ID), e.g. 'jqc727far7'"},
	"app_source": {"type": "string", "description": "App Source docname (e.g. 'SRC-frappe_theme_switcher-001')"},
	"repository_url": {"type": "string", "description": "GitHub repository URL (https://github.com/owner/repo) or owner/repo shorthand"},
	"force": {"type": "boolean", "description": "Bypass safety checks (e.g. last_github_poll_failed flag)"},
	"team": {"type": "string", "description": "Team docname (defaults to current team)"},
	"limit": {"type": "integer", "minimum": 1, "maximum": 200, "description": "Max rows to return"},
	"source": {"type": "string", "description": "App Source docname to add to the group (e.g. 'SRC-erpnext-001')"},
	"title": {"type": "string", "description": "Release Group display title"},
	"version": {"type": "string", "description": "Frappe version, e.g. 'Version 15'"},
	"cluster": {"type": "string", "description": "Cluster docname, e.g. 'Default'"},
	"saas_app": {"type": "string", "description": "Saas App docname (optional; '' if none)"},
	"dc_name": {"type": "string", "description": "Deploy Candidate docname to redeploy from"},
	"new_apps": {
		"type": "array",
		"items": {
			"type": "object",
			"properties": {
				"name": {"type": "string", "description": "App name, e.g. 'erpnext'"},
				"source": {"type": "string", "description": "App Source docname for that app"},
			},
			"required": ["name", "source"],
		},
		"description": "Apps for the NEW Release Group: list of {name, source} dicts (note: 'name' here is the app name, not a release/hash).",
	},
}


def _schema(required: list[str], optional: dict | None = None) -> dict:
	"""Build a JSON Schema object for a tool from arg fragments.

	`required` lists arg names that must be present; their fragments come from
	_ARG_FRAGMENTS. `optional` is a {arg_name: schema_fragment_or_None} dict —
	pass None to reuse the shared fragment, or pass an inline dict for tool-specific
	args that don't appear elsewhere.
	"""
	props: dict[str, dict] = {}
	for arg in required:
		if arg not in _ARG_FRAGMENTS:
			raise KeyError(
				f"_schema: arg {arg!r} has no fragment in _ARG_FRAGMENTS — "
				f"add it there or pass an inline schema via optional"
			)
		props[arg] = _ARG_FRAGMENTS[arg]
	for arg, frag in (optional or {}).items():
		if frag is None:
			if arg not in _ARG_FRAGMENTS:
				raise KeyError(f"_schema: optional arg {arg!r} has no fragment — pass inline")
			props[arg] = _ARG_FRAGMENTS[arg]
		else:
			props[arg] = frag
	return {
		"type": "object",
		"properties": props,
		"required": list(required),
	}
