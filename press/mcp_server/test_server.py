# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.mcp_server.auth import issue_token
from press.mcp_server.server import handle


def _bench_group_get_value(real_get_value):
	"""Build a side_effect for the 3 ssh-cert tests that call handle().

	A blanket `frappe.db.get_value` mock replaces the method on the SHARED
	frappe.local.db object, so it poisons EVERY internal get_value — including
	the ones frappe.get_all uses inside _authenticate_token, which then fails
	with 'token not found' before the tool ever runs. Return the fake RG only
	for _extract_target's Bench->group lookup and delegate everything else to
	the real get_value captured before patching.
	"""
	def _fake(*args, **kwargs):
		if args and args[0] == "Bench" and len(args) >= 3 and args[2] == "group":
			return "fake-rg"
		return real_get_value(*args, **kwargs)
	return _fake


class TestMCPServer(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		# Patch login_manager so issue_token doesn't try to validate password.
		mock_lm = MagicMock()
		mock_lm.check_password.return_value = None
		self._lm_patcher = patch.object(
			frappe.local, "login_manager", mock_lm, create=True
		)
		self._lm_patcher.start()
		self.addCleanup(self._lm_patcher.stop)

		# Issue a token with broad scope for tests
		issued = issue_token(
			username="Administrator",
			password="ignored",
			scope=["clone_bench", "lock_acquire", "lock_status"],
			ttl_minutes=10,
			label="test-token",
		)
		self.token = issued["token"]

	def tearDown(self):
		frappe.db.delete("Press MCP Token")
		frappe.db.delete("Press MCP Auth Attempt")
		frappe.db.delete("Press MCP Call Log")

	def test_handle_unknown_tool_returns_validation_error(self):
		result = handle(tool="not_a_real_tool", args={}, token=self.token)
		self.assertFalse(result["ok"])
		self.assertEqual(result["error_type"], "ValidationError")

	def test_issue_token_with_wrong_password_raises_validation_not_auth_error(self):
		"""Regression: wrong password used to raise AuthenticationError, which
		Frappe maps to HTTP 401, which the Vue dashboard treats as 'session
		expired' and force-logs-out the user. Re-auth flows like token issuance
		must translate to ValidationError so the dashboard shows an inline
		error instead of logging out the user.
		"""
		mock_lm = frappe.local.login_manager
		mock_lm.check_password.side_effect = frappe.AuthenticationError(
			"Incorrect User or Password"
		)
		try:
			with self.assertRaises(frappe.ValidationError) as ctx:
				issue_token(
					username="Administrator",
					password="wrong-password",
					scope=["lock_status"],
					ttl_minutes=10,
					label="should-not-issue",
				)
			# AuthenticationError must NOT propagate (would map to HTTP 401)
			self.assertNotIsInstance(ctx.exception, frappe.AuthenticationError)
		finally:
			mock_lm.check_password.side_effect = None
			mock_lm.check_password.return_value = None

	def test_handle_missing_token_returns_permission_error(self):
		result = handle(tool="clone_bench", args={}, token=None)
		self.assertFalse(result["ok"])
		self.assertEqual(result["error_type"], "PermissionError")

	def test_handle_wrong_scope_returns_permission_error(self):
		# Issue a fresh token with NO scope for clone_bench
		issued = issue_token(
			username="Administrator",
			password="ignored",
			scope=["lock_status"],  # missing clone_bench
			ttl_minutes=10,
			label="narrow",
		)
		result = handle(
			tool="clone_bench",
			args={"release_group": "fake", "new_title": "x"},
			token=issued["token"],
		)
		self.assertFalse(result["ok"])
		self.assertEqual(result["error_type"], "PermissionError")

	def test_handle_missing_required_args_returns_validation_error(self):
		result = handle(
			tool="clone_bench",
			args={"release_group": "fake"},  # missing new_title
			token=self.token,
		)
		self.assertFalse(result["ok"])
		self.assertEqual(result["error_type"], "ValidationError")

	def test_handle_dispatches_to_tool_method_with_args(self):
		# Mock the underlying clone_release_group so we don't actually clone.
		with patch(
			"press.press.doctype.release_group.release_group_clone.clone_release_group"
		) as m:
			m.return_value = "RG-CLONED-001"
			result = handle(
				tool="clone_bench",
				args={
					"release_group": "RG-SOURCE",
					"new_title": "Cloned",
					"lifetime": "persistent",
				},
				token=self.token,
			)

		self.assertTrue(result["ok"])
		self.assertEqual(result["data"], "RG-CLONED-001")
		m.assert_called_once_with(
			release_group="RG-SOURCE",
			new_title="Cloned",
			lifetime="persistent",
		)

	def _sync_enqueue(self, method_path, **kwargs):
		"""Run frappe.enqueue targets synchronously so log rows exist in tests."""
		from press.mcp_server.server import _write_call_log
		_write_call_log(
			tool=kwargs["tool"],
			user=kwargs["user"],
			token_name=kwargs["token_name"],
			status=kwargs["status"],
			duration_ms=kwargs["duration_ms"],
			args_json=kwargs["args_json"],
			response_json=kwargs["response_json"],
			error_message=kwargs["error_message"],
		)

	def test_handle_logs_call_with_status_and_duration(self):
		# Run enqueue synchronously so the log row exists before assertions
		with patch("press.mcp_server.server.frappe.enqueue", side_effect=self._sync_enqueue):
			with patch(
				"press.press.doctype.release_group.release_group_clone.clone_release_group"
			) as m:
				m.return_value = "RG-X"
				handle(
					tool="clone_bench",
					args={"release_group": "S", "new_title": "T"},
					token=self.token,
				)

		logs = frappe.get_all(
			"Press MCP Call Log",
			filters={"tool": "clone_bench"},
			fields=["status", "user", "duration_ms"],
		)
		self.assertEqual(len(logs), 1)
		self.assertEqual(logs[0].status, "Success")
		self.assertEqual(logs[0].user, "Administrator")
		self.assertGreaterEqual(logs[0].duration_ms, 0)

	def test_handle_permission_inheritance_via_set_user(self):
		captured_user = []

		def fake_clone(**kwargs):
			captured_user.append(frappe.session.user)
			return "OK"

		with patch(
			"press.press.doctype.release_group.release_group_clone.clone_release_group",
			side_effect=fake_clone,
		):
			handle(
				tool="clone_bench",
				args={"release_group": "X", "new_title": "Y"},
				token=self.token,
			)

		self.assertEqual(captured_user, ["Administrator"])

	def test_list_my_calls_returns_recent_logs_for_current_user(self):
		from press.mcp_server.dashboard import list_my_calls
		from unittest.mock import patch

		# Create a few call log rows directly
		for i in range(3):
			frappe.get_doc({
				"doctype": "Press MCP Call Log",
				"tool": f"tool-{i}",
				"user": "Administrator",
				"status": "Success",
				"duration_ms": 10 + i,
			}).insert(ignore_permissions=True)
		# Plus one for a different user — should be excluded
		frappe.get_doc({
			"doctype": "Press MCP Call Log",
			"tool": "tool-other",
			"user": "Guest",
			"status": "Success",
			"duration_ms": 5,
		}).insert(ignore_permissions=True)

		results = list_my_calls(limit=100)
		# New shape: {rows, latest}
		self.assertIn("rows", results)
		self.assertIn("latest", results)
		tools = [r["tool"] for r in results["rows"]]
		self.assertIn("tool-0", tools)
		self.assertIn("tool-1", tools)
		self.assertIn("tool-2", tools)
		self.assertNotIn("tool-other", tools)

	def test_list_my_calls_incremental_filter_returns_no_rows_when_unchanged(self):
		from press.mcp_server.dashboard import list_my_calls
		# Pull all rows first
		first = list_my_calls(limit=100)
		latest = first["latest"]
		# Re-poll with since_iso=latest — should return no NEW rows
		second = list_my_calls(limit=100, since_iso=latest)
		# Note: since the filter is creation > since_iso (strict), rows AT latest are excluded
		self.assertEqual(len(second["rows"]), 0)

	def test_deploy_failure_followup_logs_error_on_failed_build(self):
		"""When a bench_deploy build later transitions to Failure, the
		background check writes a [MCP-DEPLOY-FAILED] error log."""
		from press.mcp_server.server import _check_deploy_followup
		from unittest.mock import patch

		fake_row = frappe._dict({
			"name": "build-X",
			"status": "Failure",
			"deploy_candidate": "candidate-X",
		})
		with patch(
			"press.mcp_server.server.frappe.db.get_value",
			return_value=fake_row,
		), patch(
			"press.mcp_server.server.frappe.log_error",
		) as m_log:
			_check_deploy_followup(
				tool="bench_deploy",
				build_name="build-X",
				triggered_by="Administrator",
				deadline_seconds=300,
			)
		m_log.assert_called_once()
		_, kwargs = m_log.call_args
		self.assertIn("[MCP-DEPLOY-FAILED]", kwargs["title"])

	def test_deploy_failure_followup_no_log_on_success_status(self):
		"""Successful build → no log written."""
		from press.mcp_server.server import _check_deploy_followup
		from unittest.mock import patch

		fake_row = frappe._dict({
			"name": "build-Y",
			"status": "Success",
			"deploy_candidate": "candidate-Y",
		})
		with patch(
			"press.mcp_server.server.frappe.db.get_value",
			return_value=fake_row,
		), patch(
			"press.mcp_server.server.frappe.log_error",
		) as m_log:
			_check_deploy_followup(
				tool="bench_deploy",
				build_name="build-Y",
				triggered_by="Administrator",
				deadline_seconds=300,
			)
		m_log.assert_not_called()

	def test_handle_extracts_site_target_from_name_arg(self):
		"""api/site.py methods take `name`, not `site` — verify _extract_target maps it."""
		from unittest.mock import patch
		# Use site_migrate as a representative tool
		with patch("press.api.site.migrate") as m:
			m.return_value = {"job": "fake"}
			# Issue a token scoped to a specific site
			from press.mcp_server.auth import issue_token
			scoped = issue_token(
				username="Administrator",
				password="ignored",
				scope=["site_migrate"],
				ttl_minutes=10,
				label="site-scoped",
				allowed_sites=["allowed-site.example.com"],
			)
			# Allowed site should pass
			result_ok = handle(
				tool="site_migrate",
				args={"name": "allowed-site.example.com"},
				token=scoped["token"],
			)
			self.assertTrue(result_ok["ok"])

			# Disallowed site should fail
			result_blocked = handle(
				tool="site_migrate",
				args={"name": "different-site.example.com"},
				token=scoped["token"],
			)
			self.assertFalse(result_blocked["ok"])
			self.assertEqual(result_blocked["error_type"], "PermissionError")

	def test_handle_recognizes_new_lifecycle_tools_in_catalog(self):
		from press.mcp_server.tools import get_tool_spec
		# Spot-check a few of the newly added tools
		for tool in ("site_migrate", "bench_deploy", "app_git_status", "site_run_python"):
			spec = get_tool_spec(tool)
			self.assertIsNotNone(spec, f"tool {tool} missing from catalog")
			self.assertIn("method", spec)
			self.assertIn("required_args", spec)

	def test_extract_target_from_explicit_target_args(self):
		"""Lock-style tools pass target_doctype/target_name directly."""
		from press.mcp_server.server import _extract_target
		td, tn = _extract_target(
			"lock_acquire",
			{"target_doctype": "Release Group", "target_name": "RG-X", "reason": "test"},
		)
		self.assertEqual(td, "Release Group")
		self.assertEqual(tn, "RG-X")

	def test_extract_target_from_release_group_arg(self):
		"""clone_bench takes release_group arg."""
		from press.mcp_server.server import _extract_target
		td, tn = _extract_target("clone_bench", {"release_group": "RG-Y", "new_title": "T"})
		self.assertEqual(td, "Release Group")
		self.assertEqual(tn, "RG-Y")

	def test_bench_file_tools_are_resource_scoped(self):
		"""REGRESSION (2026-05-10): bench_list_app_files / bench_read_app_file /
		bench_ssh_instructions previously returned (None, None) from
		_extract_target → resource-scope check skipped → token scoped to bench-A
		could read files from bench-B unbounded. These tools take bench_name and
		read bench data, so they MUST resolve to the parent RG.

		bench_ssh_register_key is intentionally NOT here: it takes `public_key`
		(not bench_name) and registers a key on the calling USER, so it is
		resourceless. Bench scope is enforced later at bench_ssh_cert_generate
		(which IS bench-scoped). Asserting RG resolution for it was a test bug —
		see test_bench_ssh_register_key_is_resourceless below.
		"""
		from press.mcp_server.server import _extract_target

		# Create a fake Bench → Release Group mapping to test extraction
		from unittest.mock import patch
		with patch(
			"press.mcp_server.server.frappe.db.get_value",
			return_value="rg-mapped-from-bench",
		):
			for tool in (
				"bench_list_app_files",
				"bench_read_app_file",
				"bench_ssh_instructions",
			):
				td, tn = _extract_target(tool, {"bench_name": "bench-X-001-press-f1"})
				self.assertEqual(
					(td, tn),
					("Release Group", "rg-mapped-from-bench"),
					f"{tool!r}: expected RG resolution, got ({td!r}, {tn!r}). "
					"Resource-scope check would be SKIPPED — token scope bypass.",
				)

	def test_bench_ssh_register_key_is_resourceless(self):
		"""bench_ssh_register_key registers a pubkey on the calling USER (arg:
		public_key, NOT bench_name) so it has no bench resource to scope.
		_extract_target must return (None, None) and the tool must be in
		RESOURCELESS_TOOLS — bench scope is enforced at bench_ssh_cert_generate.
		"""
		from press.mcp_server.server import RESOURCELESS_TOOLS, _extract_target

		td, tn = _extract_target("bench_ssh_register_key", {"public_key": "ssh-ed25519 AAAA..."})
		self.assertEqual((td, tn), (None, None))
		self.assertIn("bench_ssh_register_key", RESOURCELESS_TOOLS)

	def test_bench_control_tools_registered_with_risk(self):
		"""The 10 bench-control tools (2026-06-18) must be in the catalog with the
		expected risk, so the destructive ones gate on risky_tools_enabled."""
		from press.mcp_server.tools import get_tool_risk, get_tool_spec

		expected = {
			"release_group_add_app": "medium",
			"release_group_remove_app": "high",
			"release_group_list_branches": "low",
			"release_group_versions": "low",
			"release_group_installable_apps": "low",
			"release_group_rename": "medium",
			"release_group_redeploy": "medium",
			"release_group_archive": "high",
			"bench_rebuild_assets": "high",
			"release_group_create": "medium",
		}
		for tool, risk in expected.items():
			spec = get_tool_spec(tool)
			self.assertIsNotNone(spec, f"tool {tool} missing from catalog")
			self.assertIn("method", spec)
			self.assertEqual(get_tool_risk(tool), risk, f"{tool}: wrong risk")

	def test_bench_control_rg_tools_resource_scoped(self):
		"""RG-composition tools take the Release Group docname as `name` and MUST
		resolve to ("Release Group", name) so the token RG allowlist is enforced.
		A regression here = a token scoped to RG-A could mutate RG-B."""
		from press.mcp_server.server import _extract_target

		args = {"name": "RG-Z", "app": "erpnext", "source": "S", "title": "T", "dc_name": "D"}
		for tool in (
			"release_group_add_app",
			"release_group_remove_app",
			"release_group_list_branches",
			"release_group_versions",
			"release_group_installable_apps",
			"release_group_rename",
			"release_group_redeploy",
			"release_group_archive",
		):
			td, tn = _extract_target(tool, args)
			self.assertEqual(
				(td, tn),
				("Release Group", "RG-Z"),
				f"{tool!r}: expected RG resolution, got ({td!r}, {tn!r}) — scope bypass.",
			)

	def test_bench_rebuild_assets_resolves_bench_to_parent_rg(self):
		"""bench_rebuild_assets takes a Bench docname as `name`; it must resolve to
		the parent Release Group via the Bench->group lookup."""
		from press.mcp_server.server import _extract_target

		with patch(
			"press.mcp_server.server.frappe.db.get_value",
			return_value="rg-from-bench",
		):
			td, tn = _extract_target("bench_rebuild_assets", {"name": "bench-X-001-press-f1"})
		self.assertEqual((td, tn), ("Release Group", "rg-from-bench"))

	def test_release_group_create_is_resourceless(self):
		"""release_group_create has no pre-existing resource to scope to; it must be
		in RESOURCELESS_TOOLS and _extract_target must return (None, None). Its args
		avoid _RESOURCE_ARG_NAMES so the fail-closed guard won't trip."""
		from press.mcp_server.server import RESOURCELESS_TOOLS, _extract_target

		td, tn = _extract_target(
			"release_group_create",
			{"title": "New RG", "version": "Version 15", "new_apps": [], "cluster": "Default"},
		)
		self.assertEqual((td, tn), (None, None))
		self.assertIn("release_group_create", RESOURCELESS_TOOLS)

	def test_normalize_arg_aliases_rewrites_to_canonical(self):
		"""LLM arg-name guesses (site/bench/name) rewrite to the tool's canonical arg
		so the call doesn't reject with missing-required-args."""
		from press.mcp_server.server import _normalize_arg_aliases
		from press.mcp_server.tools import get_tool_spec

		cases = [
			("site_status", "site", {"site": "x.com"}, "site_name", "x.com"),
			("site_config_get", "name", {"name": "x.com"}, "site_name", "x.com"),
			("app_git_status", "bench", {"bench": "b-1"}, "bench_name", "b-1"),
			("deploy_failure_details", "name", {"name": "DCB-1"}, "dn", "DCB-1"),
		]
		for tool, alias_key, sent, canon, val in cases:
			out = _normalize_arg_aliases(get_tool_spec(tool), sent)
			self.assertEqual(out.get(canon), val, f"{tool}: {sent} should map {canon}={val}")
			self.assertNotIn(alias_key, out, f"{tool}: alias {alias_key!r} not consumed")

	def test_normalize_arg_aliases_leaves_legit_args_untouched(self):
		"""Guard: tools that legitimately declare `site`/`name` must NOT be rewritten
		(clone_site uses `site`, bench_deploy uses `name` for the Release Group)."""
		from press.mcp_server.server import _normalize_arg_aliases
		from press.mcp_server.tools import get_tool_spec

		clone = _normalize_arg_aliases(
			get_tool_spec("clone_site"),
			{"site": "src.com", "target_release_group": "RG"},
		)
		self.assertEqual(clone.get("site"), "src.com")
		self.assertNotIn("site_name", clone)

		deploy = _normalize_arg_aliases(get_tool_spec("bench_deploy"), {"name": "RG-1", "apps": []})
		self.assertEqual(deploy.get("name"), "RG-1")

	def test_extract_target_bench_restart_resolves_name_to_parent_rg(self):
		"""REGRESSION (2026-06-02): bench_restart / bench_update take the Bench
		docname as the `name` arg (per tools.py required_args). _extract_target
		previously mapped `name` to a Release Group name in the RG block, so a
		Bench docname resolved to a bogus ("Release Group", <bench-docname>) and
		the scope check failed closed with a PermissionError -- the MCP tool was
		unusable. Verify both tools now resolve the Bench docname to its parent
		RG via the bench-docname block (whether passed as name or bench_name).
		"""
		from press.mcp_server.server import _extract_target
		from unittest.mock import patch

		with patch(
			"press.mcp_server.server.frappe.db.get_value",
			return_value="rg-mapped-from-bench",
		):
			for tool in ("bench_restart", "bench_update"):
				for arg in ("name", "bench_name"):
					td, tn = _extract_target(tool, {arg: "bench-X-001-press-f1"})
					self.assertEqual(
						(td, tn),
						("Release Group", "rg-mapped-from-bench"),
						f"{tool!r} via {arg!r}: expected RG resolution, "
						f"got ({td!r}, {tn!r}).",
					)

	def test_assert_target_extracted_fails_closed_on_unmapped_resource_tool(self):
		"""Defense-in-depth: a tool with bench_name/site/etc. arg but missing
		from _extract_target must be blocked, not silently authorized.
		"""
		from press.mcp_server.server import _assert_target_extracted

		# Simulate a future tool that takes bench_name but isn't in _extract_target
		# AND isn't in RESOURCELESS_TOOLS — must raise PermissionError.
		with self.assertRaises(frappe.PermissionError) as ctx:
			_assert_target_extracted(
				tool="some_future_unmapped_tool",
				args={"bench_name": "bench-X"},
				target_doctype=None,
				target_name=None,
			)
		self.assertIn("missing from _extract_target", str(ctx.exception))

	def test_assert_target_extracted_allows_resourceless_tools(self):
		"""list_release_groups / list_sites etc. genuinely don't operate on a
		single resource — _assert_target_extracted must allow them through.
		"""
		from press.mcp_server.server import _assert_target_extracted, RESOURCELESS_TOOLS
		for tool in RESOURCELESS_TOOLS:
			# Should NOT raise
			_assert_target_extracted(tool=tool, args={}, target_doctype=None, target_name=None)

	def test_log_call_truncates_oversized_payloads(self):
		"""args/response over MAX_ARGS_LOG_LEN must be truncated, not crash the log insert."""
		from press.mcp_server.server import MAX_ARGS_LOG_LEN

		big_response = "x" * (MAX_ARGS_LOG_LEN + 50000)
		with patch("press.mcp_server.server.frappe.enqueue", side_effect=self._sync_enqueue):
			with patch(
				"press.press.doctype.release_group.release_group_clone.clone_release_group",
				return_value=big_response,
			):
				result = handle(
					tool="clone_bench",
					args={"release_group": "src", "new_title": "t"},
					token=self.token,
				)
		self.assertTrue(result["ok"])
		log_rows = frappe.get_all(
			"Press MCP Call Log",
			filters={"tool": "clone_bench"},
			fields=["response_json"],
			limit=1,
			order_by="creation desc",
		)
		self.assertEqual(len(log_rows), 1)
		self.assertLessEqual(len(log_rows[0].response_json), MAX_ARGS_LOG_LEN)

	def test_dry_run_high_risk_tool_does_not_execute(self):
		from unittest.mock import patch
		# Issue a risky-enabled token (Administrator → auto-approved)
		from press.mcp_server.auth import issue_token
		risky = issue_token(
			username="Administrator",
			password="ignored",
			scope=["site_run_python"],
			ttl_minutes=10,
			label="dry-run-test",
			risky_tools_enabled=True,
		)
		with patch(
			"press.press.doctype.bench.bench_dev_overview.run_python_on_site"
		) as m:
			result = handle(
				tool="site_run_python",
				args={"site_name": "x", "code": "rm_rf", "dry_run": True},
				token=risky["token"],
			)
		self.assertTrue(result["ok"])
		self.assertTrue(result["data"]["dry_run"])
		# Underlying method must NOT have been called
		m.assert_not_called()

	def test_low_risk_tool_ignores_dry_run_flag(self):
		"""dry_run only short-circuits HIGH-risk tools; low-risk runs normally."""
		from unittest.mock import patch
		from press.mcp_server.auth import issue_token
		# Issue a token scoped to list_release_groups
		tok = issue_token(
			username="Administrator",
			password="ignored",
			scope=["list_release_groups"],
			ttl_minutes=10,
			label="dry-run-low-risk",
		)
		with patch("press.api.bench.all", return_value=[]):
			result = handle(
				tool="list_release_groups",
				args={"dry_run": True},
				token=tok["token"],
			)
		self.assertTrue(result["ok"])
		# Result should be the actual list, not a dry-run stub
		self.assertNotIn("dry_run", result.get("data") or {})

	def test_ssh_cert_generate_blocked_without_risky_flag(self):
		"""bench_ssh_cert_generate is high-risk; basic token must be rejected."""
		from press.mcp_server.auth import issue_token
		from unittest.mock import patch
		basic = issue_token(
			username="Administrator",
			password="ignored",
			scope=["bench_ssh_cert_generate"],
			ttl_minutes=10,
			label="ssh-no-risky",
			risky_tools_enabled=False,
		)
		# Mock Bench → group lookup so _assert_target_extracted passes and the
		# test exercises the actual high-risk gate, not the fail-closed guard.
		_real_gv = frappe.db.get_value
		with patch(
			"press.mcp_server.server.frappe.db.get_value",
			side_effect=_bench_group_get_value(_real_gv),
		):
			result = handle(
				tool="bench_ssh_cert_generate",
				args={"bench_name": "fake-bench"},
				token=basic["token"],
			)
		self.assertFalse(result["ok"])
		self.assertEqual(result["error_type"], "PermissionError")
		self.assertIn("high-risk", result["error"])

	def test_ssh_cert_get_works_with_basic_token_when_in_scope(self):
		"""bench_ssh_cert_get is medium-risk; basic token with proper scope works."""
		from press.mcp_server.auth import issue_token
		from unittest.mock import patch
		basic = issue_token(
			username="Administrator",
			password="ignored",
			scope=["bench_ssh_cert_get"],
			ttl_minutes=10,
			label="ssh-get",
			risky_tools_enabled=False,
		)
		# Mock the Bench → group lookup that _extract_target performs (the
		# fail-closed guard requires extraction to succeed even with an empty
		# allowed_release_groups allowlist).
		_real_gv = frappe.db.get_value
		with patch(
			"press.mcp_server.server.frappe.db.get_value",
			side_effect=_bench_group_get_value(_real_gv),
		), patch(
			"press.press.doctype.bench.bench_dev_overview.get_ssh_certificate",
			return_value={"certificate": "fake-cert", "expires": "2026-12-31"},
		):
			result = handle(
				tool="bench_ssh_cert_get",
				args={"bench_name": "fake-bench"},
				token=basic["token"],
			)
		self.assertTrue(result["ok"])
		self.assertIn("certificate", result["data"])

	def test_ssh_cert_generate_works_with_risky_approved_token(self):
		from press.mcp_server.auth import issue_token
		from unittest.mock import patch
		risky = issue_token(
			username="Administrator",
			password="ignored",
			scope=["bench_ssh_cert_generate"],
			ttl_minutes=10,
			label="ssh-risky",
			risky_tools_enabled=True,
		)
		self.assertEqual(risky["approval_status"], "approved")
		# Mock Bench → group lookup (see comment on test above).
		_real_gv = frappe.db.get_value
		with patch(
			"press.mcp_server.server.frappe.db.get_value",
			side_effect=_bench_group_get_value(_real_gv),
		), patch(
			"press.press.doctype.bench.bench_dev_overview.generate_ssh_certificate",
			return_value={"status": "generated"},
		):
			result = handle(
				tool="bench_ssh_cert_generate",
				args={"bench_name": "fake-bench"},
				token=risky["token"],
			)
		self.assertTrue(result["ok"])

	def test_ssh_tools_in_catalog_with_correct_risk_levels(self):
		from press.mcp_server.tools import TOOLS
		self.assertEqual(TOOLS["bench_ssh_cert_get"]["risk"], "medium")
		self.assertEqual(TOOLS["bench_ssh_cert_generate"]["risk"], "high")
		self.assertEqual(TOOLS["bench_dev_info"]["risk"], "low")

	def test_handle_returns_rate_limit_error_when_exceeded(self):
		from press.mcp_server.rate_limit import RateLimitError

		with patch(
			"press.mcp_server.server.check_rate_limit",
			side_effect=RateLimitError("test cap exceeded"),
		):
			result = handle(
				tool="lock_status",
				args={"target_doctype": "Release Group", "target_name": "X"},
				token=self.token,
			)
		self.assertFalse(result["ok"])
		self.assertEqual(result["error_type"], "RateLimitError")
		self.assertIn("cap exceeded", result["error"])

	def test_destructive_op_notification_logged_on_success(self):
		"""High-risk tool successful run must trigger _notify_destructive_op."""
		from press.mcp_server.auth import issue_token
		risky = issue_token(
			username="Administrator",
			password="ignored",
			scope=["site_run_python"],
			ttl_minutes=10,
			label="destructive-test",
			risky_tools_enabled=True,
		)
		with patch(
			"press.press.doctype.bench.bench_dev_overview.run_python_on_site",
			return_value="OK",
		):
			with patch("press.mcp_server.server._notify_destructive_op") as m_notify:
				handle(
					tool="site_run_python",
					args={"site_name": "x", "code": "print('hi')"},
					token=risky["token"],
				)
		m_notify.assert_called_once()

	def test_audit_log_writes_row_hash(self):
		"""After a successful call, the latest log row has a non-empty row_hash."""
		def sync_enqueue(method_path, **kwargs):
			from press.mcp_server.server import _write_call_log
			_write_call_log(
				tool=kwargs["tool"], user=kwargs["user"], token_name=kwargs["token_name"],
				status=kwargs["status"], duration_ms=kwargs["duration_ms"],
				args_json=kwargs["args_json"], response_json=kwargs["response_json"],
				error_message=kwargs["error_message"],
			)
		with patch("press.mcp_server.server.frappe.enqueue", side_effect=sync_enqueue):
			with patch("press.api.bench.all", return_value=[]):
				handle(
					tool="list_release_groups",
					args={},
					token=self.token,
				)
		row = frappe.get_all(
			"Press MCP Call Log",
			filters={"tool": "list_release_groups"},
			fields=["row_hash", "prev_hash"],
			order_by="creation desc",
			limit=1,
		)
		self.assertEqual(len(row), 1)
		self.assertTrue(row[0].row_hash)
		self.assertEqual(len(row[0].row_hash), 64)  # SHA-256 hex

	def test_obj8_catalog_complete(self):
		"""All Obj 8 tools registered with correct risk levels."""
		from press.mcp_server.tools import TOOLS
		expected = {
			"site_domains_list": "low",
			"site_add_domain": "medium",
			"site_remove_domain": "medium",
			"site_set_host_name": "medium",
			"site_update_config_bulk": "medium",
			"bench_update_config": "medium",
			"bench_update_dependencies": "high",
		}
		for name, risk in expected.items():
			self.assertIn(name, TOOLS, f"missing tool {name}")
			self.assertEqual(TOOLS[name]["risk"], risk, f"wrong risk for {name}")

	def test_obj8_site_domain_tool_dispatches_with_site_target(self):
		"""site_add_domain should be subject to site allowlist scoping."""
		from press.mcp_server.server import _extract_target
		td, tn = _extract_target("site_add_domain", {"name": "x.example.com", "domain": "y.com"})
		self.assertEqual(td, "Site")
		self.assertEqual(tn, "x.example.com")

	def test_obj8_bench_config_tool_dispatches_with_rg_target(self):
		from press.mcp_server.server import _extract_target
		td, tn = _extract_target("bench_update_config", {"name": "RG-X", "config": {}})
		self.assertEqual(td, "Release Group")
		self.assertEqual(tn, "RG-X")

	def test_wait_wrappers_have_resource_scope(self):
		"""The *_and_wait wrappers were unusable: registered as tools but missing
		from _extract_target, so _assert_target_extracted blocked every call."""
		from press.mcp_server.server import _extract_target

		td, tn = _extract_target("site_update_and_wait", {"site_name": "x.example.com"})
		self.assertEqual((td, tn), ("Site", "x.example.com"))

		# Scoped to the Release Group being deployed, matching bench_deploy —
		# site_name is only polled for the flip.
		td, tn = _extract_target(
			"bench_deploy_and_wait", {"name": "RG-X", "site_name": "x.example.com"}
		)
		self.assertEqual((td, tn), ("Release Group", "RG-X"))

		td, tn = _extract_target("list_sites_on_release_group", {"release_group": "RG-X"})
		self.assertEqual((td, tn), ("Release Group", "RG-X"))

	def test_every_tool_with_a_resource_arg_is_mapped(self):
		"""Guard the whole bug class: a tool registered with a resource arg but
		never named in _extract_target is dead on arrival — the fail-closed guard
		rejects every call.

		Checked statically against the function source rather than by probing with
		a fake id: several mappings resolve through a DB lookup (bench → parent
		Release Group), so a nonexistent probe value returns None and would report
		perfectly good tools as unmapped.
		"""
		import inspect

		from press.mcp_server import server as mcp_server
		from press.mcp_server.tools import TOOLS

		source = inspect.getsource(mcp_server._extract_target)

		# Lock tools carry explicit target_doctype/target_name args and are
		# resolved by the generic branch at the top of _extract_target, so they
		# are never named individually.
		generically_scoped = {"lock_acquire", "lock_release", "lock_status"}

		unmapped = []
		for name, spec in TOOLS.items():
			if name in mcp_server.RESOURCELESS_TOOLS or name in generically_scoped:
				continue
			if not (set(spec.get("required_args", [])) & mcp_server._RESOURCE_ARG_NAMES):
				continue
			if f'"{name}"' not in source:
				unmapped.append(name)

		self.assertEqual(
			sorted(unmapped),
			[],
			"tools carry a resource arg but are never named in _extract_target, so "
			f"the fail-closed guard rejects every call: {sorted(unmapped)}",
		)

	def test_bench_update_config_accepts_documented_dict(self):
		"""press.api.bench.update_config wants a LIST of {key,value,type}; the tool
		description advertises a dict. Accept the documented shape."""
		from press.mcp_server.server import _coerce_config_arg

		args = {"config": {"server_script_enabled": 1, "some_flag": True, "a_name": "x"}}
		_coerce_config_arg("bench_update_config", args)
		self.assertEqual(
			sorted(args["config"], key=lambda c: c["key"]),
			[
				{"key": "a_name", "value": "x", "type": "String"},
				{"key": "server_script_enabled", "value": 1, "type": "Number"},
				{"key": "some_flag", "value": True, "type": "Boolean"},
			],
		)

		# A list is already correct — pass it through untouched.
		already = {"config": [{"key": "k", "value": "v", "type": "String"}]}
		_coerce_config_arg("bench_update_config", already)
		self.assertEqual(already["config"], [{"key": "k", "value": "v", "type": "String"}])

		# Other tools are not touched.
		other = {"config": {"a": 1}}
		_coerce_config_arg("site_update_config_bulk", other)
		self.assertEqual(other["config"], {"a": 1})

	def test_obj8_dependency_update_is_high_risk(self):
		"""bench_update_dependencies must require risky_tools_enabled=True."""
		from press.mcp_server.auth import issue_token
		basic = issue_token(
			username="Administrator",
			password="ignored",
			scope=["bench_update_dependencies"],
			ttl_minutes=10,
			label="dep-update-no-risky",
			risky_tools_enabled=False,
		)
		result = handle(
			tool="bench_update_dependencies",
			args={"name": "RG-X", "dependencies": "{}"},
			token=basic["token"],
		)
		self.assertFalse(result["ok"])
		self.assertEqual(result["error_type"], "PermissionError")


class TestGateABusyWorkerGuard(FrappeTestCase):
	"""Gate A refuses bench_restart/bench_update when the target bench's
	agent is mid-job (agent_health verdict == 'slow'). Bypass with force=true.
	Best-effort: never breaks legitimate ops if the check itself errors."""

	def test_refuses_bench_restart_when_agent_is_slow(self):
		from press.mcp_server.server import _check_busy_worker_guard

		def fake_health(server, lookback_minutes=10):
			return {
				"verdict": "slow",
				"reason": "Agent has 1 Running job (youngest 45s).",
				"running_jobs": [{"job_type": "Update Site Migrate", "age_seconds": 45}],
			}

		with patch(
			"press.mcp_server.server.frappe.db.get_value", return_value="press-f1.example.com"
		), patch(
			"press.mcp_server.deploy_flow.agent_health", side_effect=fake_health
		):
			result = _check_busy_worker_guard("bench_restart", {"name": "bench-X-press-f1"})

		self.assertIsNotNone(result)
		self.assertEqual(result["server"], "press-f1.example.com")
		self.assertIn("Gate A refusal", result["error"])
		self.assertIn("Update Site Migrate", result["error"])
		self.assertIn("force=true", result["error"])

	def test_allows_bench_restart_when_agent_is_healthy(self):
		from press.mcp_server.server import _check_busy_worker_guard

		def fake_health(server, lookback_minutes=10):
			return {"verdict": "healthy", "reason": "Last success 30s ago.", "running_jobs": []}

		with patch(
			"press.mcp_server.server.frappe.db.get_value", return_value="press-f1.example.com"
		), patch(
			"press.mcp_server.deploy_flow.agent_health", side_effect=fake_health
		):
			result = _check_busy_worker_guard("bench_restart", {"name": "bench-X-press-f1"})

		self.assertIsNone(result, "guard should allow when verdict is healthy")

	def test_allows_when_bench_not_found(self):
		"""If we can't resolve the server, fail open — don't block legitimate ops."""
		from press.mcp_server.server import _check_busy_worker_guard

		with patch("press.mcp_server.server.frappe.db.get_value", return_value=None):
			result = _check_busy_worker_guard("bench_restart", {"name": "ghost-bench"})

		self.assertIsNone(result)

	def test_allows_when_agent_health_raises(self):
		"""If agent_health itself errors, fail open + log_error."""
		from press.mcp_server.server import _check_busy_worker_guard

		with patch(
			"press.mcp_server.server.frappe.db.get_value", return_value="press-f1.example.com"
		), patch(
			"press.mcp_server.deploy_flow.agent_health", side_effect=RuntimeError("db down")
		), patch(
			"press.mcp_server.server.frappe.log_error"
		) as fake_log:
			result = _check_busy_worker_guard("bench_restart", {"name": "bench-X"})

		self.assertIsNone(result, "guard must fail open on error")
		fake_log.assert_called_once()
		self.assertIn("Gate A", fake_log.call_args.kwargs["title"])
