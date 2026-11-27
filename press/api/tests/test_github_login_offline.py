"""Offline tests for press/api/github_login.py and press/api/oauth_finish.py with a stand-in for frappe and GitHub
(no bench, no network).

Run from the repo root: python3 press/api/tests/test_github_login_offline.py
Inside a bench, where the real frappe is importable, these tests skip themselves so they never replace it.
"""

import importlib.util
import pathlib
import sys
import types
import unittest
from urllib.parse import parse_qs, urlparse

try:
	import frappe  # noqa: F401

	REAL_FRAPPE = True
except ImportError:
	REAL_FRAPPE = False

API = pathlib.Path(__file__).resolve().parents[1]
KEYS = {"client_id": "cid", "client_secret": "csecret"}
COOKIE = "github_login_state"


class Thrown(Exception):
	pass


class Response(dict):
	"""frappe.local.response: read and written both as attributes and as keys."""

	def __getattr__(self, k):
		return self.get(k)

	def __setattr__(self, k, v):
		self[k] = v


class HttpReply:
	def __init__(self, data, status=200):
		self.data, self.status = data, status

	def raise_for_status(self):
		if self.status >= 400:
			raise RuntimeError(f"HTTP {self.status}")

	def json(self):
		return self.data


def build(state):  # noqa: C901 - one flat fixture builder
	f = types.ModuleType("frappe")
	f._ = lambda s: s
	f.conf = {"github_login": state["keys"]} if state["keys"] else {}

	class Cookies:
		def set_cookie(self, key, value, **kw):
			state["browser"][key] = value
			state["cookie_kw"] = kw

		def delete_cookie(self, key):
			state["browser"].pop(key, None)

	f.local = types.SimpleNamespace(
		response=Response(),
		login_manager=types.SimpleNamespace(login_as=lambda user: state["logged_in"].append(user)),
		cookie_manager=Cookies(),
	)
	f.request = types.SimpleNamespace(cookies=state["browser"])

	def throw(msg, exc=None):
		raise Thrown(msg)

	class Cache:
		def get_value(self, k):
			return state["cache"].get(k)

		def set_value(self, k, v, expires_in_sec=None):
			state["cache"][k] = v
			state["ttl"][k] = expires_in_sec

		def delete_value(self, k):
			state["cache"].pop(k, None)

	def db_get_value(doctype, filters, fields=None, as_dict=False):
		if doctype == "Team":
			return state["team"]
		if doctype == "User 2FA":
			return state["has_2fa"]
		if doctype == "Product Trial":
			return types.SimpleNamespace(name=filters) if filters == "erpnext" else None
		return None

	class AccountRequest:
		def __init__(self, **kw):
			self.kw, self.name = kw, "AR-0001"

		def insert(self, ignore_permissions=False):
			state["account_requests"].append(self.kw)

		def get_verification_url(self):
			return "/verify/AR-0001"

	f.throw = throw
	f.cache = Cache
	f.generate_hash = lambda length=10: "s" * length
	f.utils = types.SimpleNamespace(get_url=lambda path: "https://autodeploypanel.mvpstorm.com" + path)
	f.db = types.SimpleNamespace(get_value=db_get_value, commit=lambda: state["commits"].append(1))
	f.respond_as_web_page = lambda title, msg, **kw: state["pages"].append(
		(title, kw.get("http_status_code"))
	)
	f.get_doc = lambda doctype, **kw: AccountRequest(**kw)

	requests = types.ModuleType("requests")

	def post(url, data=None, headers=None, timeout=None):
		state["posted"].append(data)
		return state["token_reply"]

	def get(url, headers=None, timeout=None):
		state["got"].append((url, headers.get("Authorization")))
		return HttpReply(state["emails"]) if "/user/emails" in url else state["user_reply"]

	requests.post, requests.get = post, get

	utils = types.ModuleType("press.utils")
	utils.log_error = lambda title, **kw: state["errors"].append(title)
	telemetry = types.ModuleType("press.utils.telemetry")
	telemetry.capture = lambda *a: state["captured"].append(a)
	press, press_api = types.ModuleType("press"), types.ModuleType("press.api")
	return {
		"frappe": f,
		"requests": requests,
		"press": press,
		"press.api": press_api,
		"press.utils": utils,
		"press.utils.telemetry": telemetry,
	}


def team(user="owner@example.com", enabled=1):
	return types.SimpleNamespace(name="TEAM-1", enabled=enabled, user=user)


def fresh_state(**over):
	state = {
		"keys": dict(KEYS),
		"browser": {},
		"cache": {},
		"ttl": {},
		"team": team(),
		"has_2fa": None,
		"logged_in": [],
		"pages": [],
		"errors": [],
		"commits": [],
		"captured": [],
		"account_requests": [],
		"posted": [],
		"got": [],
		"token_reply": HttpReply({"access_token": "tok"}),
		"emails": [
			{"email": "Old@Example.com", "primary": False, "verified": True},
			{"email": "Owner@Example.com", "primary": True, "verified": True},
		],
		"user_reply": HttpReply({"name": "Owner Person", "login": "owner"}),
	}
	state.update(over)
	return state


@unittest.skipIf(REAL_FRAPPE, "real frappe present: run inside the bench test runner instead")
class GithubLoginOffline(unittest.TestCase):
	def load(self, state):
		stubs = build(state)
		self.saved = {k: sys.modules.get(k) for k in [*stubs, "press.api.oauth_finish"]}
		sys.modules.update(stubs)
		finish_spec = importlib.util.spec_from_file_location(
			"press.api.oauth_finish", API / "oauth_finish.py"
		)
		finish = importlib.util.module_from_spec(finish_spec)
		sys.modules["press.api.oauth_finish"] = finish
		finish_spec.loader.exec_module(finish)
		spec = importlib.util.spec_from_file_location("github_login_under_test", API / "github_login.py")
		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)
		self.addCleanup(self.restore)
		return module, stubs["frappe"]

	def restore(self):
		for k, v in self.saved.items():
			if v is None:
				sys.modules.pop(k, None)
			else:
				sys.modules[k] = v

	def start(self, state, product=None):
		m, f = self.load(state)
		m.login(product)
		s = parse_qs(urlparse(f.local.response["location"]).query)["state"][0]
		f.local.response.clear()
		return m, f, s

	def callback(self, state, product=None, **kw):
		m, f, s = self.start(state, product)
		m.login_callback(state=s, **kw)
		return f

	def test_not_set_up_says_so(self):
		m, _f = self.load(fresh_state(keys=None))
		with self.assertRaises(Thrown):
			m.login()

	def test_login_sends_to_github_with_one_time_state_and_cookie(self):
		state = fresh_state()
		m, f = self.load(state)
		m.login()
		url = urlparse(f.local.response["location"])
		q = parse_qs(url.query)
		self.assertEqual(f"{url.scheme}://{url.netloc}{url.path}", "https://github.com/login/oauth/authorize")
		self.assertEqual(q["client_id"], ["cid"])
		self.assertEqual(
			q["redirect_uri"],
			["https://autodeploypanel.mvpstorm.com/api/method/press.api.github.login_callback"],
		)
		self.assertEqual(q["scope"], ["user:email"])
		s = q["state"][0]
		self.assertEqual(state["ttl"][f"github_login:{s}"], 300)
		self.assertEqual(state["browser"][COOKIE], s)
		self.assertTrue(state["cookie_kw"]["httponly"])
		self.assertEqual(state["cookie_kw"]["samesite"], "Lax")

	def test_unknown_state_shows_expired_page(self):
		state = fresh_state()
		m, _f = self.load(state)
		m.login_callback(code="c", state="not-ours")
		self.assertEqual(state["pages"], [("Sign-in expired", 401)])
		self.assertEqual(state["logged_in"], [])

	def test_link_started_in_another_browser_is_refused(self):
		state = fresh_state()
		m, _f, s = self.start(state)
		state["browser"].clear()  # the victim's browser never had the attacker's cookie
		m.login_callback(code="c", state=s)
		self.assertEqual(state["pages"], [("Sign-in expired", 401)])
		self.assertEqual(state["logged_in"], [])
		self.assertEqual(state["posted"], [])

	def test_state_works_once(self):
		state = fresh_state()
		m, _f, s = self.start(state)
		m.login_callback(code="c", state=s)
		self.assertEqual(state["logged_in"], ["owner@example.com"])
		self.assertNotIn(COOKIE, state["browser"])
		state["browser"][COOKIE] = s  # even with the cookie put back, the state is gone
		m.login_callback(code="c", state=s)
		self.assertEqual(state["pages"], [("Sign-in expired", 401)])
		self.assertEqual(state["logged_in"], ["owner@example.com"])

	def test_cancel_on_github_goes_back_to_login(self):
		state = fresh_state()
		f = self.callback(state, error="access_denied")
		self.assertEqual(f.local.response["location"], "/dashboard/login")
		self.assertEqual(state["posted"], [])

	def test_github_failure_is_logged_and_goes_back_to_login(self):
		state = fresh_state(token_reply=HttpReply({"error": "bad_verification_code"}))
		f = self.callback(state, code="c")
		self.assertEqual(state["errors"], ["GitHub Login failed"])
		self.assertEqual(f.local.response["location"], "/dashboard/login")
		self.assertEqual(state["logged_in"], [])

	def test_no_verified_primary_email_is_refused(self):
		state = fresh_state(emails=[{"email": "a@b.com", "primary": True, "verified": False}])
		self.callback(state, code="c")
		self.assertEqual(state["pages"], [("No verified e-mail on GitHub", None)])
		self.assertEqual(state["logged_in"], [])

	def test_existing_account_signs_in_under_its_stored_name(self):
		state = fresh_state(team=team(user="Owner@Example.com"))
		f = self.callback(state, code="c")
		self.assertEqual(state["logged_in"], ["Owner@Example.com"])
		self.assertEqual(f.local.response["location"], "/dashboard")
		self.assertEqual(state["got"][0], ("https://api.github.com/user/emails?per_page=100", "Bearer tok"))
		self.assertEqual(state["posted"][0]["client_secret"], "csecret")

	def test_profile_name_failure_does_not_block_sign_up(self):
		state = fresh_state(team=None, user_reply=HttpReply({}, status=502))
		f = self.callback(state, code="c")
		self.assertEqual(state["account_requests"][0]["first_name"], "owner")
		self.assertEqual(f.local.response["location"], "/verify/AR-0001")

	def test_deactivated_account_is_refused(self):
		state = fresh_state(team=team(enabled=0))
		m, _f, s = self.start(state)
		with self.assertRaises(Thrown):
			m.login_callback(code="c", state=s)
		self.assertEqual(state["logged_in"], [])

	def test_account_with_2fa_goes_to_email_login(self):
		state = fresh_state(has_2fa="2FA-1")
		self.callback(state, code="c")
		self.assertEqual(state["pages"], [("Two-Factor Authentication Required", None)])
		self.assertEqual(state["logged_in"], [])

	def test_2fa_also_holds_on_the_product_sign_up_path(self):
		state = fresh_state(has_2fa="2FA-1")
		self.callback(state, product="erpnext", code="c")
		self.assertEqual(state["pages"], [("Two-Factor Authentication Required", None)])
		self.assertEqual(state["logged_in"], [])
		self.assertEqual(state["account_requests"], [])

	def test_existing_account_on_product_path_goes_to_site_setup(self):
		state = fresh_state()
		f = self.callback(state, product="erpnext", code="c")
		self.assertEqual(state["logged_in"], ["owner@example.com"])
		self.assertEqual(f.local.response["location"], "/dashboard/create-site/erpnext/setup")

	def test_new_email_becomes_an_account_request(self):
		state = fresh_state(team=None)
		f = self.callback(state, code="c")
		self.assertEqual(state["logged_in"], [])
		self.assertEqual(state["account_requests"][0]["email"], "owner@example.com")
		self.assertEqual(state["account_requests"][0]["first_name"], "Owner")
		self.assertTrue(state["account_requests"][0]["oauth_signup"])
		self.assertEqual(f.local.response["location"], "/verify/AR-0001")


if __name__ == "__main__":
	unittest.main(verbosity=2)
