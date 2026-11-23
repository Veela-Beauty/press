# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""recover_token returns a token's plaintext to its owner only (0.7.59). Mock-only: the token document, the session
and the decryption are patched (on the press-ctrl test runner's MOCK_ONLY list)."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.mcp_server import auth


class TestRecoverToken(FrappeTestCase):
	def _recover(self, caller, user_type="System User"):
		session = frappe._dict(user=caller, data=frappe._dict(user_type=user_type))
		with (
			patch.object(auth.frappe, "get_doc", return_value=frappe._dict(user="owner@example.com")),
			patch.object(auth.frappe, "session", session),
			patch("frappe.utils.password.get_decrypted_password", return_value="mcp_secret_value") as decrypt,
		):
			try:
				return auth.recover_token("MCPT-1"), decrypt
			except frappe.PermissionError:
				return "refused", decrypt

	def test_the_owner_gets_the_token(self):
		result, decrypt = self._recover("owner@example.com")
		self.assertEqual(result.get("token"), "mcp_secret_value")
		decrypt.assert_called_once()

	def test_another_system_user_is_refused_before_decryption(self):
		result, decrypt = self._recover("member@example.com", user_type="System User")
		self.assertEqual(result, "refused")
		decrypt.assert_not_called()

	def test_a_website_user_is_refused(self):
		result, _ = self._recover("customer@example.com", user_type="Website User")
		self.assertEqual(result, "refused")
