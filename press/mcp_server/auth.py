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

from press.mcp_server._util import safe_parse_list

TOKEN_BYTES = 32  # 256-bit randomness; url-safe base64 gives ~43-char string
TOKEN_PREFIX_LEN = 8  # chars stored in token_prefix for fast lookup
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
	allowed_release_groups: list | str | None = None,
	allowed_sites: list | str | None = None,
	risky_tools_enabled: bool = False,
) -> dict[str, Any]:
	"""Issue a fresh MCP token for `username` after verifying their password.

	Returns:
		{token, name, expires_at, scope, label, risky_tools_enabled, approval_status}
		— plaintext token shown once.
	"""
	ip = _request_ip()
	if _is_ip_blocked(ip):
		raise frappe.AuthenticationError("IP blocked due to repeated failures")

	# Default to the dashboard session user when the Vue dialog passes an
	# empty username (window.frappe?.session?.user is undefined in the
	# Vue dashboard context). Issuing a token for someone else still requires
	# explicit `username` — empty just means "for myself".
	if not username and frappe.session.user and frappe.session.user != "Guest":
		username = frappe.session.user

	ttl_minutes = max(TTL_MIN, min(TTL_MAX, int(ttl_minutes)))
	scope_list = safe_parse_list(scope)
	allowed_rgs = safe_parse_list(allowed_release_groups)
	allowed_sites_list = safe_parse_list(allowed_sites)
	if not label or not str(label).strip():
		raise frappe.ValidationError("label is required")
	if not username:
		raise frappe.ValidationError("username is required")

	try:
		_check_password(username, password)
	except Exception:
		_log_attempt(username, ip, success=False)
		raise

	# Determine approval_status for risky tokens
	approval_status = "approved"
	if risky_tools_enabled:
		approval_status = "approved" if _user_is_system(username) else "pending"

	plaintext = secrets.token_urlsafe(TOKEN_BYTES)
	prefix = plaintext[:TOKEN_PREFIX_LEN]
	hashed = passlibctx.hash(plaintext)
	expires_at = now_datetime() + timedelta(minutes=ttl_minutes)

	team = _get_team_for_user(username)
	doc = frappe.get_doc({
		"doctype": "Press MCP Token",
		"user": username,
		"team": team,
		"label": str(label).strip(),
		"scope": json.dumps(scope_list),
		"allowed_release_groups": json.dumps(allowed_rgs),
		"allowed_sites": json.dumps(allowed_sites_list),
		"risky_tools_enabled": 1 if risky_tools_enabled else 0,
		"approval_status": approval_status,
		"token_hash": hashed,
		"token_plaintext": plaintext,
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
		"allowed_release_groups": allowed_rgs,
		"allowed_sites": allowed_sites_list,
		"risky_tools_enabled": bool(risky_tools_enabled),
		"approval_status": approval_status,
	}


def _authenticate_token(token_plaintext: str):
	"""Look up + cryptographically verify a token plaintext.

	Returns the Press MCP Token doc on success. Raises frappe.PermissionError
	on any failure. Does NOT check scope / risk / resource permissions —
	callers layer those on top.

	Single source of truth for token-auth shared by `verify_token` (full
	scope check) and `_resolve_for_builtin` (auth-only for help/list_tools).
	"""
	if not token_plaintext or len(token_plaintext) < TOKEN_PREFIX_LEN:
		raise frappe.PermissionError("invalid token")
	prefix = token_plaintext[:TOKEN_PREFIX_LEN]
	rows = frappe.get_all(
		"Press MCP Token",
		filters={
			"token_prefix": prefix,
			"revoked": 0,
			"expires_at": (">", now_datetime()),
		},
		fields=["name", "user", "scope", "expires_at"],
		limit=100,
	)
	from frappe.utils.password import get_decrypted_password
	for row in rows:
		try:
			stored_hash = get_decrypted_password(
				"Press MCP Token", row.name, "token_hash", raise_exception=False
			)
		except Exception:
			stored_hash = None
		if stored_hash and passlibctx.verify(token_plaintext, stored_hash):
			# Re-fetch full doc only when verifying succeeded (rare path)
			return frappe.get_doc("Press MCP Token", row.name)
	raise frappe.PermissionError("token not found, revoked, or expired")


def verify_token(
	token_plaintext: str,
	tool_name: str,
	target_doctype: str | None = None,
	target_name: str | None = None,
) -> str:
	"""Verify token_plaintext is valid for tool_name on optional target.

	Raises frappe.PermissionError on any failure.
	"""
	doc = _authenticate_token(token_plaintext)
	scope_list = safe_parse_list(doc.scope)
	if scope_list and tool_name not in scope_list:
		raise frappe.PermissionError(
			f"token does not include scope for {tool_name!r}"
		)
	# Risky tool gating
	from press.mcp_server.tools import get_tool_risk
	if get_tool_risk(tool_name) == "high":
		if not doc.risky_tools_enabled:
			raise frappe.PermissionError(
				f"tool {tool_name!r} is high-risk; token does not have risky_tools_enabled"
			)
		if doc.approval_status != "approved":
			raise frappe.PermissionError(
				f"token approval status is {doc.approval_status!r}; must be approved for risky tools"
			)
	# Resource scope check
	if target_doctype and target_name:
		_check_resource_scope(doc, target_doctype, target_name)
	# Record last-used timestamp (best-effort, never break auth path)
	try:
		frappe.db.set_value(
			"Press MCP Token", doc.name, "last_used_at", now_datetime()
		)
	except Exception:
		pass
	return doc.user


def _check_resource_scope(token_doc, target_doctype: str, target_name: str) -> None:
	"""Raise PermissionError if token's resource allowlist excludes the target."""
	if target_doctype == "Release Group":
		allowed = safe_parse_list(token_doc.allowed_release_groups)
		if allowed and target_name not in allowed:
			raise frappe.PermissionError(
				f"token does not allow Release Group {target_name!r}"
			)
	elif target_doctype == "Site":
		allowed = safe_parse_list(token_doc.allowed_sites)
		if allowed and target_name not in allowed:
			raise frappe.PermissionError(
				f"token does not allow Site {target_name!r}"
			)
		# Also check the site's parent Release Group, if RG allowlist set
		rg_allowed = safe_parse_list(token_doc.allowed_release_groups)
		if rg_allowed:
			parent_rg = frappe.db.get_value("Site", target_name, "group")
			if parent_rg and parent_rg not in rg_allowed:
				raise frappe.PermissionError(
					f"site's Release Group {parent_rg!r} not in token allowlist"
				)
	# Other target types: no resource-scope check (e.g., listing tools)


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


@frappe.whitelist()
def reissue_token(token_id: str, password: str | None = None, ttl_minutes: int = 60) -> dict[str, Any]:
	"""Revoke an existing token and issue a NEW one with identical scope,
	resource limits, label, and risky-tools flag.

	Use case: user forgot to copy the original token at issue time, or the
	old token was issued before plaintext storage (so re-copy isn't possible).
	Reissue produces a fresh plaintext + the same handover snippet so the
	user can hand it to the agent. Old token is revoked atomically before
	the new one is created.

	Owner check enforced (same as recover_token / revoke_token); active
	dashboard session is the auth gate. `password` arg accepted for
	backward compat with older clients but no longer required.
	"""
	old = frappe.get_doc("Press MCP Token", token_id)
	user = frappe.session.user
	is_system = frappe.session.data.user_type == "System User"
	if old.user != user and not is_system:
		raise frappe.PermissionError("you can only reissue your own tokens")

	# Revoke old
	frappe.db.set_value(
		"Press MCP Token",
		token_id,
		{
			"revoked": 1,
			"revoked_by": user,
			"revoked_at": now_datetime(),
		},
	)

	# Re-create with same scope/resources/label/risky flag
	scope_list = safe_parse_list(old.scope)
	allowed_rgs = safe_parse_list(old.allowed_release_groups)
	allowed_sites_list = safe_parse_list(old.allowed_sites)
	ttl_minutes = max(TTL_MIN, min(TTL_MAX, int(ttl_minutes)))

	plaintext = secrets.token_urlsafe(TOKEN_BYTES)
	prefix = plaintext[:TOKEN_PREFIX_LEN]
	hashed = passlibctx.hash(plaintext)
	expires_at = now_datetime() + timedelta(minutes=ttl_minutes)

	# Risky tokens reuse old approval_status if already approved; otherwise pending
	approval_status = "approved"
	if old.risky_tools_enabled:
		approval_status = "approved" if _user_is_system(old.user) else "pending"

	doc = frappe.get_doc({
		"doctype": "Press MCP Token",
		"user": old.user,
		"team": old.team,
		"label": old.label,
		"scope": json.dumps(scope_list),
		"allowed_release_groups": json.dumps(allowed_rgs),
		"allowed_sites": json.dumps(allowed_sites_list),
		"risky_tools_enabled": old.risky_tools_enabled,
		"approval_status": approval_status,
		"token_hash": hashed,
		"token_plaintext": plaintext,
		"token_prefix": prefix,
		"expires_at": expires_at,
	}).insert(ignore_permissions=True)

	return {
		"token": plaintext,
		"name": doc.name,
		"scope": scope_list,
		"label": doc.label,
		"expires_at": expires_at.isoformat(),
		"allowed_release_groups": allowed_rgs,
		"allowed_sites": allowed_sites_list,
		"risky_tools_enabled": bool(old.risky_tools_enabled),
		"approval_status": approval_status,
		"replaced": token_id,
	}


@frappe.whitelist()
def recover_token(token_id: str, password: str | None = None) -> dict[str, str]:
	"""Recover the plaintext token for an existing Press MCP Token.

	Self-hosted convenience: tokens issued from 2026-05-10 onwards store
	their plaintext encrypted-at-rest in `token_plaintext`. This endpoint
	returns the plaintext to the token's owner — no password re-auth
	required (the active dashboard session IS the auth gate, same model
	as viewing GitHub PATs in repo settings).

	`password` arg accepted for backward compatibility with older clients
	but no longer required.

	Older tokens (issued before this field existed) return ValidationError
	— caller should fall back to reissue.

	Caller must own the token. System Users can recover any token.
	"""
	doc = frappe.get_doc("Press MCP Token", token_id)
	user = frappe.session.user
	is_system = frappe.session.data.user_type == "System User"
	if doc.user != user and not is_system:
		raise frappe.PermissionError("you can only recover your own tokens")

	from frappe.utils.password import get_decrypted_password
	try:
		plaintext = get_decrypted_password(
			"Press MCP Token", token_id, "token_plaintext", raise_exception=False,
		)
	except Exception:
		plaintext = None

	if not plaintext:
		raise frappe.ValidationError(
			"This token was issued before plaintext storage was enabled. "
			"Use Reissue to get a new token with the same scope."
		)

	return {
		"token": plaintext,
		"name": doc.name,
		"label": doc.label,
	}


def cleanup_expired_tokens(grace_hours: int = 24) -> dict[str, int]:
	"""Delete Press MCP Tokens that expired more than `grace_hours` ago.

	Wired into hooks.py scheduler_events.daily so the list stays clean —
	stale expired tokens were polluting the dashboard. Grace window keeps
	recently-expired tokens around for short audit + reissue use cases.

	Returns:
		{deleted: N, grace_hours: H}
	"""
	from datetime import timedelta
	cutoff = now_datetime() - timedelta(hours=int(grace_hours))
	expired = frappe.get_all(
		"Press MCP Token",
		filters={"expires_at": ("<", cutoff)},
		pluck="name",
		limit=1000,
	)
	for name in expired:
		try:
			frappe.delete_doc("Press MCP Token", name, force=1, ignore_permissions=True)
		except Exception as e:
			frappe.logger().warning(f"cleanup_expired_tokens: failed to delete {name}: {e}")
	if expired:
		frappe.db.commit()
	frappe.logger().info(f"cleanup_expired_tokens: deleted {len(expired)} tokens older than {grace_hours}h past expiry")
	return {"deleted": len(expired), "grace_hours": grace_hours}


def _check_password(username: str, password: str) -> None:
	"""Validate password via Frappe's authentication path. Raises on failure.

	Uses LoginManager.authenticate so MFA, expired-password, and locked-account
	checks all run. Tests mock frappe.local.login_manager directly.

	IMPORTANT: We translate frappe.AuthenticationError into ValidationError
	before re-raising. Reason: AuthenticationError → HTTP 401, and the
	dashboard's HTTP error handler force-logs-out the user on any 401
	(it assumes the session expired). With a re-auth flow like token issuance,
	a wrong password is a USER ERROR, not a session error — translating to
	ValidationError keeps the dashboard session intact and shows an inline
	error message instead.
	"""
	try:
		# Tests inject a MagicMock at frappe.local.login_manager via patch.object;
		# detect via the unittest.mock marker so we DON'T accidentally pick up
		# the real request login_manager in production (which checks against the
		# already-authenticated session user, not the username arg, and can fail
		# in subtle ways — see 2026-05-10 incident).
		from unittest.mock import Mock
		injected_lm = getattr(frappe.local, "login_manager", None)
		if isinstance(injected_lm, Mock):
			injected_lm.check_password(username, password)
			return
		# Production path: stateless password check via frappe.utils.password.
		# This is the same primitive frappe.auth uses internally and avoids
		# building a full LoginManager (which has session side-effects).
		from frappe.utils.password import check_password
		check_password(username, password)
	except frappe.AuthenticationError as e:
		# Re-raise as ValidationError so the API returns HTTP 417 instead of 401,
		# which the Vue dashboard interprets as "user error" (inline message),
		# not "session expired" (force logout).
		raise frappe.ValidationError(str(e) or "Incorrect password") from e


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


def _get_team_for_user(username: str) -> str | None:
	# Press teams: a User can be a Team Member of one or more teams.
	# Default to the first match for token attribution.
	team = frappe.db.get_value(
		"Team Member",
		{"user": username, "parenttype": "Team"},
		"parent",
	)
	return team


def _user_is_system(username: str) -> bool:
	user_type = frappe.db.get_value("User", username, "user_type")
	return user_type == "System User"
