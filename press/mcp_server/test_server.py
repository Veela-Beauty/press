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

	def test_handle_logs_call_with_status_and_duration(self):
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
