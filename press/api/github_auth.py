# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Per-user GitHub App OAuth (User-to-Server) flow.

The mvpstorm-deploy GitHub App (installation 114894173 on Veela-Beauty) is
shared infrastructure. Each developer authorizes the App once via this flow;
thereafter Press mints short-lived user-to-server tokens on demand.

Scope: the OAuth consent inherits the App's declared permissions — no extra
scopes are requested here.

Endpoints (all @frappe.whitelist, under the /api/method/press.api.github_auth.*
wildcard allowlist in auth.py).

  start_connect()              -> returns {"authorize_url": "..."}
  oauth_callback(code, state)  -> exchanges code, persists User GitHub Auth
  disconnect()                 -> revokes grant on GitHub, marks record revoked
  get_status()                 -> returns {"connected": bool, "username": str|None}
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import frappe
import requests
from frappe.rate_limiter import rate_limit

from press.press.doctype.user_github_auth.user_github_auth import (
	get_for_user,
	get_or_create_for_user,
)

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

STATE_CACHE_PREFIX = "github_oauth_state"
STATE_TTL_SECONDS = 600  # 10 minutes


def _get_client_credentials() -> tuple[str, str, str]:
	client_id = frappe.db.get_single_value("Press Settings", "github_app_client_id")
	client_secret = frappe.db.get_single_value("Press Settings", "github_app_client_secret")
	if not client_id or not client_secret:
		frappe.throw("GitHub App credentials not configured in Press Settings", frappe.ValidationError)
	base_url = frappe.utils.get_url()
	return client_id, client_secret, base_url


def _get_redirect_uri() -> str:
	# Use the callback URL already registered with the GitHub App
	base_url = frappe.utils.get_url()
	return f"{base_url}/github/authorize"


@frappe.whitelist()
def start_connect() -> dict:
	"""Start the per-user GitHub App authorization. Returns the URL the browser should visit.

	Generates a CSRF nonce tied to the current user, cached for 10 min. State is
	base64 JSON so the existing /github/authorize page controller can route
	based on the flow field.
	"""
	import base64, json
	if frappe.session.user == "Guest":
		frappe.throw("Log in first", frappe.AuthenticationError)

	client_id, _, _ = _get_client_credentials()
	nonce = frappe.generate_hash(length=40)
	cache_key = f"{STATE_CACHE_PREFIX}:{nonce}"
	frappe.cache.set_value(cache_key, frappe.session.user, expires_in_sec=STATE_TTL_SECONDS)

	state_payload = {"flow": "user_auth", "nonce": nonce, "user": frappe.session.user}
	state = base64.b64encode(json.dumps(state_payload).encode()).decode()

	params = {
		"client_id": client_id,
		"redirect_uri": _get_redirect_uri(),
		"state": state,
	}
	return {"authorize_url": f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"}


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=20, seconds=60)
def oauth_callback(code: str | None = None, state: str | None = None, **kwargs):
	"""Handle the OAuth redirect from GitHub.

	The user's browser lands here via a 302 from GitHub. We:
	  1. Validate the state (ties the callback to the user who started it).
	  2. Exchange the code for access+refresh tokens.
	  3. Fetch the GitHub username.
	  4. Persist the User GitHub Auth record.
	  5. Redirect back to the Press dashboard with success/error markers.
	"""
	if not code or not state:
		return _redirect_to_dashboard(error="missing_code_or_state")

	cache_key = f"{STATE_CACHE_PREFIX}:{state}"
	user_from_state = frappe.cache.get_value(cache_key)
	if not user_from_state:
		return _redirect_to_dashboard(error="state_expired_or_invalid")
	frappe.cache.delete_value(cache_key)

	client_id, client_secret, _ = _get_client_credentials()

	try:
		token_response = requests.post(
			GITHUB_TOKEN_URL,
			data={
				"client_id": client_id,
				"client_secret": client_secret,
				"code": code,
				"redirect_uri": _get_redirect_uri(),
			},
			headers={"Accept": "application/json"},
			timeout=10,
		)
	except requests.RequestException as exc:
		frappe.log_error(title="GitHub OAuth callback network error", message=str(exc))
		return _redirect_to_dashboard(error="github_unreachable")

	if token_response.status_code != 200:
		frappe.log_error(
			title="GitHub OAuth token exchange failed",
			message=f"status={token_response.status_code}\nbody={token_response.text[:500]}",
		)
		return _redirect_to_dashboard(error="github_token_exchange_failed")

	data = token_response.json()
	if "access_token" not in data:
		return _redirect_to_dashboard(
			error=data.get("error", "no_access_token"),
		)

	access_token = data["access_token"]
	refresh_token = data.get("refresh_token")
	expires_in = int(data.get("expires_in", 28800))  # 8h default
	refresh_expires_in = int(data.get("refresh_token_expires_in") or 15897600)  # 6mo default
	scopes = data.get("scope", "")

	# Fetch GitHub username to confirm identity + for display
	try:
		user_resp = requests.get(
			GITHUB_USER_URL,
			headers={
				"Authorization": f"Bearer {access_token}",
				"Accept": "application/vnd.github.v3+json",
			},
			timeout=10,
		)
	except requests.RequestException as exc:
		frappe.log_error(title="GitHub /user lookup failed", message=str(exc))
		return _redirect_to_dashboard(error="github_user_lookup_failed")

	if user_resp.status_code != 200:
		return _redirect_to_dashboard(error="github_user_lookup_failed")

	github_username = user_resp.json().get("login") or ""

	get_or_create_for_user(
		user=user_from_state,
		github_username=github_username,
		access_token=access_token,
		refresh_token=refresh_token,
		expires_in=expires_in,
		refresh_token_expires_in=refresh_expires_in,
		scopes=scopes,
	)
	return _redirect_to_dashboard(success=github_username)


@frappe.whitelist()
def disconnect() -> dict:
	"""Revoke the current user's GitHub App grant and mark the Press record revoked."""
	if frappe.session.user == "Guest":
		frappe.throw("Log in first", frappe.AuthenticationError)
	doc = get_for_user(frappe.session.user)
	if not doc:
		return {"disconnected": True, "already_disconnected": True}
	doc.revoke_on_github()
	doc.mark_revoked(reason="User clicked Disconnect")
	return {"disconnected": True, "github_revoked": True}


@frappe.whitelist()
def get_status() -> dict:
	"""Return the current user's GitHub connection status for the Settings UI."""
	if frappe.session.user == "Guest":
		return {"connected": False, "logged_in": False}
	doc = get_for_user(frappe.session.user)
	if not doc:
		return {"connected": False}
	return {
		"connected": True,
		"github_username": doc.github_username,
		"connected_on": doc.connected_on,
		"last_used_on": doc.last_used_on,
		"scopes": doc.scopes,
	}


def _redirect_to_dashboard(success: str | None = None, error: str | None = None):
	"""Emit a 302 back to the Press dashboard with query params for UX."""
	base = frappe.utils.get_url()
	if success:
		target = f"{base}/dashboard/settings/developer?github_connected={success}"
	else:
		target = f"{base}/dashboard/settings/developer?github_error={error or 'unknown'}"
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = target


def handle_user_auth_callback(code: str, state_payload: dict) -> tuple[bool, str]:
	"""Called from press/www/github/authorize.py when state.flow == user_auth.

	Returns (success, message_or_username_or_error_code).
	"""
	nonce = state_payload.get("nonce")
	user_from_state = state_payload.get("user")
	if not nonce or not user_from_state:
		return False, "missing_state_fields"

	cache_key = f"{STATE_CACHE_PREFIX}:{nonce}"
	cached_user = frappe.cache.get_value(cache_key)
	if not cached_user or cached_user != user_from_state:
		return False, "state_expired_or_mismatch"
	frappe.cache.delete_value(cache_key)

	client_id, client_secret, _ = _get_client_credentials()
	try:
		token_response = requests.post(
			GITHUB_TOKEN_URL,
			data={
				"client_id": client_id,
				"client_secret": client_secret,
				"code": code,
				"redirect_uri": _get_redirect_uri(),
			},
			headers={"Accept": "application/json"},
			timeout=10,
		)
	except requests.RequestException as exc:
		frappe.log_error(title="GitHub OAuth (user) network error", message=str(exc))
		return False, "github_unreachable"

	if token_response.status_code != 200:
		frappe.log_error(
			title="GitHub OAuth (user) token exchange failed",
			message=f"status={token_response.status_code}\nbody={token_response.text[:500]}",
		)
		return False, "github_token_exchange_failed"

	data = token_response.json()
	if "access_token" not in data:
		return False, data.get("error", "no_access_token")

	access_token = data["access_token"]
	refresh_token = data.get("refresh_token")
	expires_in = int(data.get("expires_in", 28800))
	refresh_expires_in = int(data.get("refresh_token_expires_in") or 15897600)
	scopes = data.get("scope", "")

	try:
		user_resp = requests.get(
			GITHUB_USER_URL,
			headers={
				"Authorization": f"Bearer {access_token}",
				"Accept": "application/vnd.github.v3+json",
			},
			timeout=10,
		)
	except requests.RequestException as exc:
		frappe.log_error(title="GitHub /user lookup (user flow) failed", message=str(exc))
		return False, "github_user_lookup_failed"

	if user_resp.status_code != 200:
		return False, "github_user_lookup_failed"

	github_username = user_resp.json().get("login") or ""

	get_or_create_for_user(
		user=user_from_state,
		github_username=github_username,
		access_token=access_token,
		refresh_token=refresh_token,
		expires_in=expires_in,
		refresh_token_expires_in=refresh_expires_in,
		scopes=scopes,
	)
	return True, github_username
