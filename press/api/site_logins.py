"""Site logins and sharing (PRS-SP-17).

The share login of a site (for people outside the team) and its Administrator login, shown only after a 6-digit code
(the user's authenticator app, or a code emailed to them), then without a code for UNLOCK_SECONDS. Every action is
recorded in Site Activity as "Share Login": who (the activity's owner), what and how they verified.

Access: the team owns the site (protected) and the user's Press role covers it (role_guard). The Administrator login
and creating or resetting the share user need a team admin (account.user_permissions()["admin"]); a confidential site
never shows its Administrator password (its PIN login stays).
"""

import hashlib
import hmac
import re
import secrets
import string

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import get_fullname
from frappe.utils.password import set_encrypted_password

from press.api.account import is_2fa_enabled, user_permissions, verify_2fa
from press.api.site import protected
from press.guards import role_guard
from press.press.doctype.site_activity.site_activity import log_site_activity

ACTION = "Share Login"
UNLOCK_SECONDS = 600
CODE_SECONDS = 600
HOW = {"app": "app code", "email": "email code"}
LABELS = {"share": "share password", "admin": "Administrator password"}
CREATED = "created the share user, role profile "


def _site_access(fn):
	"""Team owns the site and the user's Press role covers it."""
	guarded = role_guard.document(document_type=lambda _: "Site", document_name=lambda a: str(a.get("name")))(
		fn
	)
	return frappe.whitelist()(protected("Site")(guarded))


def _unlock_key(site):
	return f"site_logins:unlock:{frappe.session.user}:{site}"


def _email_code_key():
	return f"site_logins:email_code:{frappe.session.user}"


def _require_unlocked(site):
	how = frappe.cache.get_value(_unlock_key(site))
	if not how:
		frappe.throw("Enter your 6-digit code first", frappe.PermissionError)
	return how


def _require_admin():
	if not user_permissions().get("admin"):
		frappe.throw("Only team admins can do this", frappe.PermissionError)


def _new_password(length=18):
	alphabet = string.ascii_letters + string.digits
	while True:
		password = "".join(secrets.choice(alphabet) for _ in range(length))
		if (
			any(c.islower() for c in password)
			and any(c.isupper() for c in password)
			and any(c.isdigit() for c in password)
		):
			return password


def _hash(code):
	return hashlib.sha256(code.encode()).hexdigest()


def _mask(email):
	local, _, domain = email.partition("@")
	return f"{local[:1]}***@{domain}"


def role_profile_of(reasons):
	"""The role profile named in the newest 'created the share user' activity, or None."""
	for reason in reasons:
		if reason and reason.startswith(CREATED):
			return reason[len(CREATED) :].rsplit(" (", 1)[0]
	return None


@_site_access
def get_logins(name):
	site = frappe.db.get_value("Site", name, ["share_user", "is_confidential"], as_dict=True)
	activity = frappe.get_all(
		"Site Activity",
		filters={"site": name, "action": ACTION},
		fields=["owner", "reason", "creation"],
		order_by="creation desc",
		limit=50,
	)
	ttl = frappe.cache.ttl(frappe.cache.make_key(_unlock_key(name)))
	return {
		"share_user": site.share_user,
		"role_profile": role_profile_of([a.reason for a in activity]),
		"admin_visible": bool(user_permissions().get("admin")),
		"confidential": bool(site.is_confidential),
		"has_app": is_2fa_enabled(frappe.session.user),
		"unlocked_seconds": max(ttl or 0, 0),
		"history": [
			{"who": get_fullname(a.owner), "what": a.reason, "when": a.creation} for a in activity[:5]
		],
	}


@_site_access
@rate_limit(limit=5, seconds=60 * 10)
def send_email_code(name):
	code = f"{secrets.randbelow(10**6):06d}"
	frappe.cache.set_value(_email_code_key(), _hash(code), expires_in_sec=CODE_SECONDS)
	frappe.sendmail(
		recipients=[frappe.session.user],
		subject="Your Press code",
		message=f"Your code is {code}. It works for 10 minutes. You asked for it to see or share a site login on {name}.",
		now=True,
	)
	return {"sent_to": _mask(frappe.session.user)}


@_site_access
@rate_limit(limit=10, seconds=60 * 10)
def verify_code(name, code, method):
	code = str(code or "").strip()
	if not re.fullmatch(r"\d{6}", code) or method not in HOW:
		frappe.throw("Enter the 6-digit code")
	if method == "app":
		if not is_2fa_enabled(frappe.session.user):
			frappe.throw("Link an authenticator app first")
		try:
			verify_2fa(frappe.session.user, code)
		except frappe.AuthenticationError:
			frappe.throw("Wrong code. Try the newest code in your app.")
	else:
		stored = frappe.cache.get_value(_email_code_key())
		if not stored or not hmac.compare_digest(stored, _hash(code)):
			frappe.throw("Wrong or expired code. Ask for a new one.")
		frappe.cache.delete_value(_email_code_key())
	frappe.cache.set_value(_unlock_key(name), HOW[method], expires_in_sec=UNLOCK_SECONDS)
	return {"unlocked_seconds": UNLOCK_SECONDS}


@_site_access
def get_secret(name, which, purpose):
	"""which: share or admin; purpose: show, copy, or message (the share message, share login only)."""
	how = _require_unlocked(name)
	if (
		which not in LABELS
		or purpose not in ("show", "copy", "message")
		or (purpose == "message" and which != "share")
	):
		frappe.throw("Unknown request")
	site = frappe.get_doc("Site", name)
	if which == "admin":
		_require_admin()
		if site.is_confidential:
			frappe.throw(
				"Confidential site: use Login as Administrator with your PIN", frappe.PermissionError
			)
		user, password = "Administrator", site.get_password("admin_password")
	else:
		if not site.share_user:
			frappe.throw("No share user yet")
		user, password = site.share_user, site.get_password("share_password")
	what = (
		"copied the share message"
		if purpose == "message"
		else f"{'showed' if purpose == 'show' else 'copied'} the {LABELS[which]}"
	)
	log_site_activity(name, ACTION, reason=f"{what} ({how})")
	return {"user": user, "password": password}


@_site_access
def role_profiles(name):
	_require_unlocked(name)
	_require_admin()
	connection = frappe.get_doc("Site", name).get_connection_as_admin()
	return [r["name"] for r in connection.get_list("Role Profile", fields=["name"], limit_page_length=200)]


@_site_access
def create_share_user(name, role_profile):
	how = _require_unlocked(name)
	_require_admin()
	site = frappe.get_doc("Site", name)
	if site.share_user:
		frappe.throw("This site already has a share user")
	email, password = f"share-{secrets.token_hex(3)}@{site.name}", _new_password()
	site.get_connection_as_admin().insert(
		{
			"doctype": "User",
			"email": email,
			"first_name": "Share",
			"last_name": "Login",
			"user_type": "System User",
			"send_welcome_email": 0,
			"role_profile_name": role_profile,
			"new_password": password,
		}
	)
	frappe.db.set_value("Site", name, "share_user", email)
	set_encrypted_password("Site", name, password, "share_password")
	log_site_activity(name, ACTION, reason=f"{CREATED}{role_profile} ({how})")
	return {"share_user": email}


@_site_access
def reset_share_password(name):
	how = _require_unlocked(name)
	_require_admin()
	site = frappe.get_doc("Site", name)
	if not site.share_user:
		frappe.throw("No share user yet")
	password = _new_password()
	site.get_connection_as_admin().update(
		{"doctype": "User", "name": site.share_user, "new_password": password}
	)
	set_encrypted_password("Site", name, password, "share_password")
	log_site_activity(name, ACTION, reason=f"reset the share password ({how})")
	return {"ok": True}
