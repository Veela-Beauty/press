"""press.api.messaging (owner 2026-11-27). No site needed: python3 -m unittest press.messaging.test_messaging_api -v

Lives beside the routes tests, not in press/api: the loader imports the test's package first, and press/api/__init__.py
imports frappe and the whole client API before any stub could be set. Here `press.api` is stubbed as a bare package."""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

_frappe = types.ModuleType("frappe")
_frappe.db = MagicMock()
_frappe.get_doc = MagicMock()
_frappe.get_all = MagicMock(return_value=[])
_frappe.get_single = MagicMock()
_frappe.whitelist = lambda *a, **k: lambda f: f
_frappe.session = types.SimpleNamespace(user="owner@example.com")
_frappe.PermissionError = type("PermissionError", (Exception,), {})
_frappe.ValidationError = type("ValidationError", (Exception,), {})
_frappe._ = lambda s: s
_frappe.throw = MagicMock(side_effect=lambda msg, exc=Exception: (_ for _ in ()).throw(exc(msg)))
_frappe.generate_hash = MagicMock(return_value="tok-new")
_frappe.utils = types.ModuleType("frappe.utils")
_frappe.utils.get_url = MagicMock(return_value="https://press.example.com")
_frappe.utils.nowdate = MagicMock(return_value="2026-11-27")
_rate = types.ModuleType("frappe.rate_limiter")
_rate.rate_limit = lambda *a, **k: lambda f: f
_roles = types.ModuleType("press.press.doctype.team.team_roles")
_roles.has_role_access = MagicMock(return_value=True)
_agent = types.ModuleType("press.agent")
_agent.Agent = MagicMock()
_api = types.ModuleType("press.api")
_api.__path__ = [str(__import__("pathlib").Path(__file__).resolve().parents[1] / "api")]
for _name, _mod in {
	"press.api": _api,
	"frappe": _frappe,
	"frappe.utils": _frappe.utils,
	"frappe.rate_limiter": _rate,
	"press.press.doctype.team.team_roles": _roles,
	"press.agent": _agent,
}.items():
	sys.modules.setdefault(_name, _mod)

from press.api import messaging as m  # noqa: E402


class TestOwnerOnly(unittest.TestCase):
	def test_a_non_owner_is_refused_everywhere(self):
		with (
			patch.object(m, "has_role_access", return_value=False),
			patch.object(m, "_is_system_user", return_value=True),
		):
			for call in (m.list_sites, m.cost_by_client, m.get_routes, m.list_providers):
				with self.assertRaises(_frappe.PermissionError):
					call()

	def test_a_website_user_is_refused(self):
		with (
			patch.object(m, "has_role_access", return_value=True),
			patch.object(m, "_is_system_user", return_value=False),
		):
			with self.assertRaises(_frappe.PermissionError):
				m.list_sites()


class TestRequestSms(unittest.TestCase):
	def setUp(self):
		self.site = types.SimpleNamespace(name="hr.example.com", team="TEAM-1", status="Active")
		patches = [
			patch.object(m, "_stored_token", return_value="tok-123"),
			patch.object(m, "_site_row", return_value=self.site),
			patch.object(m, "_routes", return_value=m.routes.DEFAULT_ROUTES),
			patch.object(m, "_log"),
		]
		self.mocks = [p.start() for p in patches]
		for p in patches:
			self.addCleanup(p.stop)
		self.log = self.mocks[3]

	def test_a_wrong_key_is_refused_and_not_logged(self):
		with self.assertRaises(_frappe.PermissionError):
			m.request_sms(site="hr.example.com", token="nope", e164="+966551234567", text="t")
		self.log.assert_not_called()

	def test_an_inactive_site_is_refused(self):
		self.site.status = "Suspended"
		with self.assertRaises(_frappe.PermissionError):
			m.request_sms(site="hr.example.com", token="tok-123", e164="+966551234567", text="t")

	def test_firebase_route_logs_and_answers_firebase(self):
		out = m.request_sms(site="hr.example.com", token="tok-123", e164="+966551234567", text="t")
		self.assertEqual(out, {"mode": "firebase"})
		kwargs = self.log.call_args.kwargs
		self.assertEqual(
			(kwargs["country"], kwargs["provider"], kwargs["cost_usd"], kwargs["mode"]),
			("SA", "Google Firebase", 0.18, "firebase"),
		)
		self.assertNotIn("text", kwargs)
		self.assertNotIn("e164", kwargs)

	def test_server_route_sends_then_logs(self):
		table = {
			"EG": {"provider": "smseg Egypt", "price": 0.05},
			"default": {"provider": "Google Firebase", "price": 0.2},
		}
		with (
			patch.object(m, "_routes", return_value=table),
			patch.object(m, "_send_through", return_value=(True, "ok")) as send,
		):
			out = m.request_sms(site="hr.example.com", token="tok-123", e164="+201012345678", text="code")
		self.assertEqual(out, {"mode": "server"})
		send.assert_called_once_with("smseg Egypt", "+201012345678", "code")
		self.assertEqual(self.log.call_args.kwargs["cost_usd"], 0.05)

	def test_a_failed_provider_is_an_error_logged_as_not_delivered(self):
		table = {
			"EG": {"provider": "smseg Egypt", "price": 0.05},
			"default": {"provider": "Google Firebase", "price": 0.2},
		}
		with (
			patch.object(m, "_routes", return_value=table),
			patch.object(m, "_send_through", return_value=(False, "HTTP 401")),
		):
			with self.assertRaises(_frappe.ValidationError):
				m.request_sms(site="hr.example.com", token="tok-123", e164="+201012345678", text="code")
		self.assertEqual(self.log.call_args.kwargs["delivered"], 0)


class TestCountry(unittest.TestCase):
	def test_country_from_the_number(self):
		self.assertEqual(m._country("+966551234567"), "SA")
		self.assertEqual(m._country("+201012345678"), "EG")
		self.assertEqual(m._country("+33612345678"), "")


class TestMonth(unittest.TestCase):
	def test_month_range(self):
		self.assertEqual(m._month_range("2026-11"), ("2026-11-01", "2026-12-01"))
		self.assertEqual(m._month_range("2026-12"), ("2026-12-01", "2027-01-01"))
		self.assertEqual(m._month_range(None), ("2026-11-01", "2026-12-01"))
		with self.assertRaises(ValueError):
			m._month_range("11-2026")
