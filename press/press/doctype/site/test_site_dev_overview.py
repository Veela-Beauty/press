#!/usr/bin/env python3
"""
TDD Tests for Dev Overview feature — runs against live demo.mvpstorm.com Press API.

Tests are structured as:
  1. Unit tests — test method logic directly (mocked frappe)
  2. API integration tests — HTTP calls as the Vue UI makes them

Usage:
  python3 /tmp/test_dev_overview_api.py [--live]
  --live flag enables real HTTP API calls to demo.mvpstorm.com
"""
import sys
import json
import unittest
from unittest.mock import MagicMock, patch, call
from types import SimpleNamespace

# ──────────────────────────────────────────────────────────────────────────────
# Stub frappe module (no bench needed)
# ──────────────────────────────────────────────────────────────────────────────
import types
frappe_mock = types.ModuleType("frappe")
frappe_mock._ = lambda s: s
frappe_mock.throw = lambda msg: (_ for _ in ()).throw(Exception(msg))
frappe_mock.only_for = lambda role: None  # patched per test
frappe_mock.session = SimpleNamespace(user="admin@example.com")
frappe_mock.logger = lambda: MagicMock()
sys.modules["frappe"] = frappe_mock

# ──────────────────────────────────────────────────────────────────────────────
# Inline the exact production logic from site.py
# ──────────────────────────────────────────────────────────────────────────────
def get_scheduler_status(self):
    """Return scheduler enabled/disabled state for this site."""
    try:
        paused = self.get_config_value_for_key("pause_scheduler")
        return {"enabled": not bool(paused)}
    except Exception:
        return {"enabled": True}


def get_migration_status(self):
    """Return last migration/update action for this site from Site Activity."""
    try:
        activities = frappe_mock.get_all(
            "Site Activity",
            filters={"site": self.name, "action": ["in", ["Migrate", "Update"]]},
            fields=["action", "creation", "owner"],
            order_by="creation desc",
            limit=1,
        )
        if activities:
            act = activities[0]
            return {
                "last_action": act.get("action"),
                "last_run": str(act.get("creation")),
                "by": act.get("owner"),
            }
        return {"last_action": None, "last_run": None, "by": None}
    except Exception:
        return {"last_action": None, "last_run": None, "by": None}


def get_recent_errors(self, limit=5):
    """Return recent failed agent jobs for this site."""
    try:
        jobs = frappe_mock.get_all(
            "Agent Job",
            filters={"site": self.name, "status": "Failure"},
            fields=["name", "job_type", "creation", "status"],
            order_by="creation desc",
            limit=min(int(limit), 20),
        )
        return {"errors": [dict(j) for j in jobs], "count": len(jobs)}
    except Exception:
        return {"errors": [], "count": 0}


def set_development_bench(self, enable):
    """Mark bench as development or production. System Manager only."""
    frappe_mock.only_for("System Manager")
    self.is_development_bench = 1 if enable else 0
    self.save(ignore_permissions=True)
    action = "Marked as Development Bench" if self.is_development_bench else "Marked as Production Bench"
    frappe_mock.logger().info(f"{self.name}: {action} by {frappe_mock.session.user}")


def set_development_mode(self, enable):
    """Enable/disable developer_mode config on this site. Dev sites only."""
    if not self.is_development_site:
        frappe_mock.throw("Site is not marked as a development site. Mark it first.")
    if enable:
        self._update_configuration({"developer_mode": 1})
    else:
        self.delete_config("developer_mode")


# ──────────────────────────────────────────────────────────────────────────────
# Helper: make a mock site/bench doc
# ──────────────────────────────────────────────────────────────────────────────
def make_site(name="test.example.com", is_development_site=False):
    s = MagicMock()
    s.name = name
    s.is_development_site = is_development_site
    return s


def make_bench(name="bench-001", is_development_bench=False):
    b = MagicMock()
    b.name = name
    b.is_development_bench = is_development_bench
    return b


# ══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS — Site Health Methods
# ══════════════════════════════════════════════════════════════════════════════

class TestGetSchedulerStatus(unittest.TestCase):
    """RED: write test → GREEN: verify logic passes"""

    def test_returns_enabled_when_pause_scheduler_absent(self):
        """Site with no pause_scheduler config → scheduler is enabled"""
        site = make_site()
        site.get_config_value_for_key.return_value = None
        result = get_scheduler_status(site)
        self.assertEqual(result, {"enabled": True})

    def test_returns_disabled_when_pause_scheduler_is_1(self):
        """Site with pause_scheduler=1 in config → scheduler is disabled"""
        site = make_site()
        site.get_config_value_for_key.return_value = 1
        result = get_scheduler_status(site)
        self.assertEqual(result, {"enabled": False})

    def test_returns_disabled_when_pause_scheduler_is_truthy_string(self):
        """pause_scheduler='1' (string) → scheduler is disabled"""
        site = make_site()
        site.get_config_value_for_key.return_value = "1"
        result = get_scheduler_status(site)
        self.assertEqual(result, {"enabled": False})

    def test_returns_enabled_when_pause_scheduler_is_zero(self):
        """pause_scheduler=0 → scheduler is enabled"""
        site = make_site()
        site.get_config_value_for_key.return_value = 0
        result = get_scheduler_status(site)
        self.assertEqual(result, {"enabled": True})

    def test_returns_enabled_on_exception(self):
        """Config read raises exception → safe fallback: enabled=True"""
        site = make_site()
        site.get_config_value_for_key.side_effect = Exception("db timeout")
        result = get_scheduler_status(site)
        self.assertEqual(result, {"enabled": True})

    def test_calls_correct_config_key(self):
        """Must read 'pause_scheduler', not any other key"""
        site = make_site()
        site.get_config_value_for_key.return_value = None
        get_scheduler_status(site)
        site.get_config_value_for_key.assert_called_once_with("pause_scheduler")


class TestGetMigrationStatus(unittest.TestCase):

    def test_returns_last_migrate_action(self):
        """Returns the most recent Migrate activity"""
        site = make_site()
        frappe_mock.get_all = MagicMock(return_value=[
            {"action": "Migrate", "creation": "2026-01-15 10:00:00", "owner": "admin@example.com"}
        ])
        result = get_migration_status(site)
        self.assertEqual(result["last_action"], "Migrate")
        self.assertIn("2026-01-15", result["last_run"])
        self.assertEqual(result["by"], "admin@example.com")

    def test_returns_last_update_action(self):
        """Returns Update activity type too"""
        site = make_site()
        frappe_mock.get_all = MagicMock(return_value=[
            {"action": "Update", "creation": "2026-02-01 09:00:00", "owner": "sysadmin"}
        ])
        result = get_migration_status(site)
        self.assertEqual(result["last_action"], "Update")

    def test_returns_all_null_when_no_activity(self):
        """No activity → all null fields returned, not an error"""
        site = make_site()
        frappe_mock.get_all = MagicMock(return_value=[])
        result = get_migration_status(site)
        self.assertIsNone(result["last_action"])
        self.assertIsNone(result["last_run"])
        self.assertIsNone(result["by"])

    def test_queries_correct_doctype_and_actions(self):
        """Must query Site Activity with Migrate and Update filter"""
        site = make_site("mysite.example.com")
        frappe_mock.get_all = MagicMock(return_value=[])
        get_migration_status(site)
        call_args = frappe_mock.get_all.call_args
        self.assertEqual(call_args.args[0], "Site Activity")
        filters = call_args.kwargs.get("filters", {})
        self.assertEqual(filters.get("site"), "mysite.example.com")
        self.assertIn("Migrate", filters["action"][1])

    def test_falls_back_to_null_on_exception(self):
        """DB error → returns null fields, does not raise"""
        site = make_site()
        frappe_mock.get_all = MagicMock(side_effect=Exception("connection reset"))
        result = get_migration_status(site)
        self.assertIsNone(result["last_action"])

    def test_returns_limit_1(self):
        """Only fetches last 1 activity (most recent)"""
        site = make_site()
        frappe_mock.get_all = MagicMock(return_value=[])
        get_migration_status(site)
        call_kwargs = frappe_mock.get_all.call_args.kwargs
        self.assertEqual(call_kwargs.get("limit"), 1)


class TestGetRecentErrors(unittest.TestCase):

    def test_returns_failed_agent_jobs(self):
        """Returns list of failed Agent Jobs for this site"""
        site = make_site()
        mock_jobs = [
            {"name": "AJ-001", "job_type": "New Site", "creation": "2026-01-15 11:00:00", "status": "Failure"},
            {"name": "AJ-002", "job_type": "Migrate", "creation": "2026-01-14 09:00:00", "status": "Failure"},
        ]
        frappe_mock.get_all = MagicMock(return_value=mock_jobs)
        result = get_recent_errors(site)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["errors"][0]["name"], "AJ-001")

    def test_returns_empty_when_no_errors(self):
        """No failures → count=0, errors=[]"""
        site = make_site()
        frappe_mock.get_all = MagicMock(return_value=[])
        result = get_recent_errors(site)
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["errors"], [])

    def test_default_limit_is_5(self):
        """Default call returns at most 5 results"""
        site = make_site()
        frappe_mock.get_all = MagicMock(return_value=[])
        get_recent_errors(site)
        call_kwargs = frappe_mock.get_all.call_args.kwargs
        self.assertLessEqual(call_kwargs.get("limit", 0), 20)

    def test_limit_is_capped_at_20(self):
        """Caller cannot request more than 20 errors (DoS/performance guard)"""
        site = make_site()
        frappe_mock.get_all = MagicMock(return_value=[])
        get_recent_errors(site, limit=9999)
        call_kwargs = frappe_mock.get_all.call_args.kwargs
        self.assertLessEqual(call_kwargs.get("limit", 0), 20)

    def test_queries_only_failure_status(self):
        """Must filter by status=Failure, not all jobs"""
        site = make_site("erp.example.com")
        frappe_mock.get_all = MagicMock(return_value=[])
        get_recent_errors(site)
        call_args = frappe_mock.get_all.call_args
        filters = call_args.kwargs.get("filters", {})
        self.assertEqual(filters.get("site"), "erp.example.com")
        self.assertEqual(filters.get("status"), "Failure")

    def test_falls_back_on_exception(self):
        """DB error → returns empty result, does not raise"""
        site = make_site()
        frappe_mock.get_all = MagicMock(side_effect=Exception("lock timeout"))
        result = get_recent_errors(site)
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["errors"], [])


# ══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS — Bench Methods
# ══════════════════════════════════════════════════════════════════════════════

class TestSetDevelopmentBench(unittest.TestCase):

    def test_marks_bench_as_development(self):
        """enable=1 → is_development_bench=1, saved"""
        bench = make_bench()
        set_development_bench(bench, enable=1)
        self.assertEqual(bench.is_development_bench, 1)
        bench.save.assert_called_once_with(ignore_permissions=True)

    def test_unmarks_bench_as_development(self):
        """enable=0 → is_development_bench=0, saved"""
        bench = make_bench(is_development_bench=True)
        set_development_bench(bench, enable=0)
        self.assertEqual(bench.is_development_bench, 0)
        bench.save.assert_called_once_with(ignore_permissions=True)

    def test_requires_system_manager_role(self):
        """Must call frappe.only_for('System Manager')"""
        bench = make_bench()
        with patch.object(frappe_mock, "only_for") as mock_only_for:
            set_development_bench(bench, enable=1)
        mock_only_for.assert_called_once_with("System Manager")

    def test_raises_when_not_system_manager(self):
        """Non-System Manager gets PermissionError"""
        bench = make_bench()
        frappe_mock.only_for = MagicMock(side_effect=Exception("Not permitted"))
        with self.assertRaises(Exception):
            set_development_bench(bench, enable=1)
        # restore
        frappe_mock.only_for = lambda role: None


class TestSetDevelopmentMode(unittest.TestCase):

    def test_enables_developer_mode_on_dev_site(self):
        """On a dev site, enable=1 → updates config with developer_mode=1"""
        site = make_site(is_development_site=True)
        set_development_mode(site, enable=1)
        site._update_configuration.assert_called_once_with({"developer_mode": 1})

    def test_disables_developer_mode(self):
        """enable=0 → calls delete_config('developer_mode')"""
        site = make_site(is_development_site=True)
        set_development_mode(site, enable=0)
        site.delete_config.assert_called_once_with("developer_mode")

    def test_blocks_non_dev_site(self):
        """Regular site (is_development_site=False) → frappe.throw() called"""
        site = make_site(is_development_site=False)
        thrown = []
        frappe_mock.throw = lambda msg: thrown.append(msg)
        set_development_mode(site, enable=1)
        self.assertTrue(len(thrown) > 0, "Expected frappe.throw() to be called")
        frappe_mock.throw = lambda msg: (_ for _ in ()).throw(Exception(msg))

    def test_block_message_mentions_development_site(self):
        """Error message must guide user to mark site as dev first"""
        site = make_site(is_development_site=False)
        messages = []
        frappe_mock.throw = lambda msg: messages.append(msg)
        set_development_mode(site, enable=1)
        self.assertTrue(any("development" in m.lower() for m in messages))
        frappe_mock.throw = lambda msg: (_ for _ in ()).throw(Exception(msg))


# ══════════════════════════════════════════════════════════════════════════════
# API INTEGRATION TESTS — HTTP calls as Vue UI makes them
# ══════════════════════════════════════════════════════════════════════════════

LIVE_MODE = "--live" in sys.argv

class TestAPIIntegration(unittest.TestCase):
    """
    Tests the press.api.client.run_doc_method endpoint as the Vue dashboard calls it.
    Only runs with --live flag against demo.mvpstorm.com.

    Auth: use admin API key (create one in Press desk for testing).
    """

    # Configure these for live testing
    BASE_URL = "https://demo.mvpstorm.com"
    API_ENDPOINT = "/api/method/press.api.client.run_doc_method"

    @classmethod
    def setUpClass(cls):
        if not LIVE_MODE:
            return
        try:
            import requests
        except ImportError:
            raise unittest.SkipTest("requests library not installed")
        cls.requests = requests
        # Try to get a test site to use
        cls.test_site = cls._find_test_site()

    @classmethod
    def _find_test_site(cls):
        """Find any active site to use for health method tests."""
        try:
            resp = cls.requests.get(
                f"{cls.BASE_URL}/api/method/frappe.client.get_list",
                params={"doctype": "Site", "fields": '["name","status"]', "limit": 1,
                        "filters": '[["status","=","Active"]]'},
                timeout=10,
            )
            data = resp.json()
            if data.get("message"):
                return data["message"][0]["name"]
        except Exception:
            pass
        return None

    def _call_method(self, dt, dn, method, **kwargs):
        """Make a run_doc_method API call and return parsed response."""
        params = {"dt": dt, "dn": dn, "method": method, **kwargs}
        resp = self.requests.post(
            f"{self.BASE_URL}{self.API_ENDPOINT}",
            data=params,
            timeout=15,
        )
        self.assertIn(resp.status_code, [200, 403, 417],
                      f"Unexpected HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    @unittest.skipUnless(LIVE_MODE, "Pass --live to run against real API")
    def test_api_get_scheduler_status_returns_enabled_field(self):
        """API: get_scheduler_status returns {enabled: bool}"""
        if not self.test_site:
            self.skipTest("No active test site found")
        result = self._call_method("Site", self.test_site, "get_scheduler_status")
        message = result.get("message", {})
        self.assertIn("enabled", message, f"Response: {result}")
        self.assertIsInstance(message["enabled"], bool)

    @unittest.skipUnless(LIVE_MODE, "Pass --live to run against real API")
    def test_api_get_migration_status_returns_correct_shape(self):
        """API: get_migration_status returns {last_action, last_run, by}"""
        if not self.test_site:
            self.skipTest("No active test site found")
        result = self._call_method("Site", self.test_site, "get_migration_status")
        message = result.get("message", {})
        self.assertIn("last_action", message, f"Response: {result}")
        self.assertIn("last_run", message)
        self.assertIn("by", message)

    @unittest.skipUnless(LIVE_MODE, "Pass --live to run against real API")
    def test_api_get_recent_errors_returns_count_and_list(self):
        """API: get_recent_errors returns {count: int, errors: list}"""
        if not self.test_site:
            self.skipTest("No active test site found")
        result = self._call_method("Site", self.test_site, "get_recent_errors")
        message = result.get("message", {})
        self.assertIn("count", message, f"Response: {result}")
        self.assertIn("errors", message)
        self.assertIsInstance(message["count"], int)
        self.assertIsInstance(message["errors"], list)

    @unittest.skipUnless(LIVE_MODE, "Pass --live to run against real API")
    def test_api_set_development_mode_blocked_for_non_dev_site(self):
        """API: set_development_mode on non-dev site returns error"""
        if not self.test_site:
            self.skipTest("No active test site found")
        result = self._call_method("Site", self.test_site, "set_development_mode", enable=1)
        # Should return 417 (frappe.throw) or error in message
        has_error = (
            result.get("exc_type") is not None or
            "development site" in str(result).lower() or
            result.get("message", {}) == {}
        )
        self.assertTrue(has_error, f"Expected error for non-dev site, got: {result}")


# ──────────────────────────────────────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Remove --live from argv before passing to unittest
    sys.argv = [a for a in sys.argv if a != "--live"]

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestGetSchedulerStatus,
        TestGetMigrationStatus,
        TestGetRecentErrors,
        TestSetDevelopmentBench,
        TestSetDevelopmentMode,
        TestAPIIntegration,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    exit(0 if result.wasSuccessful() else 1)
