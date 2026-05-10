# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.mcp_server.auth import issue_token
from press.mcp_server.server import handle


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
		basic = issue_token(
			username="Administrator",
			password="ignored",
			scope=["bench_ssh_cert_generate"],
			ttl_minutes=10,
			label="ssh-no-risky",
			risky_tools_enabled=False,
		)
		result = handle(
			tool="bench_ssh_cert_generate",
			args={"bench_name": "fake-bench"},
			token=basic["token"],
		)
		self.assertFalse(result["ok"])
		self.assertEqual(result["error_type"], "PermissionError")

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
		with patch(
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
		with patch(
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
