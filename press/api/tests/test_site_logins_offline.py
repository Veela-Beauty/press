"""Offline tests for press/api/site_logins.py with a stand-in for frappe (no bench, no network).

Run from the repo root: python3 press/api/tests/test_site_logins_offline.py
Inside a bench, where the real frappe is importable, these tests skip themselves so they never replace it.
"""

import importlib.util
import pathlib
import sys
import types
import unittest

try:
	import frappe  # noqa: F401

	REAL_FRAPPE = True
except ImportError:
	REAL_FRAPPE = False

MODULE = pathlib.Path(__file__).resolve().parents[1] / "site_logins.py"
SITE = "basher-training.sandbox.mvpstorm.com"
GOOD_APP_CODE = "123456"


class Thrown(Exception):
	def __init__(self, msg, exc=None):
		super().__init__(msg)
		self.exc = exc


def frappe_stub(state):  # noqa: C901 - one flat fixture builder
	f = types.ModuleType("frappe")
	for name in ("PermissionError", "AuthenticationError", "DoesNotExistError"):
		setattr(f, name, type(name, (Exception,), {}))
	f.ValidationError = Thrown  # like frappe.throw: what it raises is a ValidationError
	f.session = types.SimpleNamespace(user="member@team.com")

	def throw(msg, exc=None):
		raise Thrown(msg, exc)

	class Cache:
		def get_value(self, k):
			return None if state["redis_down"] else state["cache"].get(k)

		def set_value(self, k, v, expires_in_sec=None):
			if not state["redis_down"]:
				state["cache"][k] = v

		def delete_value(self, k):
			state["cache"].pop(k, None)

		def make_key(self, k):
			return k

		def ttl(self, k):
			return 600 if k in state["cache"] else -2

	def whitelist(methods=None, **_):
		def deco(fn):
			state["methods"][fn.__name__] = methods
			return fn

		return deco

	def db_get_value(doctype, name, field, as_dict=False, for_update=False):
		site = state["site"]
		if doctype == "User 2FA":
			return state["has_app"]
		if field == "team":
			return site.team if name == SITE else None
		if field == "share_user":
			return site.share_user
		return types.SimpleNamespace(share_user=site.share_user, is_confidential=site.is_confidential)

	def get_all(doctype, filters=None, fields=None, pluck=None, order_by=None, limit=None):
		rows = state["activity"]
		if pluck:
			like = filters.get("reason", [None, ""])[1].rstrip("%")
			return [r.reason for r in rows if r.reason.startswith(like)][:limit]
		return rows[:limit]

	def db_set_value(doctype, name, field, value):
		if doctype == "Site":
			setattr(state["site"], field, value)

	f.throw = throw
	f.cache = Cache()
	f.whitelist = whitelist
	f.sendmail = lambda **kw: state["mails"].append(kw)
	f.get_doc = lambda doctype, name: state["site"]
	f.get_all = get_all
	f.log_error = lambda *a, **k: state["errors"].append(a)
	f.db = types.SimpleNamespace(
		get_value=db_get_value, set_value=db_set_value, commit=lambda: state["commits"].append(1)
	)
	return f


def modules(state):  # noqa: C901 - one flat fixture builder
	f = frappe_stub(state)
	utils = types.ModuleType("frappe.utils")
	utils.get_fullname = lambda user: user.split("@")[0].title()
	utils.now = lambda: "2026-11-27 12:00:00"
	utils.cint = lambda v: int(v or 0)
	f.utils = utils
	password = types.ModuleType("frappe.utils.password")
	password.get_decrypted_password = lambda *a, **k: "SECRET"
	password.get_encryption_key = lambda: "enc-key"
	password.set_encrypted_password = lambda dt, name, pwd, fieldname: state["site"].secrets.__setitem__(
		fieldname, pwd
	)

	class FrappeClient:
		def __init__(self, url, username, password):
			self.session = types.SimpleNamespace(request=lambda *a, **k: None)  # as the real one: session, then login
			if state["site_down"]:
				raise ConnectionError("down")
			self._login(username, password)

		def _login(self, username, password):
			state["timeout_set"] = "timeout" in str(self.session.request)

		def get_list(self, doctype, fields=None, limit_page_length=None):
			return [{"name": n} for n in state["profiles"]]

		def get_doc(self, doctype, name):
			return {"roles": [{"role": r} for r in state["profiles"][name]]}

		def insert(self, doc):
			state["inserted"].append(doc)

		def update(self, doc):
			state["updated"].append(doc)

	client = types.ModuleType("frappe.frappeclient")
	client.FrappeClient = FrappeClient
	pyotp = types.ModuleType("pyotp")
	pyotp.TOTP = lambda secret: types.SimpleNamespace(verify=lambda code: code == GOOD_APP_CODE)
	account = types.ModuleType("press.api.account")
	account.user_permissions = lambda: {"admin": state["admin"]}
	site_api = types.ModuleType("press.api.site")
	site_api.protected = lambda doctypes: lambda fn: fn
	guards = types.ModuleType("press.guards")
	guards.role_guard = types.SimpleNamespace(document=lambda **k: lambda fn: fn)
	activity = types.ModuleType("press.press.doctype.site_activity.site_activity")
	activity.log_site_activity = lambda site, action, reason=None: state["logged"].append((action, reason))
	press_utils = types.ModuleType("press.utils")
	press_utils.__path__ = []
	press_utils.get_current_team = lambda: state["team"]
	press_user = types.ModuleType("press.utils.user")
	press_user.is_system_manager = lambda: state["system_manager"]
	packages = {}
	for pkg in (
		"press",
		"press.api",
		"press.press",
		"press.press.doctype",
		"press.press.doctype.site_activity",
	):
		packages[pkg] = types.ModuleType(pkg)
		packages[pkg].__path__ = []
	return {
		**packages,
		"frappe": f,
		"frappe.utils": utils,
		"frappe.utils.password": password,
		"frappe.frappeclient": client,
		"pyotp": pyotp,
		"press.api.account": account,
		"press.api.site": site_api,
		"press.guards": guards,
		"press.press.doctype.site_activity.site_activity": activity,
		"press.utils": press_utils,
		"press.utils.user": press_user,
	}


class FakeSite:
	def __init__(self, share_user=None, confidential=False):
		self.name = SITE
		self.team = "team-a"
		self.share_user = share_user
		self.is_confidential = confidential
		self.secrets = {"admin_password": "AdminPass1", "share_password": "SharePass1"}

	def get_password(self, field):
		return self.secrets[field]


@unittest.skipIf(REAL_FRAPPE, "real frappe present: these offline tests would replace it")
class SiteLoginsOffline(unittest.TestCase):
	def setUp(self):
		self.state = {
			"cache": {},
			"mails": [],
			"logged": [],
			"activity": [],
			"inserted": [],
			"updated": [],
			"errors": [],
			"commits": [],
			"methods": {},
			"has_app": True,
			"admin": False,
			"team": "team-a",
			"system_manager": False,
			"redis_down": False,
			"site_down": False,
			"profiles": {"Basher Trainee": ["Employee"], "Full Access": ["System Manager"]},
		}
		self.state["site"] = FakeSite(share_user="share-ab12@" + SITE)
		stubs = modules(self.state)
		self.saved = {k: sys.modules.get(k) for k in stubs}
		sys.modules.update(stubs)
		spec = importlib.util.spec_from_file_location("site_logins_under_test", MODULE)
		self.m = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(self.m)

	def tearDown(self):
		for k, v in self.saved.items():
			if v is None:
				sys.modules.pop(k, None)
			else:
				sys.modules[k] = v

	def thrown(self, fn, *a, **k):
		with self.assertRaises(Thrown) as ctx:
			fn(*a, **k)
		return ctx.exception

	def unlock(self):
		self.m.verify_code(SITE, GOOD_APP_CODE, "app")
		self.state["cache"].pop("site_logins:last_app_code:member@team.com", None)

	def test_every_endpoint_is_post_only(self):
		names = (
			"get_logins",
			"send_email_code",
			"verify_code",
			"get_secret",
			"role_profiles",
			"create_share_user",
			"reset_share_password",
		)
		for name in names:
			self.assertEqual(self.state["methods"][name], ["POST"], name)

	def test_other_team_is_refused_even_for_a_system_user(self):
		self.state["team"] = "team-b"
		self.thrown(self.m.get_logins, SITE)
		self.state["system_manager"] = True
		self.assertIn("share_user", self.m.get_logins(SITE))

	def test_unknown_site_is_refused(self):
		self.thrown(self.m.get_logins, "nope.example.com")

	def test_secret_needs_a_code_first(self):
		self.thrown(self.m.get_secret, SITE, "share", "show")
		self.assertEqual(self.state["logged"], [])

	def test_app_code_unlocks_and_every_reveal_is_logged(self):
		self.thrown(self.m.verify_code, SITE, "999999", "app")
		self.unlock()
		got = self.m.get_secret(SITE, "share", "message")
		self.assertEqual(got, {"user": "share-ab12@" + SITE, "password": "SharePass1"})
		self.assertEqual(self.state["logged"], [("Share Login", "copied the share message (app code)")])

	def test_app_code_works_once(self):
		self.m.verify_code(SITE, GOOD_APP_CODE, "app")
		self.thrown(self.m.verify_code, SITE, GOOD_APP_CODE, "app")

	def test_five_wrong_codes_lock_the_user_out(self):
		for _ in range(4):
			self.thrown(self.m.verify_code, SITE, "999999", "app")
		self.assertIn("Too many wrong codes", str(self.thrown(self.m.verify_code, SITE, "999999", "app")))
		self.assertIn("locked out", self.state["logged"][-1][1])
		self.assertTrue(self.state["commits"])
		self.thrown(self.m.verify_code, SITE, GOOD_APP_CODE, "app")  # locked even with the right code

	def test_email_code_works_once_and_sends_are_limited(self):
		self.m.send_email_code(SITE)
		code = self.state["mails"][0]["message"].split("Your code is ")[1][:6]
		self.m.verify_code(SITE, code, "email")
		self.thrown(self.m.verify_code, SITE, code, "email")
		for _ in range(4):
			self.m.send_email_code(SITE)
		self.assertIn("Too many codes sent", str(self.thrown(self.m.send_email_code, SITE)))

	def test_bad_code_shapes_are_refused(self):
		for code, method in (("12345", "app"), ("abcdef", "app"), (GOOD_APP_CODE, "sms")):
			self.thrown(self.m.verify_code, SITE, code, method)

	def test_app_code_needs_a_linked_app(self):
		self.state["has_app"] = False
		self.assertIn(
			"Link an authenticator app", str(self.thrown(self.m.verify_code, SITE, GOOD_APP_CODE, "app"))
		)

	def test_linking_in_the_dialog_is_recorded(self):
		self.m.verify_code(SITE, GOOD_APP_CODE, "app", linked=1)
		self.assertIn("linked an authenticator app", self.state["logged"][-1][1])

	def test_redis_down_fails_closed_with_a_clear_message(self):
		self.state["redis_down"] = True
		self.assertIn("busy", str(self.thrown(self.m.verify_code, SITE, GOOD_APP_CODE, "app")))

	def test_administrator_login_only_for_team_admins(self):
		self.unlock()
		self.assertIn("team admins", str(self.thrown(self.m.get_secret, SITE, "admin", "show")))
		self.state["admin"] = True
		self.assertEqual(self.m.get_secret(SITE, "admin", "copy")["password"], "AdminPass1")
		self.assertEqual(
			self.state["logged"][-1], ("Share Login", "copied the Administrator password (app code)")
		)

	def test_confidential_site_never_shows_administrator_password_nor_gets_a_share_user(self):
		self.state["admin"] = True
		self.state["site"].is_confidential = True
		self.state["site"].share_user = None
		self.unlock()
		self.assertIn("PIN", str(self.thrown(self.m.get_secret, SITE, "admin", "show")))
		self.thrown(self.m.create_share_user, SITE, "Basher Trainee")
		self.assertEqual(self.state["inserted"], [])

	def test_share_message_only_for_the_share_login(self):
		self.state["admin"] = True
		self.unlock()
		self.thrown(self.m.get_secret, SITE, "admin", "message")

	def test_role_profiles_hide_system_manager_ones(self):
		self.state["admin"] = True
		self.unlock()
		self.assertEqual(self.m.role_profiles(SITE), ["Basher Trainee"])

	def test_create_share_user_checks_the_profile_and_is_recorded(self):
		self.state["site"].share_user = None
		self.unlock()
		self.thrown(self.m.create_share_user, SITE, "Basher Trainee")  # not an admin
		self.state["admin"] = True
		self.assertIn("System Manager", str(self.thrown(self.m.create_share_user, SITE, "Full Access")))
		out = self.m.create_share_user(SITE, "Basher Trainee")
		doc = self.state["inserted"][0]
		self.assertEqual((doc["role_profile_name"], doc["send_welcome_email"]), ("Basher Trainee", 0))
		self.assertTrue(out["share_user"].startswith("share-"))
		self.assertEqual(len(self.state["site"].secrets["share_password"]), 18)
		self.assertTrue(self.state["commits"])
		self.assertEqual(self.m.role_profile_of([r for _, r in self.state["logged"]]), "Basher Trainee")

	def test_a_down_site_gives_a_clear_message(self):
		self.state["admin"] = True
		self.unlock()
		self.state["site_down"] = True
		self.assertIn("did not answer", str(self.thrown(self.m.reset_share_password, SITE)))
		self.assertEqual(self.state["site"].secrets["share_password"], "SharePass1")

	def test_reset_changes_the_password_on_the_site_and_in_press(self):
		self.state["admin"] = True
		self.unlock()
		self.m.reset_share_password(SITE)
		new = self.state["site"].secrets["share_password"]
		self.assertNotEqual(new, "SharePass1")
		self.assertEqual(self.state["updated"][0]["new_password"], new)
		self.assertTrue(self.state["timeout_set"])  # the login itself runs with the timeout

	def test_get_logins_returns_no_secret(self):
		self.state["activity"] = [
			types.SimpleNamespace(
				owner="eslam@team.com", reason="showed the share password (app code)", creation="2026-11-27"
			)
		]
		out = self.m.get_logins(SITE)
		self.assertNotIn("SharePass1", str(out))
		self.assertNotIn("AdminPass1", str(out))
		self.assertEqual(out["history"][0]["who"], "Eslam")
		self.assertFalse(out["admin_visible"])


if __name__ == "__main__":
	unittest.main()
