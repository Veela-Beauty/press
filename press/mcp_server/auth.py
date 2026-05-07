# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""MCP server authentication: token issue/verify/revoke + brute-force guard.

Tokens are issued via password-auth (a fresh-token flow handles password
rotation better than long-lived API key pairs). Plaintext is shown ONCE
on issue; only the hash is stored.
"""
from __future__ import annotations

import json
import secrets
from datetime import timedelta
from typing import Any

import frappe
from frappe.utils import add_to_date, now_datetime
from frappe.utils.password import passlibctx

TOKEN_BYTES = 32  # 256-bit randomness; url-safe base64 gives ~43-char string
TTL_MIN = 1
TTL_MAX = 1440  # 24 hours

BRUTE_FORCE_THRESHOLD = 5
BRUTE_FORCE_WINDOW_MINUTES = 5
BRUTE_FORCE_BLOCK_MINUTES = 60


@frappe.whitelist(allow_guest=True)
def issue_token(
	username: str,
	password: str,
	scope: list | str,
	ttl_minutes: int = 60,
	label: str | None = None,
) -> dict[str, Any]:
	"""Issue a fresh MCP token for `username` after verifying their password.

	Returns:
		{token, name, expires_at, scope, label} — plaintext token shown once.
	"""
	ip = _request_ip()
	if _is_ip_blocked(ip):
		raise frappe.AuthenticationError("IP blocked due to repeated failures")

	ttl_minutes = max(TTL_MIN, min(TTL_MAX, int(ttl_minutes)))
	scope_list = _normalize_scope(scope)
	if not label or not str(label).strip():
		raise frappe.ValidationError("label is required")

	try:
		_check_password(username, password)
	except Exception:
		_log_attempt(username, ip, success=False)
		raise

	plaintext = secrets.token_urlsafe(TOKEN_BYTES)
	prefix = plaintext[:8]
	hashed = passlibctx.hash(plaintext)
	expires_at = now_datetime() + timedelta(minutes=ttl_minutes)

	team = _get_team_for_user(username)
	doc = frappe.get_doc({
		"doctype": "Press MCP Token",
		"user": username,
		"team": team,
		"label": str(label).strip(),
		"scope": json.dumps(scope_list),
		"token_hash": hashed,
		"token_prefix": prefix,
		"expires_at": expires_at,
	}).insert(ignore_permissions=True)

	_log_attempt(username, ip, success=True)

	return {
		"token": plaintext,
		"name": doc.name,
		"scope": scope_list,
		"label": doc.label,
		"expires_at": expires_at.isoformat(),
	}


def verify_token(token_plaintext: str, tool_name: str) -> str:
	"""Verify token_plaintext is valid for tool_name. Returns User docname.

	Raises frappe.PermissionError on any failure (expired/revoked/wrong scope).
	"""
	if not token_plaintext or len(token_plaintext) < 8:
		raise frappe.PermissionError("invalid token")
	prefix = token_plaintext[:8]
	rows = frappe.get_all(
		"Press MCP Token",
		filters={
			"token_prefix": prefix,
			"revoked": 0,
			"expires_at": (">", now_datetime()),
		},
		fields=["name", "user", "scope"],
	)
	for row in rows:
		doc = frappe.get_doc("Press MCP Token", row.name)
		# get_password returns the bcrypt hash (Frappe Fernet-decrypts the stored value)
		stored_hash = doc.get_password("token_hash", raise_exception=False)
		if stored_hash and passlibctx.verify(token_plaintext, stored_hash):
			scope_list = _normalize_scope(doc.scope)
			if scope_list and tool_name not in scope_list:
				raise frappe.PermissionError(
					f"token does not include scope for {tool_name!r}"
				)
			# Record last-used timestamp (best-effort, never break auth path)
			try:
				frappe.db.set_value(
					"Press MCP Token", doc.name, "last_used_at", now_datetime()
				)
			except Exception:
				pass
			return doc.user
	raise frappe.PermissionError("token not found, revoked, or expired")


@frappe.whitelist()
def revoke_token(token_id: str) -> dict[str, str]:
	"""Revoke a token by its docname. Caller must own the token OR be System User."""
	doc = frappe.get_doc("Press MCP Token", token_id)
	user = frappe.session.user
	is_system = frappe.session.data.user_type == "System User"
	if doc.user != user and not is_system:
		raise frappe.PermissionError("you can only revoke your own tokens")
	frappe.db.set_value(
		"Press MCP Token",
		token_id,
		{
			"revoked": 1,
			"revoked_by": user,
			"revoked_at": now_datetime(),
		},
	)
	return {"status": "revoked", "name": token_id}


def _check_password(username: str, password: str) -> None:
	"""Validate password via Frappe's login manager. Raises on failure."""
	# Tests mock frappe.local.login_manager with MagicMock (create=True).
	# Production uses Frappe's standard check_password utility.
	lm = getattr(frappe.local, "login_manager", None)
	if lm is not None:
		lm.check_password(username, password)
		return
	from frappe.utils.password import check_password as _cp
	_cp(username, password)


def _request_ip() -> str:
	return getattr(frappe.local, "request_ip", "0.0.0.0") or "0.0.0.0"


def _log_attempt(username: str, ip: str, success: bool) -> None:
	try:
		frappe.get_doc({
			"doctype": "Press MCP Auth Attempt",
			"username": username or "",
			"ip_address": ip,
			"success": 1 if success else 0,
		}).insert(ignore_permissions=True)
	except Exception:
		# Logging must never break auth path
		pass


def _is_ip_blocked(ip: str) -> bool:
	if not ip or ip == "0.0.0.0":
		return False
	window_start = add_to_date(now_datetime(), minutes=-BRUTE_FORCE_WINDOW_MINUTES)
	failed_count = frappe.db.count(
		"Press MCP Auth Attempt",
		{
			"ip_address": ip,
			"success": 0,
			"creation": (">=", window_start),
		},
	)
	return failed_count >= BRUTE_FORCE_THRESHOLD


def _normalize_scope(scope) -> list:
	if scope is None:
		return []
	if isinstance(scope, str):
		try:
			parsed = json.loads(scope)
			return list(parsed) if isinstance(parsed, list) else []
		except (ValueError, TypeError):
			return []
	if isinstance(scope, list):
		return [str(s) for s in scope]
	return []


def _get_team_for_user(username: str) -> str | None:
	# Press teams: a User can be a Team Member of one or more teams.
	# Default to the first match for token attribution.
	team = frappe.db.get_value(
		"Team Member",
		{"user": username, "parenttype": "Team"},
		"parent",
	)
	return team
