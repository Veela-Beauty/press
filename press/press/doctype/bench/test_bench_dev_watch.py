"""Unit tests for press.press.doctype.bench.bench_dev_watch.

Mocks Bench.docker_execute so tests run without a live container.
"""

from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

from press.press.doctype.bench.bench_dev_watch import (
	WATCH_LOCK_FILE,
	WATCH_PID_FILE,
	_is_watch_running,
	get_watch_status,
	restart_watch,
	start_watch,
	stop_watch,
)


class FakeBench:
	"""Minimal Bench stand-in with a mockable docker_execute.

	docker_execute returns successive entries from the `outputs` list — one
	per call. Each entry must look like {"output": str, "returncode": int}.
	"""

	def __init__(self, name="test-bench-0001-press-f1", outputs=None):
		self.name = name
		self.is_development_bench = 1
		self.docker_execute = MagicMock(side_effect=outputs or [])


class TestWatchLifecycle(FrappeTestCase):
	def test_start_watch_idempotent_when_running(self):
		"""start_watch must not spawn a second process if one is already alive."""
		bench = FakeBench(outputs=[{"output": "running\n", "returncode": 0}])
		result = start_watch(bench)
		self.assertEqual(result, {"started": False, "reason": "already_running"})
		# Only the running-check should have hit docker_execute, not the spawn
		self.assertEqual(bench.docker_execute.call_count, 1)

	def test_start_watch_spawns_when_stopped(self):
		"""start_watch spawns when no live PID is tracked."""
		bench = FakeBench(
			outputs=[
				{"output": "stopped\n", "returncode": 0},  # _is_watch_running
				{"output": "", "returncode": 0},  # the spawn
			]
		)
		result = start_watch(bench)
		self.assertEqual(result, {"started": True})
		self.assertEqual(bench.docker_execute.call_count, 2)
		# Verify the spawn call uses flock + bench watch + writes the PID
		spawn_cmd = bench.docker_execute.call_args_list[1][0][0]
		self.assertIn("flock", spawn_cmd)
		self.assertIn("bench watch", spawn_cmd)
		self.assertIn(WATCH_PID_FILE, spawn_cmd)
		self.assertIn(WATCH_LOCK_FILE, spawn_cmd)

	def test_stop_watch_kills_and_cleans(self):
		bench = FakeBench(outputs=[{"output": "", "returncode": 0}])
		result = stop_watch(bench)
		self.assertEqual(result, {"stopped": True})
		stop_cmd = bench.docker_execute.call_args[0][0]
		self.assertIn("kill", stop_cmd)
		self.assertIn(WATCH_PID_FILE, stop_cmd)

	def test_is_watch_running_returns_false_for_dead_pid(self):
		bench = FakeBench(outputs=[{"output": "stopped\n", "returncode": 0}])
		self.assertFalse(_is_watch_running(bench))

	def test_is_watch_running_returns_true_for_live_pid(self):
		bench = FakeBench(outputs=[{"output": "running\n", "returncode": 0}])
		self.assertTrue(_is_watch_running(bench))


class TestWatchStatus(FrappeTestCase):
	@patch("press.press.doctype.bench.bench_dev_watch.frappe.db.get_value")
	@patch("press.press.doctype.bench.bench_dev_watch.ensure_team_access")
	def test_get_watch_status_short_circuits_for_non_dev(self, _access, get_value):
		"""Non-dev benches must NOT trigger a docker_execute (perf protection)."""
		get_value.return_value = 0
		result = get_watch_status("any-bench-name")
		self.assertEqual(result, {"running": False, "is_dev_bench": False})
		# Single-column read, never opened the doc, never executed in container
		get_value.assert_called_once_with("Bench", "any-bench-name", "is_development_bench")

	@patch("press.press.doctype.bench.bench_dev_watch.frappe.get_doc")
	@patch("press.press.doctype.bench.bench_dev_watch.frappe.db.get_value")
	@patch("press.press.doctype.bench.bench_dev_watch.ensure_team_access")
	def test_get_watch_status_returns_running_for_live_dev_bench(
		self, _access, get_value, get_doc
	):
		get_value.return_value = 1
		bench = FakeBench(
			outputs=[
				{
					"output": "running:12345\nbuild line 1\nbuild line 2",
					"returncode": 0,
				}
			]
		)
		get_doc.return_value = bench
		result = get_watch_status("test-bench")
		self.assertTrue(result["running"])
		self.assertEqual(result["pid"], 12345)
		self.assertIn("build line 1", result["log_tail"])

	@patch("press.press.doctype.bench.bench_dev_watch.frappe.get_doc")
	@patch("press.press.doctype.bench.bench_dev_watch.frappe.db.get_value")
	@patch("press.press.doctype.bench.bench_dev_watch.ensure_team_access")
	def test_restart_watch_calls_stop_then_start(self, _access, get_value, get_doc):
		get_value.return_value = 1
		bench = FakeBench(
			outputs=[
				{"output": "", "returncode": 0},  # stop
				{"output": "stopped\n", "returncode": 0},  # _is_watch_running inside start
				{"output": "", "returncode": 0},  # spawn
			]
		)
		get_doc.return_value = bench
		result = restart_watch("test-bench")
		self.assertEqual(result, {"started": True})
		# stop + is_running + spawn = 3 calls
		self.assertEqual(bench.docker_execute.call_count, 3)


class TestBenchDashboardFieldsRegression(FrappeTestCase):
	"""Regression test for the dashboard_fields whitelist on Bench.

	Background: on 2026-04-29 the Watch panel + 'Mark as Dev Bench' button
	silently broke because is_development_bench was missing from this tuple.
	Press's press.api.client.get_list filters response fields to dashboard_fields,
	so the field never reached the UI even though it was requested in the query.
	This test locks in the contract.

	Lives here (not in test_bench.py) because test_bench.py's import chain
	requires the `moto` AWS mocking library which isn't always installed —
	this test must NOT depend on AWS test fixtures.
	"""

	def test_is_development_bench_in_dashboard_fields(self):
		from press.press.doctype.bench.bench import Bench

		self.assertIn(
			"is_development_bench",
			Bench.dashboard_fields,
			"is_development_bench MUST be in Bench.dashboard_fields — the dashboard "
			"depends on it for the Mark/Unset Dev Bench toggle and the Auto-Rebuild "
			"watch panel. Removing it silently breaks both surfaces.",
		)
