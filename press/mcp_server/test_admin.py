# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.mcp_server.admin import bulk_revoke, list_all_tokens
from press.mcp_server.auth import issue_token


class TestMCPAdmin(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		mock_lm = MagicMock()
		mock_lm.check_password.return_value = None
		self._lm_patcher = patch.object(
			frappe.local, "login_manager", mock_lm, create=True
		)
		self._lm_patcher.start()
		self.addCleanup(self._lm_patcher.stop)

		# Issue 3 tokens to use as fixtures
		self.tokens = []
		for label in ["alpha", "beta", "gamma"]:
			issue_token(
				username="Administrator",
				password="x",
				scope=[],
				ttl_minutes=10,
				label=label,
			)
			# Resolve docname for revoke testing
			row = frappe.get_all(
				"Press MCP Token",
				{"label": label, "user": "Administrator"},
				pluck="name",
				limit=1,
			)
			self.tokens.append({"label": label, "name": row[0]})

	def tearDown(self):
		frappe.db.delete("Press MCP Token")
		frappe.db.delete("Press MCP Auth Attempt")
		frappe.db.delete("Press MCP Admin Action")

	def test_list_all_tokens_returns_all_three(self):
		result = list_all_tokens()
		labels = [r["label"] for r in result]
		self.assertIn("alpha", labels)
		self.assertIn("beta", labels)
		self.assertIn("gamma", labels)

	def test_list_all_tokens_label_substring_filter(self):
		result = list_all_tokens(filters={"label_substring": "alp"})
		labels = [r["label"] for r in result]
		self.assertIn("alpha", labels)
		self.assertNotIn("beta", labels)

	def test_list_all_tokens_status_filter(self):
		# Revoke one and check the active filter excludes it
		bulk_revoke([self.tokens[0]["name"]], reason="test")
		active = list_all_tokens(filters={"status": "active"})
		labels = [r["label"] for r in active]
		self.assertNotIn("alpha", labels)
		self.assertIn("beta", labels)

	def test_list_all_tokens_blocked_for_non_system(self):
		# Backup + restore user_type
		original_ut = frappe.session.data.user_type if frappe.session.data else "System User"
		if frappe.session.data is None:
			frappe.session.data = frappe._dict()
		frappe.session.data.user_type = "Website User"
		try:
			with self.assertRaises(frappe.PermissionError):
				list_all_tokens()
		finally:
			frappe.session.data.user_type = original_ut

	def test_bulk_revoke_revokes_and_logs(self):
		names = [t["name"] for t in self.tokens[:2]]
		result = bulk_revoke(names, reason="cleanup test")

		self.assertEqual(result["count"], 2)
		# Tokens are revoked
		for n in names:
			self.assertEqual(frappe.db.get_value("Press MCP Token", n, "revoked"), 1)
		# Admin Action rows exist (2 Revoke + 1 Bulk Revoke)
		actions = frappe.get_all("Press MCP Admin Action", fields=["action_type"])
		types = [a["action_type"] for a in actions]
		self.assertEqual(types.count("Revoke"), 2)
		self.assertEqual(types.count("Bulk Revoke"), 1)
		# Each individual Revoke action must link to a distinct token
		revoke_targets = frappe.get_all(
			"Press MCP Admin Action",
			filters={"action_type": "Revoke"},
			pluck="target_token",
		)
		self.assertEqual(set(revoke_targets), set(names))

	def test_bulk_revoke_requires_reason(self):
		with self.assertRaises(frappe.ValidationError):
			bulk_revoke([self.tokens[0]["name"]], reason="")

	def test_bulk_revoke_blocked_for_non_system(self):
		original_ut = frappe.session.data.user_type if frappe.session.data else "System User"
		if frappe.session.data is None:
			frappe.session.data = frappe._dict()
		frappe.session.data.user_type = "Website User"
		try:
			with self.assertRaises(frappe.PermissionError):
				bulk_revoke([self.tokens[0]["name"]], reason="x")
		finally:
			frappe.session.data.user_type = original_ut
