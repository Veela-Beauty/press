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


class Thrown(Exception):
	def __init__(self, msg, exc=None):
		super().__init__(msg)
		self.exc = exc


def build_stubs(state):  # noqa: C901 - one flat fixture builder
	frappe = types.ModuleType("frappe")
	frappe.PermissionError = type("PermissionError", (Exception,), {})
	frappe.AuthenticationError = type("AuthenticationError", (Exception,), {})
	frappe.session = types.SimpleNamespace(user="member@team.com")

	def throw(msg, exc=None):
		raise Thrown(msg, exc)

	class Cache:
		def get_value(self, k):
			return state["cache"].get(k)

		def set_value(self, k, v, expires_in_sec=None):
			state["cache"][k] = v

		def delete_value(self, k):
			state["cache"].pop(k, None)

		def make_key(self, k):
			return k

		def ttl(self, k):
			return 600 if k in state["cache"] else -2

	frappe.throw = throw
	frappe.cache = Cache()
	frappe.whitelist = lambda *a, **k: lambda fn: fn
	frappe.sendmail = lambda **kw: state["mails"].append(kw)
	frappe.get_doc = lambda doctype, name: state["site"]
	frappe.get_all = lambda *a, **k: state["activity"]
	frappe.db = types.SimpleNamespace(
		get_value=lambda *a, **k: types.SimpleNamespace(
			share_user=state["site"].share_user, is_confidential=state["site"].is_confidential
		),
		set_value=lambda doctype, name, field, value: setattr(state["site"], field, value),
	)
	rate_limiter = types.ModuleType("frappe.rate_limiter")
	rate_limiter.rate_limit = lambda **k: lambda fn: fn
	utils = types.ModuleType("frappe.utils")
	utils.get_fullname = lambda user: user.split("@")[0].title()
	password = types.ModuleType("frappe.utils.password")
	password.set_encrypted_password = lambda doctype, name, pwd, fieldname: state["site"].secrets.__setitem__(
		fieldname, pwd
	)

	account = types.ModuleType("press.api.account")
	account.is_2fa_enabled = lambda user: state["has_app"]
	account.user_permissions = lambda: {"admin": state["admin"]}

	def verify_2fa(user, code):
		if code != "123456":
			raise frappe.AuthenticationError("bad")
		return True

	account.verify_2fa = verify_2fa
	site_api = types.ModuleType("press.api.site")
	site_api.protected = lambda doctypes: lambda fn: fn
	guards = types.ModuleType("press.guards")
	guards.role_guard = types.SimpleNamespace(document=lambda **k: lambda fn: fn)
	activity = types.ModuleType("press.press.doctype.site_activity.site_activity")
	activity.log_site_activity = lambda site, action, reason=None: state["logged"].append((action, reason))
	packages = {}
	for pkg in ("press", "press.api", "press.press", "press.press.doctype", "press.press.doctype.site_activity"):
		packages[pkg] = types.ModuleType(pkg)
		packages[pkg].__path__ = []
	return {
		**packages,
		"frappe": frappe,
		"frappe.rate_limiter": rate_limiter,
		"frappe.utils": utils,
		"frappe.utils.password": password,
		"press.api.account": account,
		"press.api.site": site_api,
		"press.guards": guards,
		"press.press.doctype.site_activity.site_activity": activity,
	}


class FakeConnection:
	def __init__(self, state):
		self.state = state

	def insert(self, doc):
		self.state["inserted"].append(doc)

	def update(self, doc):
		self.state["updated"].append(doc)

	def get_list(self, doctype, fields=None, limit_page_length=None):
		return [{"name": "Basher Trainee"}, {"name": "Sales User"}]


class FakeSite:
	def __init__(self, state, share_user=None, confidential=False):
		self.name = "basher-training.sandbox.mvpstorm.com"
		self.share_user = share_user
		self.is_confidential = confidential
		self.secrets = {"admin_password": "AdminPass1", "share_password": "SharePass1"}
		self.state = state

	def get_password(self, field):
		return self.secrets[field]

	def get_connection_as_admin(self):
		return FakeConnection(self.state)


@unittest.skipIf(REAL_FRAPPE, "real frappe present: these offline tests would replace it")
class SiteLoginsOffline(unittest.TestCase):
	SITE = "basher-training.sandbox.mvpstorm.com"

	def setUp(self):
		self.state = {
			"cache": {},
			"mails": [],
			"logged": [],
			"activity": [],
			"inserted": [],
			"updated": [],
			"has_app": True,
			"admin": False,
		}
		self.state["site"] = FakeSite(self.state, share_user="share-ab12@" + self.SITE)
		self.saved = {k: sys.modules.get(k) for k in build_stubs(self.state)}
		sys.modules.update(build_stubs(self.state))
		spec = importlib.util.spec_from_file_location("site_logins_under_test", MODULE)
		self.m = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(self.m)

	def tearDown(self):
		for k, v in self.saved.items():
			if v is None:
				sys.modules.pop(k, None)
			else:
				sys.modules[k] = v

	def thrown(self, fn, *a):
		with self.assertRaises(Thrown) as ctx:
			fn(*a)
		return ctx.exception

	def test_secret_needs_a_code_first(self):
		self.thrown(self.m.get_secret, self.SITE, "share", "show")
		self.assertEqual(self.state["logged"], [])

	def test_app_code_unlocks_and_every_reveal_is_logged(self):
		self.thrown(self.m.verify_code, self.SITE, "999999", "app")
		self.m.verify_code(self.SITE, "123456", "app")
		got = self.m.get_secret(self.SITE, "share", "message")
		self.assertEqual(got, {"user": "share-ab12@" + self.SITE, "password": "SharePass1"})
		self.assertEqual(self.state["logged"], [("Share Login", "copied the share message (app code)")])

	def test_email_code_works_once(self):
		self.m.send_email_code(self.SITE)
		code = self.state["mails"][0]["message"].split("Your code is ")[1][:6]
		self.m.verify_code(self.SITE, code, "email")
		self.state["cache"].pop(f"site_logins:unlock:member@team.com:{self.SITE}")
		self.thrown(self.m.verify_code, self.SITE, code, "email")

	def test_bad_code_shapes_are_refused(self):
		for code, method in (("12345", "app"), ("abcdef", "app"), ("123456", "sms")):
			self.thrown(self.m.verify_code, self.SITE, code, method)

	def test_app_code_needs_a_linked_app(self):
		self.state["has_app"] = False
		self.assertIn(
			"Link an authenticator app", str(self.thrown(self.m.verify_code, self.SITE, "123456", "app"))
		)

	def test_administrator_login_only_for_team_admins(self):
		self.m.verify_code(self.SITE, "123456", "app")
		err = self.thrown(self.m.get_secret, self.SITE, "admin", "show")
		self.assertIn("team admins", str(err))
		self.state["admin"] = True
		self.assertEqual(self.m.get_secret(self.SITE, "admin", "copy")["password"], "AdminPass1")
		self.assertEqual(
			self.state["logged"][-1], ("Share Login", "copied the Administrator password (app code)")
		)

	def test_confidential_site_never_shows_administrator_password(self):
		self.state["admin"] = True
		self.state["site"].is_confidential = True
		self.m.verify_code(self.SITE, "123456", "app")
		self.assertIn("PIN", str(self.thrown(self.m.get_secret, self.SITE, "admin", "show")))

	def test_share_message_only_for_the_share_login(self):
		self.state["admin"] = True
		self.m.verify_code(self.SITE, "123456", "app")
		self.thrown(self.m.get_secret, self.SITE, "admin", "message")

	def test_create_share_user_admin_only_and_recorded(self):
		self.state["site"].share_user = None
		self.m.verify_code(self.SITE, "123456", "app")
		self.thrown(self.m.create_share_user, self.SITE, "Basher Trainee")
		self.state["admin"] = True
		out = self.m.create_share_user(self.SITE, "Basher Trainee")
		doc = self.state["inserted"][0]
		self.assertEqual(doc["role_profile_name"], "Basher Trainee")
		self.assertEqual(doc["send_welcome_email"], 0)
		self.assertTrue(out["share_user"].startswith("share-"))
		self.assertEqual(len(self.state["site"].secrets["share_password"]), 18)
		self.assertEqual(self.m.role_profile_of([r for _, r in self.state["logged"]]), "Basher Trainee")

	def test_reset_changes_the_password_on_the_site_and_in_press(self):
		self.state["admin"] = True
		self.m.verify_code(self.SITE, "123456", "app")
		self.m.reset_share_password(self.SITE)
		new = self.state["site"].secrets["share_password"]
		self.assertNotEqual(new, "SharePass1")
		self.assertEqual(self.state["updated"][0]["new_password"], new)

	def test_get_logins_hides_nothing_sensitive(self):
		self.state["activity"] = [
			types.SimpleNamespace(
				owner="eslam@team.com", reason="showed the share password (app code)", creation="2026-11-27"
			)
		]
		out = self.m.get_logins(self.SITE)
		self.assertNotIn("password", str(out).lower().replace("showed the share password", ""))
		self.assertEqual(out["history"][0]["who"], "Eslam")
		self.assertFalse(out["admin_visible"])


if __name__ == "__main__":
	unittest.main()
