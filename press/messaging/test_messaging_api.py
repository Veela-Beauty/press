"""press.api.messaging (owner 2026-11-27). No site needed: python3 -m unittest press.messaging.test_messaging_api -v

Lives beside the routes tests, not in press/api: the loader imports the test's package first, and press/api/__init__.py
imports frappe and the whole client API before any stub could be set. Here `press.api` is stubbed as a bare package.
Needs the `phonenumbers` package (it ships with Frappe)."""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

_frappe = types.ModuleType("frappe")
_frappe.db = MagicMock()
_frappe.get_doc = MagicMock()
_frappe.get_all = MagicMock(return_value=[])
_frappe.get_single = MagicMock()
_frappe.cache = MagicMock()
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


class FakeCache:
	"""Just the Redis calls the counter uses."""

	def __init__(self):
		self.counts = {}
		self.ttls = {}

	def make_key(self, key):
		return f"test|{key}"

	def incrby(self, key, n):
		self.counts[key] = self.counts.get(key, 0) + n
		return self.counts[key]

	def ttl(self, key):
		return self.ttls.get(key, -1)

	def expire(self, key, seconds):
		self.ttls[key] = seconds


OWNER_CALLS = (
	lambda: m.list_sites(),
	lambda: m.set_sms_codes("hr.example.com", 1),
	lambda: m.sms_log(),
	lambda: m.cost_by_client(),
	lambda: m.get_routes(),
	lambda: m.save_routes("[]"),
	lambda: m.list_providers(),
	lambda: m.save_provider("smseg", "smseg", "Basher"),
	lambda: m.test_provider("smseg", "+201012345678"),
)


class TestOwnerOnly(unittest.TestCase):
	def test_a_non_owner_is_refused_everywhere(self):
		with (
			patch.object(m, "has_role_access", return_value=False),
			patch.object(m, "_is_system_user", return_value=True),
		):
			for call in OWNER_CALLS:
				with self.assertRaises(_frappe.PermissionError):
					call()

	def test_a_website_user_is_refused_everywhere(self):
		with (
			patch.object(m, "has_role_access", return_value=True),
			patch.object(m, "_is_system_user", return_value=False),
		):
			for call in OWNER_CALLS:
				with self.assertRaises(_frappe.PermissionError):
					call()


class TestRequestSms(unittest.TestCase):
	def setUp(self):
		self.site = types.SimpleNamespace(name="hr.example.com", team="TEAM-1", status="Active")
		self.cache = FakeCache()
		_frappe.db.reset_mock()
		_frappe.db.get_single_value.return_value = 200
		patches = [
			patch.object(m, "_stored_token", return_value="tok-123"),
			patch.object(m, "_site_row", return_value=self.site),
			patch.object(m, "_routes", return_value=m.routes.DEFAULT_ROUTES),
			patch.object(m, "_log", return_value="SMS-LOG-1"),
			patch.object(_frappe, "cache", self.cache),
		]
		self.mocks = [p.start() for p in patches]
		for p in patches:
			self.addCleanup(p.stop)
		self.log = self.mocks[3]
		self.egypt = {
			"EG": {"provider": "smseg Egypt", "price": 0.05},
			"default": {"provider": "Google Firebase", "price": 0.2},
		}

	def ask(self, e164="+966551234567", code="123456", **extra):
		return m.request_sms(site="hr.example.com", token="tok-123", e164=e164, code=code, **extra)

	def test_free_text_is_not_accepted(self):
		with self.assertRaises(TypeError):
			m.request_sms(site="hr.example.com", token="tok-123", e164="+966551234567", text="Buy now")

	def test_a_code_that_is_not_six_ascii_digits_is_refused(self):
		for bad in ("1234567", "12345", "12a456", "", "١٢٣٤٥٦", "123456\n", "free text"):
			with self.assertRaises(_frappe.ValidationError, msg=repr(bad)):
				self.ask(code=bad)
		self.log.assert_not_called()

	def test_a_wrong_key_is_refused_and_not_logged(self):
		with self.assertRaises(_frappe.PermissionError):
			m.request_sms(site="hr.example.com", token="nope", e164="+966551234567", code="123456")
		self.log.assert_not_called()

	def test_an_inactive_site_is_refused(self):
		self.site.status = "Suspended"
		with self.assertRaises(_frappe.PermissionError):
			self.ask()
		self.log.assert_not_called()

	def test_firebase_route_logs_and_answers_firebase(self):
		self.assertEqual(self.ask(), {"mode": "firebase"})
		kwargs = self.log.call_args.kwargs
		self.assertEqual(
			(kwargs["country"], kwargs["provider"], kwargs["cost_usd"], kwargs["mode"], kwargs["delivered"]),
			("SA", "Google Firebase", 0.18, "firebase", 1),
		)
		for stored in ("text", "e164", "code"):
			self.assertNotIn(stored, kwargs)

	def test_server_route_sends_press_template_and_marks_delivered(self):
		with (
			patch.object(m, "_routes", return_value=self.egypt),
			patch.object(m, "_send_through", return_value=(True, "ok")) as send,
		):
			out = self.ask(e164="+201012345678")
		self.assertEqual(out, {"mode": "server"})
		send.assert_called_once_with(
			"smseg Egypt", "+201012345678", "Your Basher activation code is 123456. It works for 10 minutes."
		)
		self.assertEqual(self.log.call_args.kwargs["delivered"], 0)
		self.assertEqual(self.log.call_args.kwargs["cost_usd"], 0.05)
		_frappe.db.set_value.assert_called_once_with("SMS Log", "SMS-LOG-1", "delivered", 1)

	def test_arabic_text_for_lang_ar_and_english_for_anything_else(self):
		with (
			patch.object(m, "_routes", return_value=self.egypt),
			patch.object(m, "_send_through", return_value=(True, "ok")) as send,
		):
			self.ask(e164="+201012345678", lang="ar")
			self.assertEqual(send.call_args.args[2], "رمز تفعيل باشر: 123456. يصلح 10 دقائق.")
			self.ask(e164="+201012345679", lang="fr")
			self.assertEqual(
				send.call_args.args[2], "Your Basher activation code is 123456. It works for 10 minutes."
			)

	def test_a_failed_provider_answers_failed_and_the_row_stays_not_delivered(self):
		with (
			patch.object(m, "_routes", return_value=self.egypt),
			patch.object(m, "_send_through", return_value=(False, "HTTP 401")),
		):
			out = self.ask(e164="+201012345678")
		self.assertEqual(out, {"mode": "failed"})
		self.assertEqual(self.log.call_args.kwargs["delivered"], 0)
		_frappe.db.set_value.assert_not_called()

	def test_the_sixth_request_for_one_number_in_an_hour_is_refused(self):
		for _ in range(5):
			self.assertEqual(self.ask(), {"mode": "firebase"})
		self.assertEqual(self.ask(), {"mode": "refused"})
		self.assertEqual(self.log.call_count, 5)
		self.assertEqual(self.ask(e164="+966551234999"), {"mode": "firebase"})

	def test_reaching_the_site_cap_is_refused(self):
		_frappe.db.get_single_value.return_value = 3
		for n in range(3):
			self.assertEqual(self.ask(e164=f"+96655123400{n}"), {"mode": "firebase"})
		self.assertEqual(self.ask(e164="+966551234009"), {"mode": "refused"})
		self.assertEqual(self.log.call_count, 3)

	def test_the_counter_window_is_one_hour(self):
		self.ask()
		self.assertEqual(set(self.cache.ttls.values()), {3600})


class TestSetSmsCodes(unittest.TestCase):
	def setUp(self):
		self.doc = MagicMock()
		self.doc.status = "Active"
		self.doc.server = "f1.example.com"
		self.doc.apps = [types.SimpleNamespace(app="frappe"), types.SimpleNamespace(app="basher_hr")]
		self.doc.configuration = [
			types.SimpleNamespace(key="basher_sms_token"),
			types.SimpleNamespace(key="basher_sms_press_url"),
			types.SimpleNamespace(key="other"),
		]
		_agent.Agent.reset_mock()
		patches = [
			patch.object(m, "_only_owner"),
			patch.object(_frappe, "get_doc", return_value=self.doc),
			patch.object(m, "_stored_token", return_value=None),
		]
		self.mocks = [p.start() for p in patches]
		for p in patches:
			self.addCleanup(p.stop)

	def test_on_writes_both_keys_and_tells_the_agent(self):
		out = m.set_sms_codes("hr.example.com", 1)
		self.assertEqual(out, {"site": "hr.example.com", "on": True})
		self.doc._update_configuration.assert_called_once_with(
			{"basher_sms_token": "tok-new", "basher_sms_press_url": "https://press.example.com"}
		)
		_agent.Agent.assert_called_once_with("f1.example.com")
		_agent.Agent.return_value.update_site_config.assert_called_once_with(self.doc)

	def test_on_again_keeps_the_existing_token(self):
		self.mocks[2].return_value = "tok-old"
		m.set_sms_codes("hr.example.com", "1")
		self.doc._update_configuration.assert_called_once_with(
			{"basher_sms_token": "tok-old", "basher_sms_press_url": "https://press.example.com"}
		)

	def test_off_removes_both_keys_and_saves(self):
		out = m.set_sms_codes("hr.example.com", 0)
		self.assertEqual(out["on"], False)
		self.assertEqual([r.key for r in self.doc.configuration], ["other"])
		self.doc.save.assert_called_once()
		_agent.Agent.return_value.update_site_config.assert_called_once_with(self.doc)

	def test_a_site_without_basher_or_not_active_is_refused(self):
		self.doc.apps = [types.SimpleNamespace(app="frappe")]
		with self.assertRaises(_frappe.ValidationError):
			m.set_sms_codes("hr.example.com", 1)
		self.doc.apps = [types.SimpleNamespace(app="basher_hr")]
		self.doc.status = "Suspended"
		with self.assertRaises(_frappe.ValidationError):
			m.set_sms_codes("hr.example.com", 1)
		self.doc._update_configuration.assert_not_called()
		_agent.Agent.return_value.update_site_config.assert_not_called()


class TestSaveRoutes(unittest.TestCase):
	def test_the_cap_must_be_a_whole_number_from_1_to_100000(self):
		with patch.object(m, "_only_owner"):
			for bad in ("0", "100001", "x", "2.5"):
				with self.assertRaises(_frappe.ValidationError, msg=bad):
					m.save_routes("[]", site_hourly_cap=bad)


class TestCountry(unittest.TestCase):
	def test_country_from_the_number(self):
		self.assertEqual(m._country("+966551234567"), "SA")
		self.assertEqual(m._country("+201012345678"), "EG")
		self.assertEqual(m._country("+16505550123"), "US")
		self.assertEqual(m._country("junk"), "")
		self.assertEqual(m._country(""), "")
		self.assertEqual(m._country(None), "")


class TestMonth(unittest.TestCase):
	def test_month_range(self):
		self.assertEqual(m._month_range("2026-11"), ("2026-11-01", "2026-12-01"))
		self.assertEqual(m._month_range("2026-12"), ("2026-12-01", "2027-01-01"))
		self.assertEqual(m._month_range(None), ("2026-11-01", "2026-12-01"))
		with self.assertRaises(ValueError):
			m._month_range("11-2026")

	def test_a_bad_month_is_a_validation_error_for_callers(self):
		with patch.object(m, "_only_owner"):
			for call in (lambda: m.sms_log(month="11-2026"), lambda: m.cost_by_client(month="x")):
				with self.assertRaises(_frappe.ValidationError):
					call()
