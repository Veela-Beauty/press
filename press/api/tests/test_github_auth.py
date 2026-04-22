# Copyright (c) 2026, Frappe and Contributors
# See license.txt

from __future__ import annotations

from unittest.mock import Mock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.api.github_auth import (
	STATE_CACHE_PREFIX,
	_exchange_and_persist,
	handle_user_auth_callback,
	start_connect,
)


def _mock_github_token_response(**overrides):
	r = Mock()
	r.status_code = 200
	r.ok = True
	r.json.return_value = {
		"access_token": "gho_abc",
		"refresh_token": "ghr_def",
		"expires_in": 28800,
		"refresh_token_expires_in": 15897600,
		"scope": overrides.get("scope", ""),
	}
	r.text = ""
	return r


def _mock_github_user_response(login: str = "testuser"):
	r = Mock()
	r.status_code = 200
	r.ok = True
	r.json.return_value = {"login": login}
	return r


class TestGitHubAuthApi(FrappeTestCase):
	"""Tests for the OAuth connect / callback / disconnect API surface."""

	def tearDown(self):
		frappe.db.rollback()

	def test_start_connect_returns_github_authorize_url(self):
		"""start_connect must return a https://github.com/login/oauth/authorize URL
		with the client_id from Press Settings + a fresh nonce cached.
		"""
		result = start_connect()
		self.assertIn("authorize_url", result)
		self.assertTrue(result["authorize_url"].startswith("https://github.com/login/oauth/authorize"))
		self.assertIn("client_id=", result["authorize_url"])

	def test_exchange_and_persist_happy_path(self):
		"""Happy path: GitHub returns tokens + /user returns login → User GitHub Auth upserted."""
		with patch(
			"press.api.github_auth.requests.post",
			return_value=_mock_github_token_response(),
		), patch(
			"press.api.github_auth.requests.get",
			return_value=_mock_github_user_response(login="octocat"),
		):
			result = _exchange_and_persist(code="fake_code", user_email="Administrator")

		self.assertTrue(result["success"])
		self.assertEqual(result["github_username"], "octocat")

		name = frappe.db.exists("User GitHub Auth", {"user": "Administrator"})
		self.assertTrue(name)
		doc = frappe.get_doc("User GitHub Auth", name)
		self.assertEqual(doc.github_username, "octocat")
		self.assertFalse(doc.is_revoked)

	def test_handle_user_auth_callback_expired_state(self):
		"""Callback must reject when nonce isn't in cache (expired or replayed)."""
		state_payload = {"flow": "user_auth", "nonce": "NEVER_CACHED", "user": "Administrator"}
		result = handle_user_auth_callback(code="anything", state_payload=state_payload)
		self.assertFalse(result["success"])
		self.assertEqual(result["error_code"], "state_expired_or_mismatch")

	def test_handle_user_auth_callback_missing_state_fields(self):
		"""Callback must reject when state payload is malformed."""
		result = handle_user_auth_callback(code="anything", state_payload={})
		self.assertFalse(result["success"])
		self.assertEqual(result["error_code"], "missing_state_fields")

	def test_exchange_and_persist_missing_access_token(self):
		"""If GitHub's response omits access_token, surface the error code."""
		bad = Mock()
		bad.status_code = 200
		bad.ok = True
		bad.json.return_value = {"error": "bad_verification_code"}
		bad.text = ""

		with patch("press.api.github_auth.requests.post", return_value=bad):
			result = _exchange_and_persist(code="bad_code", user_email="Administrator")
		self.assertFalse(result["success"])
		self.assertEqual(result["error_code"], "bad_verification_code")

	def test_handle_user_auth_callback_happy_path_via_cache(self):
		"""Full callback path including nonce caching and token persistence."""
		nonce = "test-nonce-12345"
		cache_key = f"{STATE_CACHE_PREFIX}:{nonce}"
		frappe.cache.set_value(cache_key, "Administrator", expires_in_sec=60)

		state_payload = {"flow": "user_auth", "nonce": nonce, "user": "Administrator"}

		with patch(
			"press.api.github_auth.requests.post",
			return_value=_mock_github_token_response(),
		), patch(
			"press.api.github_auth.requests.get",
			return_value=_mock_github_user_response(login="octocat"),
		):
			result = handle_user_auth_callback(code="fake_code", state_payload=state_payload)

		self.assertTrue(result["success"])
		self.assertEqual(result["github_username"], "octocat")
		# Nonce must be consumed so it can't be replayed
		self.assertIsNone(frappe.cache.get_value(cache_key))
