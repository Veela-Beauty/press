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

	def test_host_probes_normalizes_memory_and_agent(self):
		from press.api import infra_board

		mem = {"verdict": "ok", "memory_available_mb": 12940, "memory_total_mb": 23458}
		agent = {"verdict": "healthy"}
		with patch.object(infra_board, "_memory", return_value=mem), patch.object(
			infra_board, "_agent", return_value=agent
		), patch.object(infra_board, "_ssh_ok", return_value=True):
			out = infra_board.host_probes("press-f1.sandbox.mvpstorm.com")

		self.assertEqual(out["memory"]["verdict"], "ok")
		self.assertEqual(out["memory"]["used_pct"], 45)
		self.assertEqual(out["agent"]["verdict"], "healthy")
		self.assertTrue(out["ssh"]["ok"])

	def test_host_probes_survives_failing_probe(self):
		from press.api import infra_board

		with patch.object(infra_board, "_memory", side_effect=Exception("boom")), patch.object(
			infra_board, "_agent", return_value={"verdict": "healthy"}
		), patch.object(infra_board, "_ssh_ok", return_value=True):
			out = infra_board.host_probes("press-f1.sandbox.mvpstorm.com")

		self.assertIsNone(out["memory"])
		self.assertEqual(out["agent"]["verdict"], "healthy")


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
