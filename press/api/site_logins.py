"""Site logins and sharing (PRS-SP-17).

The share login of a site (for people outside the team) and its Administrator login, shown only after a 6-digit code
(the user's authenticator app, or a code emailed to them), then without a code for UNLOCK_SECONDS. Every action is
recorded in Site Activity as "Share Login": who (the activity's owner), what and how they verified.

Access, checked on every endpoint (POST only, so the activity row is never rolled back by a GET):
- the site's team is the user's current team (System Users included; only a System Manager passes for any site);
- the team owns the site (protected) and the user's Press role covers it (role_guard);
- the Administrator login, creating and resetting the share user need a team admin (account.user_permissions);
- a confidential site never shows its Administrator password and gets no share user (its PIN login stays).

Codes: an app code is checked against User 2FA directly (not account.verify_2fa: its rate limit shares the outer
endpoint's key) and cannot be used twice; 5 wrong codes lock the user out of codes for LOCK_SECONDS.
A user without an app may link one inside the dialog: that proves no more than the session, which can already use
Login as Administrator on a non-confidential site, so it opens nothing new; it is recorded.
"""

import functools
import hashlib
import hmac
import re
import secrets
import string

import frappe
import pyotp
from frappe.frappeclient import FrappeClient
from frappe.utils import get_fullname
from frappe.utils.password import get_decrypted_password, get_encryption_key, set_encrypted_password

from press.api.account import user_permissions
from press.api.site import protected
from press.guards import role_guard
from press.press.doctype.site_activity.site_activity import log_site_activity
from press.utils import get_current_team
from press.utils.user import is_system_manager

ACTION = "Share Login"
UNLOCK_SECONDS = 600
CODE_SECONDS = 600
LOCK_SECONDS = 600
MAX_FAILURES = 5
MAX_EMAILS = 5
REMOTE_TIMEOUT = 30
HOW = {"app": "app code", "email": "email code"}
LABELS = {"share": "share password", "admin": "Administrator password"}
CREATED = "created the share user, role profile "
POWERFUL_ROLES = {"System Manager", "Administrator"}


def _same_team(fn):
	@functools.wraps(fn)
	def inner(*args, **kwargs):
		name = kwargs.get("name") or (args[0] if args else None)
		team = frappe.db.get_value("Site", name, "team") if name else None
		if not team:
			frappe.throw("Site not found", frappe.DoesNotExistError)
		if team != get_current_team() and not is_system_manager():
			frappe.throw("Not permitted", frappe.PermissionError)
		return fn(*args, **kwargs)

	return inner


def _site_access(fn):
	guarded = role_guard.document(document_type=lambda _: "Site", document_name=lambda a: str(a.get("name")))(
		_same_team(fn)
	)
	return frappe.whitelist(methods=["POST"])(protected("Site")(guarded))


def _key(kind, site=None):
	return f"site_logins:{kind}:{frappe.session.user}" + (f":{site}" if site else "")


def _require_unlocked(site):
	how = frappe.cache.get_value(_key("unlock", site))
	if not how:
		frappe.throw("Enter your 6-digit code first", frappe.PermissionError)
	return how


def _require_admin():
	if not user_permissions().get("admin"):
		frappe.throw("Only team admins can do this", frappe.PermissionError)


def _require_not_locked():
	if frappe.cache.get_value(_key("lock")):
		frappe.throw("Too many wrong codes. Try again in 10 minutes.", frappe.PermissionError)


def _failed(site, message):
	count = (frappe.cache.get_value(_key("fail")) or 0) + 1
	if count >= MAX_FAILURES:
		frappe.cache.set_value(_key("lock"), 1, expires_in_sec=LOCK_SECONDS)
		frappe.cache.delete_value(_key("fail"))
		frappe.cache.delete_value(_key("email_code"))
		log_site_activity(
			site, ACTION, reason=f"locked out of codes for 10 minutes after {MAX_FAILURES} wrong codes"
		)
		frappe.db.commit()  # the throw below rolls the request back; the lock-out stays recorded
		frappe.throw("Too many wrong codes. Try again in 10 minutes.", frappe.PermissionError)
	frappe.cache.set_value(_key("fail"), count, expires_in_sec=LOCK_SECONDS)
	frappe.throw(message)


def _set(key, value, seconds):
	frappe.cache.set_value(key, value, expires_in_sec=seconds)
	if frappe.cache.get_value(key) is None:
		frappe.throw("The service is busy. Try again in a minute.")


def _hash(code):
	return hmac.new(get_encryption_key().encode(), code.encode(), hashlib.sha256).hexdigest()


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


def _mask(email):
	local, _, domain = email.partition("@")
	return f"{local[:1]}***@{domain}"


def _has_app(user):
	return bool(frappe.db.get_value("User 2FA", user, "enabled"))


def _app_code_ok(user, code):
	if frappe.cache.get_value(_key("last_app_code")) == code:
		return False  # an app code works once
	secret = get_decrypted_password("User 2FA", user, "totp_secret", raise_exception=False)
	if not secret or not pyotp.TOTP(secret).verify(code):
		return False
	frappe.cache.set_value(_key("last_app_code"), code, expires_in_sec=90)
	frappe.db.set_value("User 2FA", user, "last_verified_at", frappe.utils.now())
	return True


class _Client(FrappeClient):
	"""FrappeClient with a timeout on every request, the login included."""

	def _login(self, username, password):
		self.session.request = functools.partial(self.session.request, timeout=REMOTE_TIMEOUT)
		return super()._login(username, password)


def _remote(site, call):
	try:
		return call(_Client(f"https://{site.name}", "Administrator", site.get_password("admin_password")))
	except frappe.ValidationError:
		raise  # our own checks (frappe.throw) keep their message
	except Exception:
		frappe.log_error(f"Site logins: {site.name} did not answer")
		frappe.throw("The site did not answer. Try again.")


def role_profile_of(reasons):
	"""The role profile named in the newest 'created the share user' activity, or None."""
	for reason in reasons:
		if reason and reason.startswith(CREATED):
			return reason[len(CREATED) :].rsplit(" (", 1)[0]
	return None


@_site_access
def get_logins(name):
	site = frappe.db.get_value("Site", name, ["share_user", "is_confidential"], as_dict=True)
	created = frappe.get_all(
		"Site Activity",
		filters={"site": name, "action": ACTION, "reason": ["like", f"{CREATED}%"]},
		pluck="reason",
		order_by="creation desc",
		limit=1,
	)
	history = frappe.get_all(
		"Site Activity",
		filters={"site": name, "action": ACTION},
		fields=["owner", "reason", "creation"],
		order_by="creation desc",
		limit=5,
	)
	ttl = frappe.cache.ttl(frappe.cache.make_key(_key("unlock", name)))
	return {
		"share_user": site.share_user,
		"role_profile": role_profile_of(created),
		"admin_visible": bool(user_permissions().get("admin")),
		"confidential": bool(site.is_confidential),
		"has_app": _has_app(frappe.session.user),
		"unlocked_seconds": max(ttl or 0, 0),
		"history": [{"who": get_fullname(h.owner), "what": h.reason, "when": h.creation} for h in history],
	}


@_site_access
def send_email_code(name):
	_require_not_locked()
	sent = frappe.cache.get_value(_key("emails")) or 0
	if sent >= MAX_EMAILS:
		frappe.throw("Too many codes sent. Try again in 10 minutes.")
	code = f"{secrets.randbelow(10**6):06d}"
	_set(_key("email_code"), _hash(code), CODE_SECONDS)
	frappe.cache.set_value(_key("emails"), sent + 1, expires_in_sec=CODE_SECONDS)
	try:
		frappe.sendmail(
			recipients=[frappe.session.user],
			subject="Your Press code",
			message=f"Your code is {code}. It works for 10 minutes. You asked for it to see or share a login on {name}.",
			now=True,
		)
	except Exception:
		frappe.log_error("Site logins: the code email was not sent")
		frappe.throw("The email could not be sent. Use your authenticator app.")
	return {"sent_to": _mask(frappe.session.user)}


@_site_access
def verify_code(name, code, method, linked=False):
	_require_not_locked()
	code = str(code or "").strip()
	if not re.fullmatch(r"\d{6}", code) or method not in HOW:
		frappe.throw("Enter the 6-digit code")
	user = frappe.session.user
	if method == "app":
		if not _has_app(user):
			frappe.throw("Link an authenticator app first")
		if not _app_code_ok(user, code):
			_failed(name, "Wrong code. Wait for the next code in your app.")
	else:
		stored = frappe.cache.get_value(_key("email_code"))
		if not stored or not hmac.compare_digest(stored, _hash(code)):
			_failed(name, "Wrong or expired code. Ask for a new one.")
		frappe.cache.delete_value(_key("email_code"))
	frappe.cache.delete_value(_key("fail"))
	_set(_key("unlock", name), HOW[method], UNLOCK_SECONDS)
	if frappe.utils.cint(linked):
		log_site_activity(name, ACTION, reason="linked an authenticator app in the code dialog (app code)")
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
	verb = "showed" if purpose == "show" else "copied"
	what = "copied the share message" if purpose == "message" else f"{verb} the {LABELS[which]}"
	log_site_activity(name, ACTION, reason=f"{what} ({how})")
	return {"user": user, "password": password}


def _safe_profiles(client):
	names = [r["name"] for r in client.get_list("Role Profile", fields=["name"], limit_page_length=50)]
	safe = []
	for profile in names:
		roles = {r.get("role") for r in client.get_doc("Role Profile", profile).get("roles", [])}
		if not roles & POWERFUL_ROLES:
			safe.append(profile)
	return safe


@_site_access
def role_profiles(name):
	_require_unlocked(name)
	_require_admin()
	return _remote(frappe.get_doc("Site", name), _safe_profiles)


@_site_access
def create_share_user(name, role_profile):
	how = _require_unlocked(name)
	_require_admin()
	site = frappe.get_doc("Site", name)
	if site.is_confidential:
		frappe.throw("A confidential site gets no share user", frappe.PermissionError)
	if frappe.db.get_value("Site", name, "share_user", for_update=True):
		frappe.throw("This site already has a share user")
	email, password = f"share-{secrets.token_hex(3)}@{site.name}", _new_password()

	def create(client):
		if role_profile not in _safe_profiles(client):
			frappe.throw("Pick a role profile from the list (profiles with System Manager are not allowed)")
		client.insert(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Share",
				"last_name": "Login",
				"user_type": "System User",
				"send_welcome_email": 0,
				"role_profile_name": role_profile,
				"role_profiles": [{"role_profile": role_profile}],
				"new_password": password,
			}
		)

	_remote(site, create)
	frappe.db.set_value("Site", name, "share_user", email)
	set_encrypted_password("Site", name, password, "share_password")
	frappe.db.commit()  # the user exists on the site now: never lose its password to a later error
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
	_remote(site, lambda c: c.update({"doctype": "User", "name": site.share_user, "new_password": password}))
	set_encrypted_password("Site", name, password, "share_password")
	frappe.db.commit()  # the password changed on the site: keep it in Press whatever happens next
	log_site_activity(name, ACTION, reason=f"reset the share password ({how})")
	return {"ok": True}
