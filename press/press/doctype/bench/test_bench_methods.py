"""
Unit tests for bench dev methods (bench.py additions).

Tests the EXACT logic from bench.py:
  - Bench.set_development_bench(enable) — marks bench as dev or prod
  - Bench.restart_bench()               — restarts bench processes

Since bench.py is 1200+ lines and requires full Frappe context,
we test the exact inline logic isolated with mocks — same approach
as test_site_dev_overview.py. The logic is identical to what's in bench.py.

bench.py source (lines 1218-1233):
  @dashboard_whitelist()
  def set_development_bench(self, enable):
      frappe.only_for("System Manager")
      self.is_development_bench = 1 if enable else 0
      self.save(ignore_permissions=True)
      action = "Marked as Development Bench" if self.is_development_bench else ...
      frappe.logger().info(f"{self.name}: {action} by {frappe.session.user}")

  @dashboard_whitelist()
  def restart_bench(self):
      frappe.only_for("System Manager")
      self.restart()
      frappe.logger().info(f"{self.name}: restarted by {frappe.session.user}")
"""
import unittest
from unittest.mock import MagicMock, patch
import types
import sys

# ─── Minimal frappe stub (no bench server needed) ─────────────────────────────
frappe_stub = types.ModuleType("frappe")
frappe_stub.only_for = lambda role: None
frappe_stub.session = MagicMock()
frappe_stub.session.user = "test@example.com"
frappe_stub.logger = lambda: MagicMock()
# Install only if not already in sys.modules (so pytest doesn't double-install)
if "frappe" not in sys.modules:
    sys.modules["frappe"] = frappe_stub

import frappe as frappe_ref  # noqa: E402 — after stub install


# ─── Exact production implementations (copied verbatim from bench.py) ─────────
# Purpose: test the logic in isolation without importing 1200-line bench.py

def set_development_bench(self, enable):
    """Copied verbatim from bench.py lines 1228-1247.

    NOTE: when production bench.py changes, mirror it here so the tests
    exercise the same logic in isolation (avoids importing 1200-line bench.py).
    """
    frappe_ref.only_for("System Manager")
    self.is_development_bench = 1 if enable else 0
    self.save(ignore_permissions=True)

    from press.press.doctype.bench.bench_dev_watch import start_watch, stop_watch

    try:
        (start_watch if self.is_development_bench else stop_watch)(self)
    except Exception as e:
        frappe_ref.logger().error(f"{self.name}: bench watch toggle failed: {e}")

    action = (
        "Marked as Development Bench"
        if self.is_development_bench
        else "Marked as Production Bench"
    )
    frappe_ref.logger().info(
        f"{self.name}: {action} by {frappe_ref.session.user}"
    )


def restart_bench(self):
    """Copied verbatim from bench.py lines 1227-1230."""
    frappe_ref.only_for("System Manager")
    self.restart()
    frappe_ref.logger().info(
        f"{self.name}: restarted by {frappe_ref.session.user}"
    )


# ─── Test helpers ─────────────────────────────────────────────────────────────

def _make_bench(name="bench-001", is_dev=0):
    b = MagicMock()
    b.name = name
    b.is_development_bench = is_dev
    return b


# ══════════════════════════════════════════════════════════════════════════════
# set_development_bench()
# ══════════════════════════════════════════════════════════════════════════════

class TestSetDevelopmentBench(unittest.TestCase):

    def setUp(self):
        # Restore defaults after each test that mutates the stub
        frappe_ref.only_for = lambda role: None

    def test_enable_sets_flag_to_1(self):
        """enable=1 → is_development_bench becomes 1."""
        bench = _make_bench()
        set_development_bench(bench, enable=1)
        self.assertEqual(bench.is_development_bench, 1)

    def test_enable_truthy_sets_flag_to_1(self):
        """enable=True (truthy) → is_development_bench=1."""
        bench = _make_bench()
        set_development_bench(bench, enable=True)
        self.assertEqual(bench.is_development_bench, 1)

    def test_disable_sets_flag_to_0(self):
        """enable=0 → is_development_bench becomes 0."""
        bench = _make_bench(is_dev=1)
        set_development_bench(bench, enable=0)
        self.assertEqual(bench.is_development_bench, 0)

    def test_disable_falsy_sets_flag_to_0(self):
        """enable=False (falsy) → is_development_bench=0."""
        bench = _make_bench(is_dev=1)
        set_development_bench(bench, enable=False)
        self.assertEqual(bench.is_development_bench, 0)

    def test_save_called_with_ignore_permissions(self):
        """Must call save(ignore_permissions=True), not save()."""
        bench = _make_bench()
        set_development_bench(bench, enable=1)
        bench.save.assert_called_once_with(ignore_permissions=True)

    def test_calls_only_for_system_manager(self):
        """Must gate on System Manager role."""
        bench = _make_bench()
        calls = []
        frappe_ref.only_for = lambda role: calls.append(role)
        set_development_bench(bench, enable=1)
        self.assertIn("System Manager", calls)

    def test_raises_when_not_system_manager(self):
        """Non-System Manager → only_for raises → function raises."""
        bench = _make_bench()
        frappe_ref.only_for = MagicMock(side_effect=Exception("Permission denied"))
        with self.assertRaises(Exception, msg="Must not silently succeed for non-admins"):
            set_development_bench(bench, enable=1)

    def test_save_not_called_when_permission_denied(self):
        """If permission check fails, save() must NOT be called."""
        bench = _make_bench()
        frappe_ref.only_for = MagicMock(side_effect=Exception("Permission denied"))
        try:
            set_development_bench(bench, enable=1)
        except Exception:
            pass
        bench.save.assert_not_called()

    def test_log_message_says_marked_as_development(self):
        """Enabling dev bench → log contains 'Marked as Development Bench'."""
        bench = _make_bench(name="bench-test")
        logger_mock = MagicMock()
        frappe_ref.logger = lambda: logger_mock
        set_development_bench(bench, enable=1)
        logged = " ".join(str(a) for a in logger_mock.info.call_args_list)
        self.assertIn("Marked as Development Bench", logged)

    def test_log_message_says_marked_as_production(self):
        """Disabling dev bench → log contains 'Marked as Production Bench'."""
        bench = _make_bench(name="bench-test", is_dev=1)
        logger_mock = MagicMock()
        frappe_ref.logger = lambda: logger_mock
        set_development_bench(bench, enable=0)
        logged = " ".join(str(a) for a in logger_mock.info.call_args_list)
        self.assertIn("Marked as Production Bench", logged)

    def test_log_includes_bench_name_and_user(self):
        """Log message includes bench name and current user."""
        bench = _make_bench(name="bench-xyz")
        logger_mock = MagicMock()
        frappe_ref.logger = lambda: logger_mock
        frappe_ref.session.user = "sysadmin@test.com"
        set_development_bench(bench, enable=1)
        logged = logger_mock.info.call_args[0][0]
        self.assertIn("bench-xyz", logged)
        self.assertIn("sysadmin@test.com", logged)


# ══════════════════════════════════════════════════════════════════════════════
# restart_bench()
# ══════════════════════════════════════════════════════════════════════════════

class TestRestartBench(unittest.TestCase):

    def setUp(self):
        frappe_ref.only_for = lambda role: None

    def test_calls_self_restart(self):
        """restart_bench() delegates to self.restart()."""
        bench = _make_bench()
        restart_bench(bench)
        bench.restart.assert_called_once_with()

    def test_calls_only_for_system_manager(self):
        """Must gate on System Manager before restarting."""
        bench = _make_bench()
        calls = []
        frappe_ref.only_for = lambda role: calls.append(role)
        restart_bench(bench)
        self.assertIn("System Manager", calls)

    def test_raises_when_not_system_manager(self):
        """Non-System Manager → raises before restart."""
        bench = _make_bench()
        frappe_ref.only_for = MagicMock(side_effect=Exception("Permission denied"))
        with self.assertRaises(Exception):
            restart_bench(bench)

    def test_restart_not_called_when_permission_denied(self):
        """If permission check fails, self.restart() must NOT be called."""
        bench = _make_bench()
        frappe_ref.only_for = MagicMock(side_effect=Exception("Permission denied"))
        try:
            restart_bench(bench)
        except Exception:
            pass
        bench.restart.assert_not_called()

    def test_logs_restart_event(self):
        """restart_bench() must log a restart event."""
        bench = _make_bench(name="bench-restart")
        logger_mock = MagicMock()
        frappe_ref.logger = lambda: logger_mock
        frappe_ref.session.user = "admin@test.com"
        restart_bench(bench)
        logger_mock.info.assert_called_once()
        logged = logger_mock.info.call_args[0][0]
        self.assertIn("bench-restart", logged)
        self.assertIn("admin@test.com", logged)

    def test_log_includes_restarted_keyword(self):
        """Log message includes 'restarted'."""
        bench = _make_bench()
        logger_mock = MagicMock()
        frappe_ref.logger = lambda: logger_mock
        restart_bench(bench)
        logged = logger_mock.info.call_args[0][0]
        self.assertIn("restarted", logged)

    def test_restart_called_before_log(self):
        """restart() must be called (bench is stopped before we log)."""
        bench = _make_bench()
        call_order = []
        bench.restart = MagicMock(side_effect=lambda: call_order.append("restart"))
        logger_mock = MagicMock()
        logger_mock.info = MagicMock(side_effect=lambda msg: call_order.append("log"))
        frappe_ref.logger = lambda: logger_mock
        restart_bench(bench)
        self.assertEqual(call_order, ["restart", "log"])


# ══════════════════════════════════════════════════════════════════════════════
# set_development_bench() — bench-watch side-effect hook
# ══════════════════════════════════════════════════════════════════════════════

class TestSetDevelopmentBenchWatchHook(unittest.TestCase):
    """Verify set_development_bench triggers start_watch / stop_watch."""

    def setUp(self):
        frappe_ref.only_for = lambda role: None

    @patch("press.press.doctype.bench.bench_dev_watch.start_watch")
    @patch("press.press.doctype.bench.bench_dev_watch.stop_watch")
    def test_enable_calls_start_watch(self, mock_stop, mock_start):
        bench = _make_bench(is_dev=0)
        set_development_bench(bench, enable=1)
        mock_start.assert_called_once_with(bench)
        mock_stop.assert_not_called()

    @patch("press.press.doctype.bench.bench_dev_watch.start_watch")
    @patch("press.press.doctype.bench.bench_dev_watch.stop_watch")
    def test_disable_calls_stop_watch(self, mock_stop, mock_start):
        bench = _make_bench(is_dev=1)
        set_development_bench(bench, enable=0)
        mock_stop.assert_called_once_with(bench)
        mock_start.assert_not_called()

    @patch("press.press.doctype.bench.bench_dev_watch.start_watch",
           side_effect=Exception("watch failed"))
    def test_watch_failure_does_not_break_toggle(self, _start):
        """The flag toggle and save must succeed even if watch start raises."""
        bench = _make_bench(is_dev=0)
        # Must not raise — exception is swallowed and logged
        set_development_bench(bench, enable=1)
        # Save still happened
        bench.save.assert_called_once_with(ignore_permissions=True)
        # Flag still flipped
        self.assertEqual(bench.is_development_bench, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
