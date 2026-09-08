# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""MCP HTTP entry point. Single whitelisted method dispatches to tool wrappers.

Auth flow per call:
	1. Caller passes {tool, args, token}.
	2. verify_token(token, tool_name) -> User docname OR raises PermissionError.
	3. frappe.set_user(user) — underlying tool method runs as the human user,
	   so all team/role permission checks work transparently.
	4. Dispatch via the tool catalog. Log call to Press MCP Call Log.
"""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Any

import frappe
from frappe.utils import now_datetime

from press.mcp_server.auth import TOKEN_PREFIX_LEN, _authenticate_token, verify_token
from press.mcp_server.help import BUILTIN_TOOLS, DISCOVERABILITY_HINT, get_tool_help
from press.mcp_server.rate_limit import RateLimitError, check_rate_limit
from press.mcp_server.tools import get_tool_spec, get_tool_risk, list_tool_names

MAX_ARGS_LOG_LEN = 5000  # truncate long arg payloads in audit log

# Gate A — tools that can corrupt in-flight work if the agent is mid-job.
# These get refused when agent_health(server) verdict == 'slow' unless the
# caller passes args.force=true. The arg key used to find the bench/server.
_GATE_A_GUARDED_TOOLS: dict[str, str] = {
	# tool_name → arg_key holding the bench docname
	"bench_restart": "name",
	"bench_update": "name",
}


def _check_busy_worker_guard(tool: str, dispatch_args: dict) -> dict | None:
	"""Return a dict {server, error} if Gate A should refuse the call, else None.

	Best-effort: if anything in the check raises (bench not found, agent_health
	import fails, etc.), we allow the call through — guards must never break
	legitimate ops. The audit log captures both the refusal and the bypass.
	"""
	try:
		from press.mcp_server.deploy_flow import agent_health

		arg_key = _GATE_A_GUARDED_TOOLS[tool]
		bench_name = dispatch_args.get(arg_key)
		if not bench_name:
			return None
		server = frappe.db.get_value("Bench", bench_name, "server")
		if not server:
			return None
		verdict = agent_health(server=server, lookback_minutes=5)
		if verdict.get("verdict") == "slow":
			reason = verdict.get("reason", "agent is mid-job")
			running = verdict.get("running_jobs", [])
			running_summary = ", ".join(
				f"{j.get('job_type', '?')} ({j.get('age_seconds', '?')}s old)"
				for j in running[:3]
			)
			return {
				"server": server,
				"error": (
					f"Gate A refusal: {tool!r} blocked because {server!r} agent is "
					f"verdict='slow'. {reason} Running jobs: {running_summary}. "
					f"Restarting now would kill mid-flight work and may corrupt the "
					f"live DB. Pass args.force=true to override (audit-logged)."
				),
			}
	except Exception as e:  # noqa: BLE001 — guard must never block legitimate ops
		frappe.log_error(
			title=f"MCP Gate A: check failed for {tool}",
			message=f"args={dispatch_args} err={e}",
		)
	return None


@contextmanager
def _as_user(user: str):
	"""Run a block as `user`, then restore the previous session user.

	Guarantees restoration even on exception, mid-edit, or future refactor.
	"""
	original = frappe.session.user
	frappe.set_user(user)
	try:
		yield
	finally:
		frappe.set_user(original)


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


@frappe.whitelist(allow_guest=True)
def handle(tool: str, args: dict | str | None = None, token: str | None = None) -> dict[str, Any]:
	"""Single MCP entry point. Returns structured result.

	Returns:
		{ok: bool, data: any, error?: str, error_type?: str}
	"""
	args = _parse_args(args)
	start = time.perf_counter()
	user = None
	token_doc_name = None
	error_type = None
	error_msg = None
	response = None

	try:
		# Built-in discoverability tools (help / list_tools) — handled inline.
		# Still require a valid token (so anonymous callers can't enumerate),
		# but bypass the per-tool scope check and rate limit.
		if tool in BUILTIN_TOOLS:
			if not token:
				raise frappe.PermissionError("token is required")
			user, token_doc_name, caller_scope = _resolve_for_builtin(token)
			help_args = args if isinstance(args, dict) else {}
			response = get_tool_help(
				tool=help_args.get("tool"),
				category=help_args.get("category"),
				scope_only=bool(help_args.get("scope_only", True)),
				caller_scope=caller_scope,
			)
			_log_call(
				tool=tool, user=user, token_name=token_doc_name,
				args=args, response=response, status="Success",
				duration_ms=int((time.perf_counter() - start) * 1000),
			)
			return _wrap_success(response, args, tool=tool)

		spec = get_tool_spec(tool)
		if not spec:
			raise frappe.ValidationError(
				f"unknown tool {tool!r}; available: {list_tool_names()}. "
				f"Call {{tool: 'help'}} to see what your token can use."
			)

		if not token:
			raise frappe.PermissionError("token is required")

		# Rewrite common arg aliases (site→site_name, bench→bench_name, name→dn,
		# etc.) BEFORE scope extraction + validation, so an agent's natural guess
		# succeeds instead of round-tripping through a 'missing required args' error.
		args = _normalize_arg_aliases(spec, args)
		_coerce_config_arg(tool, args)

		target_doctype, target_name = _extract_target(tool, args)
		# SECURITY: fail-closed guard against missing _extract_target entries.
		# If the tool's args carry a known target identifier (bench_name/site/
		# release_group/name/site_name) but extraction returned (None, None),
		# the tool was registered without a resource-scope mapping. Block the
		# call instead of silently bypassing the token's allowed_release_groups
		# / allowed_sites allowlist.
		_assert_target_extracted(tool, args, target_doctype, target_name)
		user = verify_token(token, tool_name=tool, target_doctype=target_doctype, target_name=target_name)
		token_doc_name = _resolve_token_docname(token)

		# Rate limit per token (Obj 7)
		check_rate_limit(token_doc_name)

		# Validate required args present
		missing = [a for a in spec["required_args"] if a not in args]
		if missing:
			# Hint the caller at the canonical arg names AND whether they sent a
			# close miss (e.g. 'site' vs 'site_name', 'sql' vs 'query'). The most
			# common cause of "missing required args" is an LLM client inferring
			# a natural-language name from the description instead of the schema.
			sent = sorted(args.keys()) if isinstance(args, dict) else []
			hint = ""
			if sent:
				hint = (
					f" Got: {sent}. Expected: {spec['required_args']}. "
					f"For the full args_schema, call {{tool: 'help', args: {{tool: {tool!r}}}}}."
				)
			_track_rejection(token_doc_name, tool, "missing_required_args", str(missing))
			raise frappe.ValidationError(
				f"missing required args: {missing}.{hint}"
			)

		# Dry-run support for high-risk tools
		if args.get("dry_run") and get_tool_risk(tool) == "high":
			response = {
				"dry_run": True,
				"tool": tool,
				"would_execute_with_args": {k: v for k, v in args.items() if k != "dry_run"},
				"risk": "high",
				"warning": "this is a dry-run; no action was taken",
			}
			_log_call(
				tool=tool, user=user, token_name=token_doc_name,
				args=args, response=response, status="Success",
				duration_ms=int((time.perf_counter() - start) * 1000),
			)
			return _wrap_success(response, args, tool=tool)

		# Build dispatch_args by FILTERING to only schema-declared properties.
		# Args the schema doesn't know about are dropped at the MCP layer with
		# a logged warning — they don't reach the Python method (which would
		# TypeError on the unexpected kwarg). Meta-args (dry_run, suppress_hints)
		# are MCP-layer concerns and stripped here too.
		# This stops the classic "agent guessed `timeout` from the description,
		# blasts the rate limit because each call rejects in <1ms" failure mode.
		_META_ARGS = {"dry_run", "suppress_hints"}
		schema_props = set(spec.get("args_schema", {}).get("properties", {}).keys())
		# If the tool has no args_schema (legacy), fall back to required_args only
		known_args = schema_props or set(spec.get("required_args", []))
		dispatch_args = {}
		ignored = []
		for k, v in args.items():
			if k in _META_ARGS:
				continue
			if k in known_args:
				dispatch_args[k] = v
			else:
				ignored.append(k)
		if ignored:
			frappe.log_error(
				title=f"MCP: dropped unknown args from {tool}",
				message=f"token={token_doc_name} ignored={ignored} known={sorted(known_args)}",
			)
			# Track for fail-fast — agent that keeps sending unknown args
			# in a tight loop should be stopped before it bursts the rate limit
			_track_rejection(
				token_doc_name, tool, "unknown_args", ",".join(sorted(ignored))
			)

		# Gate A — busy-worker restart guard.
		# Restarting an agent (bench_restart) or rebuilding a bench (bench_update)
		# while the agent has a Running migrate/backup job mid-flight will kill
		# the job mid-write and can corrupt the live DB. This guard refuses
		# those tools when agent_health(server) returns verdict='slow'.
		# Bypass with args.force=true (logged in audit). The verdict source is
		# Press-side Agent Job records, no agent-side polling needed.
		if tool in _GATE_A_GUARDED_TOOLS and not args.get("force"):
			gate_a_block = _check_busy_worker_guard(tool, dispatch_args)
			if gate_a_block is not None:
				_track_rejection(token_doc_name, tool, "busy_worker_guard", gate_a_block["server"])
				raise frappe.ValidationError(gate_a_block["error"])

		# Run tool as the resolved user
		with _as_user(user):
			method = frappe.get_attr(spec["method"])
			response = method(**dispatch_args)

		_log_call(
			tool=tool, user=user, token_name=token_doc_name,
			args=args, response=response, status="Success",
			duration_ms=int((time.perf_counter() - start) * 1000),
		)
		# Destructive-op notification (Obj 7)
		if get_tool_risk(tool) == "high":
			_notify_destructive_op(tool=tool, user=user, args=args, token_name=token_doc_name)
		# Deploy-failure follow-up (Obj-10 polish item 8): tools that schedule a
		# Press build return a build name; enqueue a delayed status check so an
		# operator/agent gets notified if the build later transitions to Failure.
		_maybe_schedule_deploy_failure_check(tool, response, user)
		return _wrap_success(response, args, tool=tool)
	except RateLimitError as e:
		error_type = "RateLimitError"
		error_msg = str(e)
	except frappe.PermissionError as e:
		error_type = "PermissionError"
		error_msg = str(e)
	except frappe.ValidationError as e:
		error_type = "ValidationError"
		error_msg = str(e)
	except Exception as e:
		error_type = "Error"
		error_msg = str(e)

	_log_call(
		tool=tool, user=user, token_name=token_doc_name,
		args=args, response=None, status=error_type,
		duration_ms=int((time.perf_counter() - start) * 1000),
		error_message=error_msg,
	)
	return {"ok": False, "error": error_msg, "error_type": error_type}


def _parse_args(args) -> dict:
	if args is None:
		return {}
	if isinstance(args, dict):
		return args
	if isinstance(args, str):
		try:
			parsed = json.loads(args)
			return parsed if isinstance(parsed, dict) else {}
		except (ValueError, TypeError):
			return {}
	return {}


_SSH_RULE_WARNING = (
	"RULE — read before disconnecting: any file you edit inside the bench "
	"container at /home/frappe/frappe-bench/apps/<app>/... MUST be git "
	"commit + git push'd BEFORE you exit the SSH session. Press deploys "
	"rebuild containers from the registered Git repo; uncommitted edits "
	"are lost on the next deploy. Preferred path: use the Press MCP tool "
	"app_git_push (commits + pushes from inside the bench with audit "
	"trail). Never leave 'TODO commit later' — if you edit, you push."
)

# _tooling_rules — appears on EVERY response (unless caller passes
# suppress_hints:true). Distinct rules in separate keys so an agent parser
# can pick the relevant one. Suppressable for token-savvy clients.
_TOOLING_RULES = {
	"ctx_shell_no_file_writes": (
		"If you use the lean-ctx MCP wrapper (common on Sanad dev boxes), "
		"`ctx_shell` REJECTS any command containing a shell redirect "
		"(>, >>, tee, heredoc-to-file). It throws 'ctx_shell detected a "
		"file-write command'. Use the Write tool to create/overwrite files, "
		"Edit for appends to an existing file, or native Bash for one-shot "
		"tiny redirects. Reading command output via ctx_shell is fine — "
		"writing files via ctx_shell is not."
	),
	"ssh_commit_push_before_disconnect": (
		"If you SSH into a Press bench container (via bench_ssh_* tools) "
		"and edit files under /home/frappe/frappe-bench/apps/<app>/..., "
		"you MUST git commit + push BEFORE exiting the SSH session. "
		"Press deploys rebuild containers from the registered Git repo — "
		"uncommitted edits are lost. Preferred: use the Press MCP tool "
		"`app_git_push` (commits + pushes with audit trail)."
	),
}


def _wrap_success(response: Any, args: Any, tool: str | None = None) -> dict[str, Any]:
	"""Build the success envelope.

	Always returns: {ok, data}
	Conditionally adds:
	  _hint            — discoverability tip (suppressed by suppress_hints)
	  _tooling_rules   — universal agent tooling rules (suppressed by suppress_hints)
	  _warning         — only for bench_ssh_* tools (NEVER suppressed — load-bearing)

	Agents that already know the rules can pass {suppress_hints: true} to
	skip _hint + _tooling_rules and shave a few tokens off each response.
	_warning is always present on SSH-granting tools because forgetting to
	commit+push has caused real data loss.
	"""
	# Defensive guard: callers should pass a dict (after _parse_args), but
	# treat any non-dict as empty so we never crash on `args.get`.
	if not isinstance(args, dict):
		args = {}
	envelope: dict[str, Any] = {"ok": True, "data": response}
	if not args.get("suppress_hints"):
		envelope["_hint"] = DISCOVERABILITY_HINT
		envelope["_tooling_rules"] = _TOOLING_RULES
	if tool and tool.startswith("bench_ssh_"):
		envelope["_warning"] = _SSH_RULE_WARNING
	return envelope


def _resolve_for_builtin(token_plaintext: str) -> tuple[str, str | None, list[str]]:
	"""Verify token + return (user, token_docname, scope_list) for built-in tools.

	Built-ins (help/list_tools) skip the per-tool scope check, but we still
	authenticate the token so anonymous callers can't enumerate the catalog.
	Uses the shared `_authenticate_token` helper so token-auth lives in
	one place — see auth.py.

	Raises frappe.PermissionError on invalid/expired/revoked token.
	"""
	from press.mcp_server._util import safe_parse_list

	doc = _authenticate_token(token_plaintext)
	return doc.user, doc.name, safe_parse_list(doc.scope)


def _resolve_token_docname(token_plaintext: str) -> str | None:
	prefix = token_plaintext[:TOKEN_PREFIX_LEN]
	rows = frappe.get_all(
		"Press MCP Token",
		filters={"token_prefix": prefix},
		pluck="name",
		limit=1,
	)
	return rows[0] if rows else None


def _config_value_type(value) -> str:
	"""Site Config Key types: Password / String / Number / Boolean / JSON."""
	if isinstance(value, bool):
		return "Boolean"
	if isinstance(value, (int, float)):
		return "Number"
	if isinstance(value, (dict, list)):
		return "JSON"
	return "String"


def _coerce_config_arg(tool: str, args: dict) -> None:
	"""Accept `config` as the documented {key: value} dict.

	press.api.bench.update_config does `[frappe._dict(c) for c in config]`, so it
	needs a LIST of {key, value, type}. Passing the dict the tool description
	advertises iterates its keys and dies with "dictionary update sequence
	element #0 has length 1; 2 is required". Translate here so the documented
	shape works; a list is passed through untouched. Press overrides `type` from
	the Site Config Key row when the key is registered.
	"""
	if tool != "bench_update_config":
		return

	config = args.get("config")
	if not isinstance(config, dict):
		return

	args["config"] = [
		{"key": key, "value": value, "type": _config_value_type(value)}
		for key, value in config.items()
	]


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


# Fail-fast burst guard: track per-token "same rejection N times in a row".
# Stops agents that loop a malformed call from blasting the rate limit.
# Stored in-process (single gunicorn worker) — if the same token hits a
# different worker, the counter resets; that's acceptable since rate limit
# itself is per-token across workers via Redis.
_REJECTION_HISTORY: dict[str, dict[str, Any]] = {}
_REJECTION_BURST_LIMIT = 3  # consecutive identical rejections before backoff
_REJECTION_BURST_WINDOW_SECONDS = 10  # rejections within this window count as "in a row"


def _track_rejection(
	token_name: str | None, tool: str, kind: str, signature: str
) -> None:
	"""Track a rejection. Raises ValidationError with a clear back-off message
	once the same token hits the same kind+signature {LIMIT} times in a row
	within the burst window. Caller still raises its own ValidationError on
	the first {LIMIT-1} attempts.
	"""
	if not token_name:
		return
	key = f"{token_name}::{tool}::{kind}::{signature}"
	now = time.monotonic()
	entry = _REJECTION_HISTORY.get(key)
	if entry and now - entry["last_at"] < _REJECTION_BURST_WINDOW_SECONDS:
		entry["count"] += 1
		entry["last_at"] = now
	else:
		entry = {"count": 1, "last_at": now}
	_REJECTION_HISTORY[key] = entry

	# Prune anything older than 5x the window to keep dict tiny
	if len(_REJECTION_HISTORY) > 1000:
		cutoff = now - _REJECTION_BURST_WINDOW_SECONDS * 5
		_REJECTION_HISTORY.clear()
		# Re-add the live entry so the current request still sees it
		_REJECTION_HISTORY[key] = entry

	if entry["count"] >= _REJECTION_BURST_LIMIT:
		# Reset so caller can retry after fixing — don't trap them forever
		_REJECTION_HISTORY.pop(key, None)
		raise frappe.ValidationError(
			f"BURST-GUARD: same {kind} rejection on tool {tool!r} fired "
			f"{_REJECTION_BURST_LIMIT}x in <{_REJECTION_BURST_WINDOW_SECONDS}s. "
			f"Fix the call before retrying — likely your loop sends the same "
			f"bad args repeatedly. Call {{tool: 'help', args: {{tool: {tool!r}}}}} "
			f"for the correct args_schema. Counter reset; next call will be "
			f"evaluated normally."
		)


def _log_call(
	tool: str,
	user: str | None,
	token_name: str | None,
	args: dict,
	response: Any,
	status: str,
	duration_ms: int,
	error_message: str | None = None,
) -> None:
	"""Best-effort async log of MCP call. Never blocks the response path."""
	try:
		args_json = json.dumps(args, default=str)[:MAX_ARGS_LOG_LEN]
		response_json = (
			json.dumps(response, default=str)[:MAX_ARGS_LOG_LEN]
			if response is not None
			else None
		)
		frappe.enqueue(
			"press.mcp_server.server._write_call_log",
			queue="short",
			tool=tool,
			user=user or "",
			token_name=token_name,
			status=status,
			duration_ms=duration_ms,
			args_json=args_json,
			response_json=response_json,
			error_message=error_message,
		)
	except Exception:
		pass


def _write_call_log(
	tool: str,
	user: str,
	token_name: str | None,
	status: str,
	duration_ms: int,
	args_json: str,
	response_json: str | None,
	error_message: str | None,
) -> None:
	"""Background-job target invoked by _log_call. Computes hash chain."""
	import hashlib

	try:
		# Walk back to the latest row's row_hash for chain linkage
		latest = frappe.get_all(
			"Press MCP Call Log",
			fields=["row_hash"],
			order_by="creation desc",
			limit=1,
		)
		prev_hash = latest[0].row_hash if latest else "GENESIS"

		# Compute this row's hash. Use a stable serialization.
		creation_iso = now_datetime().isoformat()
		hash_input = "||".join([
			prev_hash or "",
			tool,
			user or "",
			token_name or "",
			status,
			creation_iso,
		])
		row_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

		frappe.get_doc({
			"doctype": "Press MCP Call Log",
			"tool": tool,
			"user": user,
			"token": token_name,
			"status": status,
			"duration_ms": duration_ms,
			"args_json": args_json,
			"response_json": response_json,
			"error_message": error_message,
			"prev_hash": prev_hash,
			"row_hash": row_hash,
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			title=f"MCP audit log write failed for tool {tool}",
			message=frappe.get_traceback(),
		)


def _notify_destructive_op(
	tool: str, user: str, args: dict, token_name: str | None
) -> None:
	"""Best-effort notification when a high-risk MCP tool runs successfully.

	Writes to Error Log with a distinctive title so operators can grep / hook
	external alerting on it (e.g., a periodic scheduler scan + Slack post).
	"""
	try:
		summary = (
			f"MCP destructive op: {tool} by {user} "
			f"via token {token_name or 'unknown'}"
		)
		# Use error_log so it shows up in Frappe's Error Log list — operators
		# can build an alerting hook on this title prefix.
		frappe.log_error(
			title=f"[MCP-DESTRUCTIVE] {tool}",
			message=f"{summary}\n\nargs: {json.dumps(args, default=str)[:2000]}",
		)
	except Exception:
		pass


# Tools whose response includes a build job that may fail asynchronously.
# Each entry maps tool name → key in response dict that holds the build name.
_DEPLOY_FOLLOWUP_TOOLS = {
	"bench_deploy": "name",  # press.api.bench.deploy returns the build name as 'name'
	"deploy_candidate_schedule_build": "build",
}
_DEPLOY_FOLLOWUP_DELAY_SECONDS = 300  # 5 min


def _maybe_schedule_deploy_failure_check(
	tool: str, response: Any, user: str | None
) -> None:
	"""If the tool kicks off a Press build, enqueue a check 5 min later that
	emits a notification if the build is in Failure state.

	No-op for tools that don't produce a build name.
	"""
	if tool not in _DEPLOY_FOLLOWUP_TOOLS:
		return
	if not isinstance(response, dict):
		return
	build_name = response.get(_DEPLOY_FOLLOWUP_TOOLS[tool])
	if not build_name:
		return
	try:
		frappe.enqueue(
			"press.mcp_server.server._check_deploy_followup",
			queue="long",
			enqueue_after_commit=True,
			now=False,
			# Frappe's enqueue doesn't have a built-in delay; we re-enqueue if
			# the build is still in-flight when the worker picks this up.
			tool=tool,
			build_name=build_name,
			triggered_by=user or "",
			deadline_seconds=_DEPLOY_FOLLOWUP_DELAY_SECONDS,
		)
	except Exception:
		# Notification is best-effort; never break the MCP response path.
		pass


def _check_deploy_followup(
	tool: str, build_name: str, triggered_by: str, deadline_seconds: int
) -> None:
	"""Background task: poll the build's status, notify on Failure.

	If the build is still Running/Pending, re-enqueue once for another check.
	After 2 re-enqueues we stop polling — terminal-state notification not
	guaranteed for 30+ minute builds. Operators can use audit_verify_chain
	+ deploy_candidate_status for those.
	"""
	try:
		row = frappe.db.get_value(
			"Deploy Candidate Build",
			build_name,
			["name", "status", "deploy_candidate"],
			as_dict=True,
		)
		if not row:
			return
		status = row.status or ""
		if status in ("Failure", "Cancelled"):
			frappe.log_error(
				title=f"[MCP-DEPLOY-FAILED] {tool}",
				message=(
					f"Build {build_name} (candidate {row.deploy_candidate}) "
					f"transitioned to {status} after {deadline_seconds}s.\n"
					f"Triggered by: {triggered_by or 'unknown'}\n"
					f"Tool: {tool}"
				),
			)
		# Success / no further action; Running/Pending → fire and forget
		# (operators can poll deploy_candidate_status directly).
	except Exception:
		pass
