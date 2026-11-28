# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Confirm it's you, before a token is shown, copied, reissued or given more tools (PRS-SP-22).

Three ways, any one is enough: the user's authenticator app (User 2FA), a 6-digit code emailed to them (the Issue
Token code, press.mcp_server.auth.request_email_otp), or their dashboard password. A confirm then holds for
UNLOCK_SECONDS for this user, as the site logins' does (press.api.site_logins); issuing a token counts as one.
5 wrong tries lock confirming for LOCK_SECONDS.

An app counts only if it was linked before this login: linking one needs no password (press.api.account.enable_2fa),
so an app linked in the same session proves no more than the session, which is what this guards against.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import get_datetime

from press.api.site_logins import _app_code_ok, _mask
from press.mcp_server import auth

UNLOCK_SECONDS = 600
LOCK_SECONDS = 600
MAX_FAILURES = 5
HOW = {"app": "authenticator code", "email": "email code", "password": "password"}


def _key(kind: str) -> str:
	"""The unlock is this browser session's; the wrong-try count and the lock are the user's."""
	if kind == "unlock":
		return f"mcp_confirm:unlock:{frappe.session.user}:{frappe.session.sid}"
	return f"mcp_confirm:{kind}:{frappe.session.user}"


def _app_state(user: str) -> str:
	"""'ready' (linked before this login), 'new' (linked during it) or 'none'."""
	row = frappe.db.get_value("User 2FA", user, ["enabled", "creation"], as_dict=True)
	if not row or not row.enabled:
		return "none"
	login = (frappe.session.data or {}).get("creation")
	if not login or get_datetime(row.creation) >= get_datetime(login):
		return "new"
	return "ready"


def unlocked_seconds() -> int:
	ttl = frappe.cache.ttl(frappe.cache.make_key(_key("unlock")))
	return max(ttl or 0, 0) if frappe.cache.get_value(_key("unlock")) else 0


def mark_confirmed(how: str) -> None:
	"""A successful confirm, or an issue (which re-checks the password or an email code)."""
	if frappe.cache.get_value(_key("lock")):
		return
	frappe.cache.set_value(_key("unlock"), how, expires_in_sec=UNLOCK_SECONDS)
	frappe.cache.delete_value(_key("fail"))


def confirmed_how() -> str:
	"""How the current confirm was made; refuses when there is none."""
	how = frappe.cache.get_value(_key("unlock"))
	if not how:
		frappe.throw(
			"Confirm it's you first (authenticator code, email code or password).", frappe.PermissionError
		)
	return how


def count_failure() -> bool:
	"""One more wrong try; True when it locks confirming."""
	count = (frappe.cache.get_value(_key("fail")) or 0) + 1
	if count >= MAX_FAILURES:
		frappe.cache.set_value(_key("lock"), 1, expires_in_sec=LOCK_SECONDS)
		frappe.cache.delete_value(_key("fail"))
		return True
	frappe.cache.set_value(_key("fail"), count, expires_in_sec=LOCK_SECONDS)
	return False


def _fail(message: str) -> None:
	if count_failure():
		frappe.throw("Too many wrong tries. Try again in 10 minutes.", frappe.ValidationError)
	frappe.throw(message, frappe.ValidationError)


def _check(method: str, code: str, password: str, user: str) -> None:
	if method == "app":
		if _app_state(user) != "ready":
			frappe.throw(
				"Use an email code or your password: no authenticator app was linked before this login."
			)
		if not _app_code_ok(user, code):
			_fail("That code is not right, or was already used. Enter the code the app shows now.")
	elif method == "email":
		try:
			auth._verify_email_otp(user, code)
		except frappe.ValidationError as e:
			_fail(str(e))
	else:
		try:
			auth._check_password(user, password)
		except frappe.ValidationError:
			_fail("That password is not right.")


@frappe.whitelist(methods=["POST"])
def confirm(method: str, code: str = "", password: str = "") -> dict[str, Any]:
	"""Confirm it's you by one of the three ways; opens UNLOCK_SECONDS."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw("Sign in first.", frappe.PermissionError)
	if method not in HOW:
		frappe.throw("Choose authenticator app, email code or password.")
	if frappe.cache.get_value(_key("lock")):
		frappe.throw("Too many wrong tries. Try again in 10 minutes.", frappe.ValidationError)
	_check(method, (code or "").strip(), password or "", user)
	mark_confirmed(HOW[method])
	return {"unlocked_seconds": UNLOCK_SECONDS, "how": HOW[method]}


@frappe.whitelist()
def confirm_status() -> dict[str, Any]:
	"""What the Confirm it's you dialog needs: whether a confirm still holds, and which ways the user has."""
	user = frappe.session.user
	email = frappe.db.get_value("User", user, "email") or ""
	return {
		"unlocked_seconds": unlocked_seconds(),
		"app": _app_state(user),
		"email": _mask(email) if email else "",
		"locked": bool(frappe.cache.get_value(_key("lock"))),
	}
