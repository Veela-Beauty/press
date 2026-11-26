"""Exposure watch (0.7.74), pinned on fakes: no network, no database, no email. Runs without a bench:
python3 -m pytest press/watch_tower/alerts/test_exposure_alerts.py"""

import importlib.util
import pathlib
import unittest

_spec = importlib.util.spec_from_file_location(
	"exposure_alerts", pathlib.Path(__file__).with_name("exposure_alerts.py")
)
ex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ex)

OPENAPI = b'{"openapi":"3.1.0","info":{"title":"x"},"paths":{}}'


def no_ports(ip):
	return []


LOGIN_URLS = [url for url, kind, _ in ex.CLOSED_URLS if kind == "login"]


def answers(table):
	"""A fake fetch: url -> (status, body). Sanad Preview pages answer 401 (its login) unless the table says
	otherwise; anything else is 404."""
	full = {url: (401, b"") for url in LOGIN_URLS} | table
	return lambda url: full.get(url, (404, b""))


class TestExposure(unittest.TestCase):
	def test_open_port_is_found_and_the_registry_exception_holds(self):
		found = ex.collect(
			probe=lambda ip: [8200] if ip == ex.SERVERS["sandbox-1"] else [],
			probe_press_ctrl=lambda ip: [5000, 8200],
			get=answers({}),
		)
		self.assertEqual(
			[w for k, w, _ in found if k == "Open port"],
			["press-ctrl 89.167.116.92:8200", "sandbox-1 65.108.128.91:8200"],
		)

	def test_route_list_needs_a_real_openapi_document(self):
		url = "https://brain.sanadeoi.mvpstorm.com/openapi.json"
		html_catch_all = answers({url: (200, b"<!doctype html><div id=app></div>")})
		self.assertEqual(ex.collect(probe=no_ports, get=html_catch_all), [])
		found = ex.collect(probe=no_ports, get=answers({url: (200, OPENAPI)}))
		self.assertEqual([(k, w) for k, w, _ in found], [("route-list", url)])

	def test_admin_without_a_key_and_preview_without_its_login(self):
		audit = "https://brain.sanadeoi.mvpstorm.com/admin/audit"
		home = ex.PREVIEW + "/"
		table = {audit: (200, b'{"entries":[]}'), home: (200, b"<html>")}
		found = ex.collect(probe=no_ports, get=answers(table))
		self.assertEqual(sorted((k, w) for k, w, _ in found), [("login", home), ("no-key", audit)])

	def test_refused_or_unreachable_is_quiet(self):
		for kind in ("route-list", "no-key", "login"):
			self.assertFalse(ex.is_open(kind, 401, b""))
			self.assertFalse(ex.is_open(kind, 0, b""))

	def test_a_404_behind_the_preview_means_the_login_is_off(self):
		# with the login on, Traefik answers 401 before nginx can say 404
		self.assertTrue(ex.is_open("login", 404, b""))

	def test_traefik_hosts_are_probed_and_templates_skipped(self):
		labels = (
			"Host(`demo.mvpstorm.com`) Host(`*.mvpstorm.com`) Host(`{{ .Name }}.x`) Host(`demo.mvpstorm.com`)"
		)
		self.assertEqual(ex.traefik_hosts(labels), ["demo.mvpstorm.com"])
		url = "https://demo.mvpstorm.com/openapi.json"
		found = ex.collect(
			probe=no_ports, get=answers({url: (200, OPENAPI)}), extra_hosts=["demo.mvpstorm.com"]
		)
		self.assertIn(("route-list", url), [(k, w) for k, w, _ in found])

	def test_vantage_command_is_built_from_constants_only(self):
		cmd = ex.vantage_command("89.167.116.92", ports=(8200, 5432))
		self.assertEqual(
			cmd,
			"(timeout 2 bash -c '</dev/tcp/89.167.116.92/8200' 2>/dev/null && echo 8200) & "
			"(timeout 2 bash -c '</dev/tcp/89.167.116.92/5432' 2>/dev/null && echo 5432) & wait",
		)

	def test_open_ports_reports_only_the_ports_that_connect(self):
		class Conn:
			def close(self):
				pass

		def connect(addr, timeout):
			if addr[1] == 8200:
				return Conn()
			raise OSError("refused")

		self.assertEqual(ex.open_ports("1.2.3.4", ports=(22, 8200, 9300), connect=connect), [8200])

	def test_every_finding_kind_has_a_fix_line(self):
		self.assertTrue({"Open port", "route-list", "no-key", "login"} <= set(ex.FIX))

	def test_rows_for_the_dashboard_are_plain_words_worst_first(self):
		found = [
			("Open port", "press-ctrl 89.167.116.92:9000", "Frappe realtime (socketio) open to the internet"),
			("Open port", "sandbox-1 65.108.128.91:3000", "Daytona API open to the internet"),
			(
				"route-list",
				"https://brain.sanadeoi.mvpstorm.com/openapi.json",
				"Sanad Brain: lists all its routes publicly",
			),
			(
				"no-key",
				"https://brain.sanadeoi.mvpstorm.com/admin/audit",
				"Sanad Brain: audit log answers without a key",
			),
		]
		rows = ex.to_rows(found)
		self.assertEqual(
			[(r["severity"], r["where"], r["what"]) for r in rows],
			[
				("High", "Sanad Brain", "audit log answers without a key"),
				("Medium", "Sanad Brain", "lists all its routes publicly"),
				("Medium", "sandbox-1 :3000", "Daytona API open to the internet"),
				("Low", "press-ctrl :9000", "Frappe realtime (socketio) open to the internet"),
			],
		)
		self.assertTrue(all(r["fix"] for r in rows))

	def test_an_open_port_names_its_service_or_says_a_service(self):
		found = ex.collect(
			probe=lambda ip: [3000, 6379] if ip == ex.SERVERS["sandbox-1"] else [], get=answers({})
		)
		self.assertEqual(
			sorted(w for k, _, w in found if k == "Open port"),
			["A service open to the internet", "Daytona API open to the internet"],
		)


if __name__ == "__main__":
	unittest.main()
