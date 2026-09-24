"""Resolve which Site or Release Group an MCP call acts on.

Moved unchanged out of press/mcp_server/server.py so the scoping rules live in one
reviewable place; server.py re-imports every name, so callers and tests are unaffected.
"""

from __future__ import annotations

import frappe


# Common arg-name aliases. LLM clients routinely guess the natural short name
# ('site', 'bench') or a generic 'name' instead of the catalog's canonical name
# ('site_name', 'bench_name', 'dn'). Without normalization every such call
# rejects with "missing required args", the agent calls help, then retries —
# wasted round-trips that read as the agent stalling mid-task. We rewrite an
# alias to its canonical name ONLY when the tool's schema declares the canonical
# arg AND the caller did not already pass it, so tools that legitimately use
# 'site'/'name' (clone_site, bench_deploy, agent_job_list) stay untouched.
_GLOBAL_ARG_ALIASES: dict[str, tuple[str, ...]] = {
	"site_name": ("site", "sitename", "site_url", "fqdn"),
	"bench_name": ("bench", "benchname"),
	"release_group": ("rg", "group", "release_group_name"),
	"query": ("sql",),
	"public_key": ("pubkey", "ssh_key", "ssh_public_key"),
}
# Canonical resource identifiers a bare 'name' might mean. When a tool does NOT
# declare 'name' but declares exactly one of these (and it's missing), a sent
# 'name' is rewritten to it (covers deploy_failure_details wanting 'dn',
# site_* tools wanting 'site_name', etc.). If 2+ candidates match we leave it
# alone and let validation surface the canonical names.
_NAME_FALLBACK_CANONICALS: tuple[str, ...] = (
	"site_name", "bench_name", "dn", "release_group", "candidate_name", "dc_name",
)


def _normalize_arg_aliases(spec: dict, args: dict) -> dict:
	"""Rewrite common arg-name aliases to the tool's canonical arg names."""
	if not isinstance(args, dict):
		return args
	props = set(spec.get("args_schema", {}).get("properties", {}).keys())
	if not props:
		return args
	out = dict(args)
	for canon, aliases in _GLOBAL_ARG_ALIASES.items():
		if canon in props and canon not in out:
			for alias in aliases:
				if alias in out:
					out[canon] = out.pop(alias)
					break
	if "name" in out and "name" not in props:
		candidates = [c for c in _NAME_FALLBACK_CANONICALS if c in props and c not in out]
		if len(candidates) == 1:
			out[candidates[0]] = out.pop("name")
	return out


def _extract_target(tool: str, args: dict) -> tuple[str | None, str | None]:
	"""Map tool args → (target_doctype, target_name) for resource-scope checks.

	Returns (None, None) for tools that don't operate on a single resource.
	"""
	# Lock-style tools have explicit target_doctype/target_name args
	if "target_doctype" in args and "target_name" in args:
		td = args.get("target_doctype")
		if td in ("Site", "Release Group"):
			return td, args.get("target_name")

	# Site-targeted tools — arg name varies between site, name, site_name
	site = args.get("site") or args.get("site_name")
	if tool in {
		"clone_site",
		"move_site_to_release_group",
		"site_migrate",
		"site_backup",
		"site_install_app",
		"site_uninstall_app",
		"site_activate",
		"site_deactivate",
		"site_update",
		"site_run_python",
		"site_run_sql",
		"site_db_processlist",
		"site_config_get",
		"site_config_set",
		"site_file_read",
		"site_file_write",
		"site_domains_list",
		"site_add_domain",
		"site_remove_domain",
		"site_set_host_name",
		"site_update_config_bulk",
		# Obj 10
		"site_schedule_update",
		"site_status",
		"wait_for_bench_flip",
		# Obj 11: *_and_wait wrappers. Without these the fail-closed guard
		# _assert_target_extracted blocks them outright.
		"site_update_and_wait",
		# Restores INTO an existing site, so the site is the written resource.
		# site_create is RG-scoped instead: its site does not exist yet.
		"site_restore",
	}:
		# api/site.py methods take 'name'; bench_dev_overview methods take 'site_name'
		site = site or args.get("name")
		if site:
			return "Site", site

	# agent_job_list takes an OPTIONAL site filter. When present, scope-check
	# it. When absent, the tool is effectively team-scoped — falls through to
	# RESOURCELESS handling below. SECURITY (2026-05-10): previously listed in
	# RESOURCELESS_TOOLS, which let a token scoped to site-A enumerate jobs
	# for site-B by passing {"site": "site-B"} (information disclosure).
	if tool == "agent_job_list":
		filter_site = args.get("site")
		if filter_site:
			return "Site", filter_site
		# No site filter → fall through; agent_job_list is in RESOURCELESS_TOOLS
		# for the no-filter case (handled below). When no site arg, the tool's
		# backend filters by the caller's team via Frappe perm.
		return None, None

	# Release-Group-targeted tools — arg name varies
	rg = args.get("release_group") or args.get("name")
	if tool in {
		"clone_bench",
		"bench_deploy",
		"bench_deploy_information",
		"bench_update_config",
		"bench_update_dependencies",
		# Obj 10
		"release_group_create_deploy_candidate",
		# Bench-control surface (name = Release Group docname)
		"release_group_add_app",
		"release_group_remove_app",
		"release_group_list_branches",
		"release_group_versions",
		"release_group_installable_apps",
		"release_group_rename",
		"release_group_redeploy",
		"release_group_archive",
		# Obj 11: scoped to the Release Group being deployed, matching
		# bench_deploy. bench_deploy_and_wait also takes site_name, but that
		# site is only polled for the flip -- the RG is the written resource.
		"bench_deploy_and_wait",
		"list_sites_on_release_group",
		# Takes release_group; was never mapped, so the guard rejected it.
		"bench_set_app_branch",
		# Scoped to the Release Group the site lands on: the site does not exist
		# yet, so there is no Site resource to scope against.
		"site_create",
	}:
		if rg:
			return "Release Group", rg

	# Bench-targeted tools: bench_name → parent Release Group via DB lookup.
	# Token RG allowlist applies to the parent RG of the bench.
	# bench_restart / bench_update take the Bench docname as 'name' (per
	# tools.py required_args); accept name here so the docname resolves to
	# its parent RG instead of being mistaken for a Release Group name.
	bench_name = args.get("bench_name") or args.get("name")
	if bench_name and tool in {
		"bench_restart",
		"bench_update",
		"app_git_status",
		"app_git_push",
		"app_create_locally",
		"app_init_github",
		"bench_recent_logs",
		"bench_ssh_cert_get",
		"bench_ssh_cert_generate",
		"bench_ssh_connect",
		"bench_ssh_instructions",  # SECURITY (2026-05-10): previously missing; leaked SSH paths cross-RG
		"bench_read_app_file",     # SECURITY (2026-05-10): previously missing; allowed cross-RG source-file reads
		"bench_list_app_files",    # SECURITY (2026-05-10): previously missing; allowed cross-RG file listings
		"bench_dev_info",
		"bench_provision_progress",
		# Obj 10
		"bench_run_repo_script",
		# Bench-control surface (name = Bench docname)
		"bench_rebuild_assets",
	}:
		parent_rg = frappe.db.get_value("Bench", bench_name, "group")
		if parent_rg:
			return "Release Group", parent_rg

	# Deploy Candidate / Build → resolve to parent Release Group (Obj 10).
	# SECURITY (2026-05-10): deploy_failure_details added — was previously in
	# RESOURCELESS_TOOLS, letting tokens scoped to one RG read failed-build
	# stdout/stderr (which can contain secrets) for builds in other RGs.
	if tool in {
		"deploy_candidate_schedule_build",
		"deploy_candidate_status",
		"deploy_failure_details",
	}:
		candidate_or_build = args.get("candidate_name") or args.get("name") or args.get("dn")
		if candidate_or_build:
			rg = _candidate_to_release_group(candidate_or_build)
			if rg:
				return "Release Group", rg

	# Agent Job → the Site it ran against, falling back to the bench's
	# parent Release Group for bench-level jobs. SECURITY: scoping these
	# matters -- job output and tracebacks can carry site detail, so a
	# token scoped to site-A must not read site-B's job.
	if tool in {
		"agent_job_progress",
		"agent_job_traceback",
	}:
		job = args.get("name") or args.get("job_name") or args.get("dn")
		if job:
			row = frappe.db.get_value("Agent Job", job, ["site", "bench"], as_dict=True)
			if row:
				if row.get("site"):
					return "Site", row["site"]
				if row.get("bench"):
					parent_rg = frappe.db.get_value("Bench", row["bench"], "group")
					if parent_rg:
						return "Release Group", parent_rg

	return None, None


# Tools that legitimately do NOT operate on a single Site/Release Group/Bench
# resource — global listings, token self-management, audit. Resource-scope
# checks are skipped for these by design (no target to compare allowlist to).
# CRITICAL: any tool that takes a bench_name/site/release_group/name arg
# MUST be in _extract_target above. The fail-closed guard
# `_assert_target_extracted` enforces this — adding a tool here that DOES
# carry a resource argument allows scope bypass.
RESOURCELESS_TOOLS: set[str] = {
	"help",
	"list_tools",
	"list_release_groups",  # backend handler filters by caller's team
	"list_sites",           # backend handler filters by caller's team
	"list_my_tokens",
	"revoke_my_token",
	"audit_verify_chain",
	# bench_ssh_register_key registers a SSH pubkey on the calling USER (one-time
	# setup). Doesn't operate on any bench — the cert sign step (bench_ssh_cert_*)
	# is what enforces bench scope.
	"bench_ssh_register_key",
	# agent_job_list IS resource-scoped when its `site` arg is set — see
	# _extract_target's special-case for that. This allowlist entry covers
	# the fall-through case where no site is specified (team-scoped via
	# Frappe perm).
	"agent_job_list",
	"app_release_approve",  # app-scoped, not RG/Site-scoped
	"app_source_fetch_latest",  # app-scoped via App Source.team
	"list_pending_releases",    # filtered by app/source/RG in handler
	"register_existing_app",    # creates new App Source for current team
	# Creates a brand-new Release Group — no pre-existing resource to scope to.
	# Server-side new() still gates on team.enabled + server ownership. Its args
	# (title/version/new_apps/cluster/server/saas_app) deliberately avoid the
	# _RESOURCE_ARG_NAMES set so the fail-closed guard doesn't trip.
	"release_group_create",
}

# Argument names that, when present, indicate the tool operates on a specific
# resource. If any of these are in args but _extract_target returned (None, None)
# AND the tool is not in RESOURCELESS_TOOLS, we fail closed.
_RESOURCE_ARG_NAMES: set[str] = {
	"bench_name",
	"site",
	"site_name",
	"release_group",
	"name",          # ambiguous (could be doc name in any DocType) but worth checking
	"target_name",
	"dn",            # Deploy Candidate Build name; backstops deploy_failure_details
	"candidate_name",
}


def _assert_target_extracted(
	tool: str,
	args: dict,
	target_doctype: str | None,
	target_name: str | None,
) -> None:
	"""Fail-closed guard: catch tools registered without _extract_target mapping.

	Background: prior bug (2026-05-10) — bench_list_app_files / bench_read_app_file
	/ bench_ssh_register_key / bench_ssh_instructions accepted bench_name args
	but were missing from _extract_target. _check_resource_scope was skipped,
	letting tokens with `allowed_release_groups: [bench-A]` read files from
	bench-B unbounded.

	If any future tool ships with a resource arg but no _extract_target entry,
	this function blocks the call instead of silently authorizing it.
	"""
	if target_doctype and target_name:
		return  # extraction worked — proceed to verify_token's scope check
	if tool in RESOURCELESS_TOOLS:
		return  # explicitly safe (no resource to check)
	# Extraction returned (None, None) AND tool isn't allowlisted as resourceless.
	# If it carries a resource arg, that's a bug.
	leaks = sorted(_RESOURCE_ARG_NAMES & set(args.keys()))
	if leaks:
		# Blame the caller FIRST. The overwhelmingly common cause is a resource arg the
		# tool does not declare (passing release_group to a tool whose required_args is
		# ["bench_name"]), and the old wording sent people to patch _extract_target for
		# a mapping that was already correct. Only mention the server after ruling that
		# out. Cost of the old message: two tools written off as broken for a week.
		from press.mcp_server.tools import TOOLS

		expected = TOOLS.get(tool, {}).get("required_args", [])
		unexpected = [a for a in leaks if a not in expected]
		if unexpected and expected:
			# Caller error: an arg the tool does not declare. Say so first, and do not
			# name the server internals until the end.
			raise frappe.PermissionError(
				f"tool {tool!r} was called with resource argument(s) {unexpected!r} that it "
				f"does not declare; it expects {expected!r}. Retry with the declared "
				f"argument. The call is refused rather than run unscoped. If the arguments "
				f"ARE the declared ones, then {tool!r} is genuinely missing from "
				f"_extract_target / RESOURCELESS_TOOLS in press/mcp_server/server.py."
			)
		# NOTE: test_assert_target_extracted_fails_closed_on_unmapped_resource_tool asserts
		# on the phrase "missing from _extract_target". Keep it.
		raise frappe.PermissionError(
			f"tool {tool!r} carries resource argument(s) {leaks!r} that could not be resolved "
			f"to a Site or Release Group, so the call is refused rather than run unscoped. "
			f"{tool!r} is missing from _extract_target — add it to the matching set there, or "
			f"to RESOURCELESS_TOOLS if it genuinely owns no resource "
			f"(press/mcp_server/server.py)."
		)
	# No resource args at all — tool genuinely operates on nothing scopable.
	# Add it to RESOURCELESS_TOOLS to silence this check on next deploy if
	# you encounter it intentionally.


def _candidate_to_release_group(name: str) -> str | None:
	"""Resolve a Deploy Candidate Build or Deploy Candidate name to its RG.

	Fail-closed: if the name resolves to a Build whose `deploy_candidate` is
	null (orphaned mid-create), raise rather than returning None — silent None
	would skip the resource-scope check at the dispatch layer.
	"""
	build_row = frappe.db.get_value(
		"Deploy Candidate Build",
		name,
		["name", "deploy_candidate"],
		as_dict=True,
	)
	if build_row is not None:
		if not build_row.deploy_candidate:
			frappe.throw(
				f"Deploy Candidate Build {name!r} has no linked candidate; "
				"cannot enforce resource scope.",
				frappe.ValidationError,
			)
		return frappe.db.get_value(
			"Deploy Candidate", build_row.deploy_candidate, "group"
		)
	# Maybe the name IS a Deploy Candidate
	return frappe.db.get_value("Deploy Candidate", name, "group")
