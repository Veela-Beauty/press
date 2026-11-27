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
	f.local = types.SimpleNamespace(
		response=Response(),
		login_manager=types.SimpleNamespace(login_as=lambda email: state["logged_in"].append(email)),
	)

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
			return None
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
	f.respond_as_web_page = lambda title, msg, **kw: state["pages"].append(title)
	f.get_doc = lambda doctype, **kw: AccountRequest(**kw)

	requests = types.ModuleType("requests")

	def post(url, data=None, headers=None, timeout=None):
		state["posted"].append(data)
		return state["token_reply"]

	def get(url, headers=None, timeout=None):
		state["got"].append((url, headers.get("Authorization")))
		return HttpReply(state["emails"]) if url.endswith("/user/emails") else HttpReply(state["user"])

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


def fresh_state(**over):
	state = {
		"keys": dict(KEYS),
		"cache": {},
		"ttl": {},
		"team": ["TEAM-1", 1],
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
		"user": {"name": "Owner Person", "login": "owner"},
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

	def start(self, state):
		m, f = self.load(state)
		m.login()
		return m, f

	def test_not_set_up_says_so(self):
		m, _f = self.load(fresh_state(keys=None))
		with self.assertRaises(Thrown):
			m.login()

	def test_login_sends_to_github_with_one_time_state(self):
		state = fresh_state()
		_m, f = self.start(state)
		url = urlparse(f.local.response["location"])
		q = parse_qs(url.query)
		self.assertEqual(f.local.response["type"], "redirect")
		self.assertEqual(f"{url.scheme}://{url.netloc}{url.path}", "https://github.com/login/oauth/authorize")
		self.assertEqual(q["client_id"], ["cid"])
		self.assertEqual(
			q["redirect_uri"],
			["https://autodeploypanel.mvpstorm.com/api/method/press.api.github.login_callback"],
		)
		self.assertIn("user:email", q["scope"][0])
		self.assertIn(f"github_login:{q['state'][0]}", state["cache"])
		self.assertEqual(state["ttl"][f"github_login:{q['state'][0]}"], 300)

	def test_unknown_state_is_refused(self):
		m, f = self.load(fresh_state())
		m.login_callback(code="c", state="not-ours")
		self.assertEqual(f.local.response["http_status_code"], 401)
		self.assertEqual(f.local.response.get("type"), None)

	def test_state_works_once(self):
		state = fresh_state()
		m, f = self.start(state)
		s = parse_qs(urlparse(f.local.response["location"]).query)["state"][0]
		m.login_callback(code="c", state=s)
		self.assertEqual(state["logged_in"], ["owner@example.com"])
		f.local.response.clear()
		m.login_callback(code="c", state=s)
		self.assertEqual(f.local.response["http_status_code"], 401)
		self.assertEqual(state["logged_in"], ["owner@example.com"])

	def callback(self, state, **kw):
		m, f = self.start(state)
		s = parse_qs(urlparse(f.local.response["location"]).query)["state"][0]
		f.local.response.clear()
		m.login_callback(state=s, **kw)
		return f

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
		self.assertEqual(state["pages"], ["No verified e-mail on GitHub"])
		self.assertEqual(state["logged_in"], [])

	def test_existing_account_signs_in_with_primary_verified_email(self):
		state = fresh_state()
		f = self.callback(state, code="c")
		self.assertEqual(state["logged_in"], ["owner@example.com"])
		self.assertEqual(f.local.response["location"], "/dashboard")
		self.assertEqual(state["got"][0][1], "Bearer tok")
		self.assertEqual(state["posted"][0]["client_secret"], "csecret")

	def test_deactivated_account_is_refused(self):
		state = fresh_state(team=["TEAM-1", 0])
		m, f = self.start(state)
		s = parse_qs(urlparse(f.local.response["location"]).query)["state"][0]
		with self.assertRaises(Thrown):
			m.login_callback(code="c", state=s)
		self.assertEqual(state["logged_in"], [])

	def test_account_with_2fa_goes_to_email_login(self):
		state = fresh_state(has_2fa="2FA-1")
		self.callback(state, code="c")
		self.assertEqual(state["pages"], ["Two-Factor Authentication Required"])
		self.assertEqual(state["logged_in"], [])

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
