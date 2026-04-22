# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Per-user GitHub App OAuth (User-to-Server) flow.

The mvpstorm-deploy GitHub App (installation 114894173 on Veela-Beauty) is
shared infrastructure. Each developer authorizes the App once via this flow;
thereafter Press mints short-lived user-to-server tokens on demand.

Scope: the OAuth consent inherits the App's declared permissions — no extra
scopes are requested here.

Endpoints (all @frappe.whitelist, under the /api/method/press.api.github_auth.*
wildcard allowlist in auth.py):

  start_connect()   -> returns {"authorize_url": "..."}
  disconnect()      -> revokes grant on GitHub, marks record revoked
  get_status()      -> returns {"connected": bool, "github_username": str|None}

Plus one internal helper imported by press/www/github/authorize.py:

  handle_user_auth_callback(code, state_payload) -> CallbackResult
"""

from __future__ import annotations

import base64
import json
from typing import TypedDict
from urllib.parse import urlencode

import frappe
import requests
from frappe.rate_limiter import rate_limit

from press.press.doctype.user_github_auth.user_github_auth import (
	GitHubAppCredentials,
	get_for_user,
	get_or_create_for_user,
)

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

STATE_CACHE_PREFIX = "github_oauth_state"
STATE_TTL_SECONDS = 600  # 10 minutes
GITHUB_HTTP_TIMEOUT = 5  # seconds


class CallbackResult(TypedDict, total=False):
	success: bool
	github_username: str | None
	error_code: str | None


def _get_redirect_uri() -> str:
	# Use the callback URL already registered with the GitHub App
	return f"{frappe.utils.get_url()}/github/authorize"


def _exchange_and_persist(code: str, user_email: str) -> CallbackResult:
	"""Shared body of the OAuth callback: trade a code for tokens, fetch the
	GitHub username, upsert User GitHub Auth.
	"""
	creds = GitHubAppCredentials.load()

	try:
		token_response = requests.post(
			GITHUB_TOKEN_URL,
			data={
				"client_id": creds.client_id,
				"client_secret": creds.client_secret,
				"code": code,
				"redirect_uri": _get_redirect_uri(),
			},
			headers={"Accept": "application/json"},
			timeout=GITHUB_HTTP_TIMEOUT,
		)
	except requests.Timeout:
		frappe.log_error(title="GitHub OAuth token exchange timed out")
		return {"success": False, "error_code": "github_timeout"}
	except requests.RequestException as exc:
		frappe.log_error(title="GitHub OAuth token exchange network error", message=str(exc))
		return {"success": False, "error_code": "github_unreachable"}

	if token_response.status_code != 200:
		frappe.log_error(
			title="GitHub OAuth token exchange non-200",
			message=f"status={token_response.status_code}\nbody={token_response.text[:500]}",
		)
		return {"success": False, "error_code": "github_token_exchange_failed"}

	data = token_response.json()
	if "access_token" not in data:
		return {"success": False, "error_code": data.get("error", "no_access_token")}

	access_token = data["access_token"]
	refresh_token = data.get("refresh_token")
	scopes = data.get("scope", "")

	try:
		user_resp = requests.get(
			GITHUB_USER_URL,
			headers={
				"Authorization": f"Bearer {access_token}",
				"Accept": "application/vnd.github.v3+json",
			},
			timeout=GITHUB_HTTP_TIMEOUT,
		)
	except requests.Timeout:
		frappe.log_error(title="GitHub /user lookup timed out")
		return {"success": False, "error_code": "github_timeout"}
	except requests.RequestException as exc:
		frappe.log_error(title="GitHub /user lookup network error", message=str(exc))
		return {"success": False, "error_code": "github_user_lookup_failed"}

	if user_resp.status_code != 200:
		return {"success": False, "error_code": "github_user_lookup_failed"}

	github_username = user_resp.json().get("login") or ""

	get_or_create_for_user(
		user=user_email,
		github_username=github_username,
		access_token=access_token,
		refresh_token=refresh_token,
		expires_in=int(data.get("expires_in") or 0),
		refresh_token_expires_in=int(data.get("refresh_token_expires_in") or 0),
		scopes=scopes,
	)
	return {"success": True, "github_username": github_username}


@frappe.whitelist()
def start_connect() -> dict:
	"""Start the per-user GitHub App authorization. Returns the URL the browser should visit.

	Generates a CSRF nonce tied to the current user, cached for 10 min. State
	is base64 JSON so the existing /github/authorize page controller can route
	based on the flow field.
	"""
	if frappe.session.user == "Guest":
		frappe.throw("Log in first", frappe.AuthenticationError)

	creds = GitHubAppCredentials.load()
	nonce = frappe.generate_hash(length=40)
	cache_key = f"{STATE_CACHE_PREFIX}:{nonce}"
	frappe.cache.set_value(cache_key, frappe.session.user, expires_in_sec=STATE_TTL_SECONDS)

	state_payload = {"flow": "user_auth", "nonce": nonce, "user": frappe.session.user}
	state = base64.b64encode(json.dumps(state_payload).encode()).decode()

	params = {
		"client_id": creds.client_id,
		"redirect_uri": _get_redirect_uri(),
		"state": state,
	}
	return {"authorize_url": f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"}


def handle_user_auth_callback(code: str, state_payload: dict) -> CallbackResult:
	"""Called from press/www/github/authorize.py when state.flow == user_auth.

	Returns a CallbackResult:
	  success=True + github_username on success
	  success=False + error_code on failure
	"""
	nonce = state_payload.get("nonce")
	user_from_state = state_payload.get("user")
	if not nonce or not user_from_state:
		return {"success": False, "error_code": "missing_state_fields"}

	cache_key = f"{STATE_CACHE_PREFIX}:{nonce}"
	cached_user = frappe.cache.get_value(cache_key)
	if not cached_user or cached_user != user_from_state:
		return {"success": False, "error_code": "state_expired_or_mismatch"}
	frappe.cache.delete_value(cache_key)

	return _exchange_and_persist(code, user_from_state)


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
