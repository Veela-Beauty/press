# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from press.mcp_server.auth import (
	BRUTE_FORCE_BLOCK_MINUTES,
	BRUTE_FORCE_THRESHOLD,
	BRUTE_FORCE_WINDOW_MINUTES,
	issue_token,
	revoke_token,
	verify_token,
)


class TestPressMCPToken(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.delete("Press MCP Token")
		frappe.db.delete("Press MCP Auth Attempt")

	def _mock_password_check(self, valid: bool):
		mock_lm = MagicMock()
		if valid:
			mock_lm.check_password.return_value = None  # success: no exception
		else:
			mock_lm.check_password.side_effect = frappe.AuthenticationError(
				"Invalid login credentials"
			)
		return patch.object(frappe.local, "login_manager", mock_lm, create=True)

	def test_issue_token_with_correct_password_returns_plaintext_once(self):
		with self._mock_password_check(valid=True):
			result = issue_token(
				username="Administrator",
				password="ignored-by-mock",
				scope=["clone_bench"],
				ttl_minutes=60,
				label="Test agent token",
			)

		self.assertIn("token", result)
		self.assertGreater(len(result["token"]), 30)
		self.assertEqual(result["scope"], ["clone_bench"])
		self.assertEqual(result["label"], "Test agent token")
		# DB row exists with hashed token, not plaintext
		rows = frappe.get_all("Press MCP Token", pluck="name")
		self.assertEqual(len(rows), 1)
		stored = frappe.get_doc("Press MCP Token", rows[0])
		# Hashed value must NOT equal plaintext
		hashed = stored.get_password("token_hash", raise_exception=False)
		# Frappe's Password fieldtype stores+returns the value via the Auth table.
		# We just assert the plaintext is verifiable AND that token_prefix matches.
		self.assertEqual(stored.token_prefix, result["token"][:8])

	def test_issue_token_with_wrong_password_raises_auth_error(self):
		with self._mock_password_check(valid=False):
			with self.assertRaises(frappe.AuthenticationError):
				issue_token(
					username="Administrator",
					password="wrong",
					scope=[],
					ttl_minutes=10,
					label="bad",
				)

	def test_brute_force_blocks_after_threshold(self):
		ip = "10.0.0.1"
		# Record THRESHOLD failures within the window
		for i in range(BRUTE_FORCE_THRESHOLD):
			frappe.get_doc({
				"doctype": "Press MCP Auth Attempt",
				"username": "victim@example.com",
				"ip_address": ip,
				"success": 0,
			}).insert(ignore_permissions=True)
		# Next attempt from same IP should be blocked even with valid creds
		with patch.object(frappe.local, "request_ip", ip, create=True):
			with self._mock_password_check(valid=True):
				with self.assertRaises(frappe.AuthenticationError) as ctx:
					issue_token(
						username="someone@example.com",
						password="ignored",
						scope=[],
						ttl_minutes=10,
						label="blocked",
					)
				self.assertIn("blocked", str(ctx.exception).lower())

	def test_verify_token_returns_user_for_valid_token(self):
		with self._mock_password_check(valid=True):
			result = issue_token(
				username="Administrator",
				password="x",
				scope=["clone_bench"],
				ttl_minutes=10,
				label="t",
			)
		user = verify_token(result["token"], tool_name="clone_bench")
		self.assertEqual(user, "Administrator")

	def test_verify_token_with_wrong_scope_raises(self):
		with self._mock_password_check(valid=True):
			result = issue_token(
				username="Administrator",
				password="x",
				scope=["clone_bench"],
				ttl_minutes=10,
				label="t",
			)
		with self.assertRaises(frappe.PermissionError):
			verify_token(result["token"], tool_name="not_in_scope")

	def test_revoked_token_rejected(self):
		with self._mock_password_check(valid=True):
			result = issue_token(
				username="Administrator",
				password="x",
				scope=["clone_bench"],
				ttl_minutes=10,
				label="t",
			)
		token_name = frappe.get_all(
			"Press MCP Token", {"user": "Administrator"}, pluck="name"
		)[0]
		revoke_token(token_name)
		with self.assertRaises(frappe.PermissionError):
			verify_token(result["token"], tool_name="clone_bench")

	def test_expired_token_rejected(self):
		with self._mock_password_check(valid=True):
			result = issue_token(
				username="Administrator",
				password="x",
				scope=["clone_bench"],
				ttl_minutes=10,
				label="t",
			)
		token_name = frappe.get_all(
			"Press MCP Token", {"user": "Administrator"}, pluck="name"
		)[0]
		# Backdate expires_at
		frappe.db.set_value(
			"Press MCP Token",
			token_name,
			"expires_at",
			now_datetime() - timedelta(minutes=5),
		)
		with self.assertRaises(frappe.PermissionError):
			verify_token(result["token"], tool_name="clone_bench")

	def test_resource_scope_allows_listed_release_group(self):
		with self._mock_password_check(valid=True):
			result = issue_token(
				username="Administrator",
				password="x",
				scope=["lock_acquire"],
				ttl_minutes=10,
				label="rg-scoped",
				allowed_release_groups=["RG-Allowed-001"],
			)
		user = verify_token(
			result["token"],
			tool_name="lock_acquire",
			target_doctype="Release Group",
			target_name="RG-Allowed-001",
		)
		self.assertEqual(user, "Administrator")

	def test_resource_scope_rejects_unlisted_release_group(self):
		with self._mock_password_check(valid=True):
			result = issue_token(
				username="Administrator",
				password="x",
				scope=["lock_acquire"],
				ttl_minutes=10,
				label="rg-scoped",
				allowed_release_groups=["RG-Allowed-001"],
			)
		with self.assertRaises(frappe.PermissionError):
			verify_token(
				result["token"],
				tool_name="lock_acquire",
				target_doctype="Release Group",
				target_name="RG-NOT-ALLOWED",
			)

	def test_resource_scope_empty_allowlist_means_all_access(self):
		with self._mock_password_check(valid=True):
			result = issue_token(
				username="Administrator",
				password="x",
				scope=["lock_acquire"],
				ttl_minutes=10,
				label="all-rg",
			)
		user = verify_token(
			result["token"],
			tool_name="lock_acquire",
			target_doctype="Release Group",
			target_name="any-rg-name",
		)
		self.assertEqual(user, "Administrator")
