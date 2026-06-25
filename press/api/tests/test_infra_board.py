# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.api.bench import _service_action


class TestServiceAction(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_rejects_invalid_action(self):
		fake_bench = MagicMock()
		with patch("press.api.bench.frappe.get_doc", return_value=fake_bench):
			with self.assertRaises(frappe.ValidationError):
				_service_action("bench-X-001-press-f1", "redis-queue", "delete")
		fake_bench.supervisorctl.assert_not_called()

	def test_rejects_unknown_program(self):
		fake_bench = MagicMock()
		with patch("press.api.bench.get_processes", return_value=[{"program": "redis-queue"}]), patch(
			"press.api.bench.frappe.get_doc", return_value=fake_bench
		):
			with self.assertRaises(frappe.ValidationError):
				_service_action("bench-X-001-press-f1", "ghost-program", "restart")
		fake_bench.supervisorctl.assert_not_called()

	def test_calls_supervisorctl_for_valid_program(self):
		fake_bench = MagicMock()
		with patch("press.api.bench.get_processes", return_value=[{"program": "redis-queue"}, {"program": "frappe-web"}]), patch(
			"press.api.bench.frappe.get_doc", return_value=fake_bench
		):
			result = _service_action("bench-X-001-press-f1", "redis-queue", "restart")
		fake_bench.supervisorctl.assert_called_once_with("restart", programs=["redis-queue"])
		self.assertTrue(result["ok"])
		self.assertEqual(result["action"], "restart")
		self.assertEqual(result["program"], "redis-queue")


class TestHostProbes(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_host_probes_normalizes_memory_cpu_disk_and_agent(self):
		from press.api import infra_board

		mem = {"verdict": "ok", "memory_available_mb": 12940, "memory_total_mb": 23458}
		agent = {"verdict": "healthy"}
		stats = {"cpu": {"used_pct": 15}, "disk": {"used_pct": 61}}
		with patch.object(infra_board, "_memory", return_value=mem), patch.object(
			infra_board, "_agent", return_value=agent
		), patch.object(infra_board, "_cpu_disk", return_value=stats):
			out = infra_board.host_probes("press-f1.sandbox.mvpstorm.com")

		self.assertEqual(out["memory"]["verdict"], "ok")
		self.assertEqual(out["memory"]["used_pct"], 45)
		self.assertEqual(out["cpu"]["used_pct"], 15)
		self.assertEqual(out["disk"]["used_pct"], 61)
		self.assertEqual(out["agent"]["verdict"], "healthy")
		# ssh.ok is derived from the cpu/disk probe returning data
		self.assertTrue(out["ssh"]["ok"])

	def test_host_probes_survives_failing_probe(self):
		from press.api import infra_board

		with patch.object(infra_board, "_memory", side_effect=Exception("boom")), patch.object(
			infra_board, "_agent", return_value={"verdict": "healthy"}
		), patch.object(infra_board, "_cpu_disk", side_effect=Exception("boom")):
			out = infra_board.host_probes("press-f1.sandbox.mvpstorm.com")

		self.assertIsNone(out["memory"])
		self.assertIsNone(out["cpu"])
		self.assertIsNone(out["disk"])
		self.assertEqual(out["agent"]["verdict"], "healthy")
		# cpu/disk probe failed -> server treated as unreachable
		self.assertFalse(out["ssh"]["ok"])


class TestParseCpuDisk(FrappeTestCase):
	def test_valid_line(self):
		from press.api import infra_board

		r = infra_board._parse_cpu_disk("CPU=2.0:4 DISK=53")
		self.assertEqual(r["cpu"]["used_pct"], 50)
		self.assertEqual(r["cpu"]["cores"], 4)
		self.assertEqual(r["disk"]["used_pct"], 53)

	def test_caps_cpu_at_100(self):
		from press.api import infra_board

		# load 16 on 4 cores = 400% -> capped at 100
		self.assertEqual(infra_board._parse_cpu_disk("CPU=16.0:4 DISK=10")["cpu"]["used_pct"], 100)

	def test_single_core_no_zero_division(self):
		from press.api import infra_board

		self.assertEqual(infra_board._parse_cpu_disk("CPU=0.5:0 DISK=10")["cpu"]["cores"], 1)

	def test_returns_none_on_malformed_or_empty(self):
		from press.api import infra_board

		self.assertIsNone(infra_board._parse_cpu_disk("CPU=1.0:4"))      # no DISK
		self.assertIsNone(infra_board._parse_cpu_disk("CPU=oops DISK=53"))  # cpu not load:cores
		self.assertIsNone(infra_board._parse_cpu_disk("CPU=1.0:4 DISK=x"))  # disk not int
		self.assertIsNone(infra_board._parse_cpu_disk(""))
		self.assertIsNone(infra_board._parse_cpu_disk(None))


class TestInfraTree(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_build_tree_groups_benches_by_server_with_services(self):
		from press.api import infra_board

		benches = [
			{"name": "bench-A", "server": "press-f1", "group": "g1", "status": "Active", "site_count": 1},
			{"name": "bench-B", "server": "u4", "group": "g2", "status": "Active", "site_count": 2},
		]
		procs = {
			"bench-A": [{"program": "frappe-web", "status": "Running"}, {"program": "redis-queue", "status": "Stopped"}],
			"bench-B": [{"program": "frappe-web", "status": "Running"}],
		}
		with patch.object(infra_board, "_all_servers", return_value=["press-f1", "u4"]), patch.object(
			infra_board, "_all_benches", return_value=benches
		), patch.object(infra_board, "_bench_services", side_effect=lambda b: procs[b]), patch.object(
			infra_board, "host_probes", side_effect=lambda s: {"server": s, "memory": None, "agent": None, "ssh": {"ok": True}}
		):
			tree = infra_board._build_tree()

		f1 = next(s for s in tree["servers"] if s["name"] == "press-f1")
		self.assertEqual(len(f1["benches"]), 1)
		bench_a = f1["benches"][0]
		self.assertEqual(bench_a["name"], "bench-A")
		self.assertEqual(bench_a["services_down"], 1)
		self.assertEqual(bench_a["health"], "down")

	def test_get_infra_tree_uses_cache_on_second_call(self):
		from press.api import infra_board

		frappe.cache().delete_value(infra_board.CACHE_KEY)
		calls = {"n": 0}

		def fake_build():
			calls["n"] += 1
			return {"servers": [], "built": calls["n"]}

		with patch("press.api.infra_board.frappe.only_for"), patch.object(
			infra_board, "_build_tree", side_effect=fake_build
		):
			first = infra_board.get_infra_tree()
			second = infra_board.get_infra_tree()

		self.assertEqual(calls["n"], 1)
		self.assertEqual(first["built"], second["built"])
		frappe.cache().delete_value(infra_board.CACHE_KEY)


	def test_get_infra_tree_requires_system_manager(self):
		from press.api import infra_board

		frappe.cache().delete_value(infra_board.CACHE_KEY)
		with patch("press.api.infra_board.frappe.only_for") as gate, patch.object(
			infra_board, "_build_tree", return_value={"servers": []}
		):
			infra_board.get_infra_tree()
		gate.assert_called_once_with("System Manager")
		frappe.cache().delete_value(infra_board.CACHE_KEY)

	def test_build_tree_marks_unreachable_bench_unknown(self):
		from press.api import infra_board

		benches = [{"name": "bench-C", "server": "press-f1", "group": "g", "status": "Active", "site_count": 0}]
		with patch.object(infra_board, "_all_servers", return_value=["press-f1"]), patch.object(
			infra_board, "_all_benches", return_value=benches
		), patch.object(infra_board, "_bench_services", return_value=[]), patch.object(
			infra_board, "host_probes", side_effect=lambda s: {"server": s, "memory": None, "agent": None, "ssh": {"ok": True}}
		):
			tree = infra_board._build_tree()

		bench_c = tree["servers"][0]["benches"][0]
		self.assertEqual(bench_c["health"], "unknown")
		self.assertEqual(tree["servers"][0]["health"], "down")

	def test_build_tree_attaches_telephony_for_pbx_hosts(self):
		from press.api import infra_board

		mh = frappe._dict(host_name="pbx-1", server_type="docker", ssh_host="1.2.3.4",
			ssh_port=22, ssh_user="sanad", proxy_port=2375, status="Active", last_error=None)
		ok = {"units": [], "metrics": {"cpu": 1, "mem": 1, "disk": 1, "req": 0}, "reach": "ok"}
		tele = {"trunk_registered": True, "active_calls": 4, "listener_connected": True}
		with patch.object(infra_board, "_press_servers", return_value=[]), \
			patch.object(infra_board, "_managed_hosts", return_value=[mh]), \
			patch.object(infra_board, "_enumerate_managed", return_value=ok), \
			patch.object(infra_board, "_telephony_for", return_value=tele):
			tree = infra_board._build_tree()

		node = tree["servers"][0]
		self.assertEqual(node["telephony"]["active_calls"], 4)
		self.assertTrue(node["telephony"]["trunk_registered"])

	def test_build_tree_omits_telephony_for_non_pbx_hosts(self):
		from press.api import infra_board

		mh = frappe._dict(host_name="plain-1", server_type="plain", ssh_host="h",
			ssh_port=22, ssh_user="sanad", proxy_port=2375, status="Active", last_error=None)
		ok = {"units": [], "metrics": {"cpu": 1, "mem": 1, "disk": 1, "req": 0}, "reach": "ok"}
		with patch.object(infra_board, "_press_servers", return_value=[]), \
			patch.object(infra_board, "_managed_hosts", return_value=[mh]), \
			patch.object(infra_board, "_enumerate_managed", return_value=ok), \
			patch.object(infra_board, "_telephony_for", return_value=None):
			tree = infra_board._build_tree()

		self.assertNotIn("telephony", tree["servers"][0])


class TestClassifyConnError(FrappeTestCase):
	def test_maps_known_failures_to_actionable_reasons(self):
		from press.api import infra_board as ib

		self.assertIn("Gate 0", ib.classify_conn_error("infra secret infra/ssh_ca_private is not provisioned; Gate 0 pending"))
		self.assertIn("cert rejected", ib.classify_conn_error("ssh exited 255: Permission denied (publickey)"))
		self.assertIn("socket-proxy", ib.classify_conn_error("SSH forward to host did not come up within 15s").lower())
		self.assertIn("respond", ib.classify_conn_error("operation timed out"))
		self.assertIn("refused", ib.classify_conn_error("connect: Connection refused").lower())

	def test_unknown_error_passes_through_trimmed(self):
		from press.api import infra_board as ib

		self.assertEqual(ib.classify_conn_error("  some weird thing  "), "some weird thing")
		self.assertEqual(ib.classify_conn_error(""), "Unknown connection error")


class TestGate0Status(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_ready_when_key_and_ca_pass(self):
		from press.api import infra_board as ib

		with patch.object(ib, "_control_key_present", return_value=True), patch.object(
			ib, "_gate0_ca_probe", return_value=(True, "")
		):
			r = ib.gate0_status()
		self.assertTrue(r["ready"])
		self.assertTrue(all(c["ok"] for c in r["checks"]))

	def test_not_ready_missing_control_key_gives_hint(self):
		from press.api import infra_board as ib

		with patch.object(ib, "_control_key_present", return_value=False), patch.object(
			ib, "_gate0_ca_probe", return_value=(True, "")
		):
			r = ib.gate0_status()
		self.assertFalse(r["ready"])
		key = next(c for c in r["checks"] if c["name"] == "Control-plane key")
		self.assertFalse(key["ok"])
		self.assertIn("ssh-keygen", key["hint"])

	def test_not_ready_when_ca_missing_surfaces_ca_hint(self):
		from press.api import infra_board as ib

		with patch.object(ib, "_control_key_present", return_value=True), patch.object(
			ib, "_gate0_ca_probe", return_value=(False, "CA secret missing")
		):
			r = ib.gate0_status()
		self.assertFalse(r["ready"])
		ca = next(c for c in r["checks"] if c["name"] == "SSH CA secret")
		self.assertIn("CA secret missing", ca["hint"])


class TestProvisionReasonSurfacing(FrappeTestCase):
	def test_attach_cert_captures_reason_on_sign_failure(self):
		from press.api import infra_board as ib

		frappe.cache().delete_value("infra_board:cert:frappe")
		host = frappe._dict(ssh_user="frappe")
		with patch("press.infra.ssh_ca.sign_cert", side_effect=Exception("infra secret infra/ssh_ca_private is not provisioned; Gate 0 pending")):
			out = ib._attach_cert(host)
		self.assertIsNone(out.get("ssh_cert"))
		self.assertIn("Gate 0", out._provision_error)

	def test_build_tree_surfaces_managed_host_last_error(self):
		from press.api import infra_board as ib

		mh = frappe._dict(host_name="demo-1", server_type="docker", ssh_host="127.0.0.1",
			ssh_port=2222, ssh_user="frappe", proxy_port=2375, status="Unreachable", last_error=None)
		failed = {"units": [], "metrics": {"cpu": 0, "mem": 0, "disk": 0, "req": 0},
			"reach": "fail", "reason": "Gate 0 not provisioned: the SSH CA secret is missing."}
		with patch.object(ib, "_press_servers", return_value=[]), patch.object(
			ib, "_managed_hosts", return_value=[mh]
		), patch.object(ib, "_enumerate_managed", return_value=failed):
			tree = ib._build_tree()

		node = tree["servers"][0]
		self.assertEqual(node["kind"], "managed")
		self.assertEqual(node["health"], "unknown")
		self.assertIn("Gate 0", node["last_error"])


class TestParseHostStats(FrappeTestCase):
	def test_valid_line(self):
		from press.infra.adapters.ssh_docker import parse_host_stats

		r = parse_host_stats("CPU=2.0:4 MEM=37 DISK=53")
		self.assertEqual(r["cpu"], 50)
		self.assertEqual(r["mem"], 37)
		self.assertEqual(r["disk"], 53)

	def test_caps_cpu_and_handles_zero_cores(self):
		from press.infra.adapters.ssh_docker import parse_host_stats

		self.assertEqual(parse_host_stats("CPU=16.0:4 MEM=1 DISK=1")["cpu"], 100)
		self.assertEqual(parse_host_stats("CPU=0.5:0 MEM=1 DISK=1")["cpu"], 50)

	def test_missing_or_malformed_fields_become_none(self):
		from press.infra.adapters.ssh_docker import parse_host_stats

		r = parse_host_stats("CPU=oops MEM=x DISK=")
		self.assertIsNone(r["cpu"])
		self.assertIsNone(r["mem"])
		self.assertIsNone(r["disk"])
		empty = parse_host_stats("")
		self.assertEqual(empty, {"cpu": None, "mem": None, "disk": None, "req": 0})


class TestAttachCertCacheValidation(FrappeTestCase):
	def test_resigns_when_cached_cert_file_missing(self):
		from press.api import infra_board as ib

		# A stale cache entry whose cert file no longer exists must NOT be served.
		frappe.cache().set_value("infra_board:cert:frappe", "/nonexistent/sanad-infra-cert.pub")
		host = frappe._dict(ssh_user="frappe")
		with patch("press.infra.ssh_ca.sign_cert", return_value="/tmp/fresh-cert.pub"):
			out = ib._attach_cert(host)
		self.assertEqual(out.ssh_cert, "/tmp/fresh-cert.pub")
		frappe.cache().delete_value("infra_board:cert:frappe")
