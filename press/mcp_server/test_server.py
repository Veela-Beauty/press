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
		tools = [r["tool"] for r in results]
		self.assertIn("tool-0", tools)
		self.assertIn("tool-1", tools)
		self.assertIn("tool-2", tools)
		self.assertNotIn("tool-other", tools)

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
