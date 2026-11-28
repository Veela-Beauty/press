# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""recover_token returns a token's plaintext to its owner only (0.7.59). Mock-only: the token document, the session
and the decryption are patched (on the press-ctrl test runner's MOCK_ONLY list)."""

import pathlib
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press import overrides
from press.mcp_server import auth

PRESS = pathlib.Path(__file__).parents[1]  # this file's own tree (the press-ctrl runner copies the tree with it)


class TestRecoverToken(FrappeTestCase):
	def _recover(self, caller, user_type="System User", confirmed=True):
		session = frappe._dict(user=caller, data=frappe._dict(user_type=user_type))
		confirm = (
			patch("press.mcp_server.token_confirm.confirmed_how", return_value="password")
			if confirmed
			else patch("press.mcp_server.token_confirm.confirmed_how", side_effect=frappe.PermissionError("confirm"))
		)
		with (
			patch.object(auth.frappe, "get_doc", return_value=frappe._dict(user="owner@example.com", name="MCPT-1")),
			patch.object(auth.frappe, "session", session),
			patch("frappe.utils.password.get_decrypted_password", return_value="mcp_secret_value") as decrypt,
			confirm,
			patch("press.mcp_server.token_edit.log_token_action"),
		):
			try:
				return auth.recover_token("MCPT-1"), decrypt
			except frappe.PermissionError:
				return "refused", decrypt

	def test_the_owner_gets_the_token(self):
		result, decrypt = self._recover("owner@example.com")
		self.assertEqual(result.get("token"), "mcp_secret_value")
		decrypt.assert_called_once()

	def test_the_owner_without_a_recent_confirm_is_refused_before_decryption(self):
		"""PRS-SP-22: an open session alone no longer copies a token."""
		result, decrypt = self._recover("owner@example.com", confirmed=False)
		self.assertEqual(result, "refused")
		decrypt.assert_not_called()

	def test_another_system_user_is_refused_before_decryption(self):
		result, decrypt = self._recover("member@example.com", user_type="System User")
		self.assertEqual(result, "refused")
		decrypt.assert_not_called()

	def test_a_website_user_is_refused(self):
		result, _ = self._recover("customer@example.com", user_type="Website User")
		self.assertEqual(result, "refused")


class TestGetPasswordOverride(FrappeTestCase):
	"""frappe.client.get_password hands any System Manager any Password field; MCP tokens are refused (0.7.59)."""

	def test_an_mcp_token_is_refused_before_decryption(self):
		with patch("frappe.client.get_password") as frappe_get_password, self.assertRaises(frappe.PermissionError):
			overrides.get_password("Press MCP Token", "MCPT-1", "token_plaintext")
		frappe_get_password.assert_not_called()

	def test_other_doctypes_go_to_frappe(self):
		with patch("frappe.client.get_password", return_value="kept") as frappe_get_password:
			self.assertEqual(overrides.get_password("Email Account", "Support", "password"), "kept")
		frappe_get_password.assert_called_once_with("Email Account", "Support", "password")

	def test_hooks_route_frappe_get_password_here(self):
		hooks = (PRESS / "hooks.py").read_text()
		self.assertIn('"frappe.client.get_password": "press.overrides.get_password"', hooks)
