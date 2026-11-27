"""The disk, SSH and site-down checks with alert_state wired in (0.7.85), run on fakes: frappe, the mailer, SSH and
HTTP. No bench, no network. Runs without a bench: python3 -m unittest test_alert_on_change_wiring (from this folder)."""

import datetime
import importlib
import pathlib
import sys
import types
import unittest

HERE = pathlib.Path(__file__).resolve().parent


class FakeCache:
	def __init__(self):
		self.data = {}

	def get_value(self, key, expires=False):
		return self.data.get(key)

	def set_value(self, key, value, expires_in_sec=None):
		self.data[key] = value

	def delete_value(self, key):
		self.data.pop(key, None)


class Row(dict):
	__getattr__ = dict.get


def _install_fakes():
	sent, cache, db = [], FakeCache(), {"rows": []}
	frappe = types.ModuleType("frappe")
	frappe.cache = lambda: cache
	frappe.db = types.SimpleNamespace(sql=lambda *a, **k: db["rows"])
	frappe.logger = lambda *a, **k: types.SimpleNamespace(error=print, info=print, warning=print)
	frappe._dict = Row
	utils = types.ModuleType("frappe.utils")
	utils.now_datetime = utils.get_datetime = lambda *a: datetime.datetime(2026, 11, 27, 12, 0)
	frappe.utils = utils
	mail = types.ModuleType("press.watch_tower.email_branding")
	mail.wrap_email = lambda title, body, footer: body
	mail.send_alert_email = lambda **kw: sent.append(kw) or True
	modules = {"frappe": frappe, "frappe.utils": utils, "press.watch_tower.email_branding": mail}
	for name, path in (
		("press", HERE.parent.parent),
		("press.watch_tower", HERE.parent),
		("press.watch_tower.alerts", HERE),
	):
		pkg = types.ModuleType(name)
		pkg.__path__ = [str(path)]
		modules[name] = pkg
	sys.modules.update(modules)
	return sent, db


def _how(call):
	if call.get("important") or call.get("immediate"):
		return "cleared" if "cleared" in call["subject"] else "email"
	return "digest"


class TestWiring(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.saved = dict(sys.modules)
		cls.sent, cls.db = _install_fakes()
		cls.infra = importlib.import_module("press.watch_tower.alerts.infra_alerts")
		cls.site = importlib.import_module("press.watch_tower.alerts.site_alerts")

	@classmethod
	def tearDownClass(cls):
		sys.modules.clear()
		sys.modules.update(cls.saved)

	def step(self, run):
		self.sent.clear()
		run()
		return [_how(c) for c in self.sent]

	def test_ssh_emails_once_digests_repeats_and_says_cleared_once(self):
		self.db["rows"] = [{"name": "s1", "ip": "10.0.0.1"}]
		answers = {"r": (False, "", "timeout")}
		self.infra.ssh_cmd = lambda ip, cmd, timeout=15: answers["r"]
		def ssh():
			return self.infra.check_ssh_connectivity({}, None)
		self.assertEqual(self.step(ssh), ["email"])
		answers["r"] = (False, "", "connection reset")  # new error text: no new email
		self.assertEqual(self.step(ssh), ["digest"])
		answers["r"] = (True, "OK", "")
		self.assertEqual(self.step(ssh), ["cleared"])
		self.assertEqual(self.step(ssh), [])

	def test_disk_band_95_re_alerts_and_unreachable_is_not_cleared(self):
		disk = {"pct": 90, "ok": True}
		self.infra.get_all_servers = lambda: [{"name": "a", "ip": "10.0.0.2"}]
		self.infra.ssh_cmd = lambda ip, cmd, timeout=15: (
			(True, f"/dev/sda1 100G {disk['pct']}G 1G {disk['pct']}% /\n", "")
			if disk["ok"]
			else (False, "", "down")
		)
		def run():
			return self.infra.check_server_disk_usage({}, None)
		self.assertEqual(self.step(run), ["email"])
		disk["pct"] = 91
		self.assertEqual(self.step(run), ["digest"])
		disk["pct"] = 96
		self.assertEqual(self.step(run), ["email"])
		disk["ok"] = False  # no reading: not a recovery
		self.assertEqual(self.step(run), [])
		disk.update(ok=True, pct=50)
		self.assertEqual(self.step(run), ["cleared"])

	def test_site_down_once_then_digest_then_cleared(self):
		self.db["rows"] = [Row(name="x.example.com", bench="b1", status="Active")]
		state = {"code": 502}
		req = types.ModuleType("requests")
		req.exceptions = types.SimpleNamespace(
			SSLError=type("SSLError", (Exception,), {}),
			ConnectionError=type("ConnectionError", (Exception,), {}),
			Timeout=type("Timeout", (Exception,), {}),
		)
		req.get = lambda *a, **k: types.SimpleNamespace(status_code=state["code"])
		sys.modules["requests"] = req
		def run():
			return self.site.check_site_reachability({}, None)
		self.assertEqual(self.step(run), ["email"])
		state["code"] = 503
		self.assertEqual(self.step(run), ["digest"])
		state["code"] = 200
		self.assertEqual(self.step(run), ["cleared"])
		self.assertEqual(self.sent[0].get("important"), True)


if __name__ == "__main__":
	unittest.main()
