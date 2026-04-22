# Copyright (c) 2026, Frappe and Contributors
# See license.txt

from __future__ import annotations

from unittest.mock import Mock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.press.doctype.user_github_auth.user_github_auth import (
	DEFAULT_ACCESS_TTL_SECONDS,
	get_or_create_for_user,
)


def _create_test_auth(user: str = "Administrator", **overrides):
	"""Persist a User GitHub Auth row for the given user (defaults to Administrator)."""
	doc = get_or_create_for_user(
		user=user,
		github_username=overrides.get("github_username", "test-gh-user"),
		access_token=overrides.get("access_token", "gho_fake_access_token"),
		refresh_token=overrides.get("refresh_token", "ghr_fake_refresh_token"),
		expires_in=overrides.get("expires_in", DEFAULT_ACCESS_TTL_SECONDS),
		refresh_token_expires_in=overrides.get("refresh_token_expires_in", 6 * 30 * 24 * 3600),
		scopes=overrides.get("scopes", ""),
	)
	return doc


class TestUserGitHubAuth(FrappeTestCase):
	"""Tests the UserGitHubAuth doctype controller — refresh, revoke, upsert."""

	def tearDown(self):
		frappe.db.rollback()

	def test_refresh_marks_revoked_on_bad_refresh_token(self):
		"""If GitHub returns error=bad_refresh_token, the record MUST be marked
		revoked and tokens cleared — otherwise users loop forever in a bad state.
		"""
		doc = _create_test_auth()
		fake_response = Mock()
		fake_response.status_code = 200  # GitHub returns 200 with error body
		fake_response.ok = True
		fake_response.json.return_value = {"error": "bad_refresh_token"}

		with patch(
			"press.press.doctype.user_github_auth.user_github_auth.requests.post",
			return_value=fake_response,
		):
			result = doc._do_refresh()

		self.assertFalse(result)
		doc.reload()
		self.assertTrue(doc.is_revoked)
		# Tokens cleared
		self.assertIsNone(doc.get_password("access_token", raise_exception=False))
		self.assertIsNone(doc.get_password("refresh_token", raise_exception=False))

	def test_refresh_marks_revoked_on_401(self):
		"""HTTP 401 from GitHub token endpoint = refresh token no longer valid."""
		doc = _create_test_auth()
		fake_response = Mock()
		fake_response.status_code = 401
		fake_response.ok = False
		fake_response.json.return_value = {}
		fake_response.text = ""

		with patch(
			"press.press.doctype.user_github_auth.user_github_auth.requests.post",
			return_value=fake_response,
		):
			result = doc._do_refresh()

		self.assertFalse(result)
		doc.reload()
		self.assertTrue(doc.is_revoked)

	def test_refresh_happy_path_updates_tokens(self):
		"""200 + new tokens = access_token + expires_at updated, record still active."""
		doc = _create_test_auth()
		fake_response = Mock()
		fake_response.status_code = 200
		fake_response.ok = True
		fake_response.json.return_value = {
			"access_token": "gho_NEW_token",
			"refresh_token": "ghr_NEW_refresh",
			"expires_in": 28800,
			"refresh_token_expires_in": 15897600,
			"scope": "repo",
		}

		with patch(
			"press.press.doctype.user_github_auth.user_github_auth.requests.post",
			return_value=fake_response,
		):
			result = doc._do_refresh()

		self.assertTrue(result)
		doc.reload()
		self.assertFalse(doc.is_revoked)
		self.assertEqual(doc.get_password("access_token"), "gho_NEW_token")
		self.assertEqual(doc.get_password("refresh_token"), "ghr_NEW_refresh")
		self.assertEqual(doc.scopes, "repo")

	def test_get_fresh_access_token_returns_none_if_revoked(self):
		doc = _create_test_auth()
		doc.is_revoked = 1
		doc.save(ignore_permissions=True)
		self.assertIsNone(doc.get_fresh_access_token())
