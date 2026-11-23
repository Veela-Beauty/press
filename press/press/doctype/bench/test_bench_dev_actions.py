"""
Unit tests for get_bench_app_names(), push_app_to_github() (a shim) and restart_bench_for_site()
in dev_overview/panel.py

Run:
  cd /home/eslam/data/erpnext-app-repos/press_local
  python3 -m unittest press.press.doctype.bench.test_bench_dev_actions -v
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ─── Install frappe stub BEFORE importing bench_dev_overview ──────────────────
_frappe_stub = types.ModuleType("frappe")
_frappe_stub._ = lambda s: s
_frappe_stub.whitelist = lambda fn=None, **kw: (lambda f: f) if fn is None else fn
_frappe_stub.only_for = lambda role: None
_frappe_stub.get_all = MagicMock()
_frappe_stub.get_doc = MagicMock()
_frappe_stub.session = MagicMock()
_frappe_stub.session.user = "admin@test.com"
_frappe_stub.db = MagicMock()
_frappe_stub.logger = lambda: MagicMock()
sys.modules.setdefault("frappe", _frappe_stub)

import press.press.doctype.bench.dev_overview.panel as _bdo  # noqa: E402


class TestGetBenchAppNames(unittest.TestCase):
    """Tests for get_bench_app_names() in bench_dev_overview.py"""

    def setUp(self):
        self.mf = MagicMock()
        _bdo.frappe = self.mf

    def tearDown(self):
        _bdo.frappe = _frappe_stub

    def test_requires_team_access(self):
        with (
            patch.object(_bdo, "ensure_team_access", side_effect=PermissionError("Not allowed")) as guard,
            self.assertRaises(PermissionError),
        ):
            _bdo.get_bench_app_names("bench-0001")
        guard.assert_called_once_with(bench_name="bench-0001")
        self.mf.get_all.assert_not_called()

    def test_queries_bench_app_doctype(self):
        """Must query 'Bench App' filtered by the given bench name."""
        self.mf.get_all.return_value = []
        _bdo.get_bench_app_names("bench-0001")
        args, kwargs = self.mf.get_all.call_args
        self.assertEqual(args[0], "Bench App")
        filters = kwargs.get("filters") or {}
        self.assertEqual(filters.get("parent"), "bench-0001")

    def test_returns_list_of_app_name_strings(self):
        """Must return a plain list of app name strings."""
        row1 = MagicMock(); row1.app = "frappe"
        row2 = MagicMock(); row2.app = "erpnext"
        self.mf.get_all.return_value = [row1, row2]
        result = _bdo.get_bench_app_names("bench-0001")
        self.assertEqual(result, ["frappe", "erpnext"])

    def test_returns_empty_list_when_no_apps(self):
        """Must return [] when the bench has no apps."""
        self.mf.get_all.return_value = []
        result = _bdo.get_bench_app_names("bench-0001")
        self.assertEqual(result, [])

    def test_result_is_json_serializable(self):
        """Return value must be a plain list (not frappe._dict) for JSON."""
        import json
        row = MagicMock(); row.app = "press"
        self.mf.get_all.return_value = [row]
        result = _bdo.get_bench_app_names("bench-0001")
        self.assertEqual(json.dumps(result), '["press"]')


class TestPushAppToGithub(unittest.TestCase):
    """push_app_to_github() here is a shim; the code is bench_app_push.py, tested in test_bench_app_push.py."""

    def test_hands_every_argument_to_bench_app_push(self):
        target = "press.press.doctype.bench.bench_app_push.push_app_to_github"
        with patch(target, return_value={"step": "done"}) as impl:
            result = _bdo.push_app_to_github("bench-0001", "myapp", "WIP", branch_name="feat/x")
        impl.assert_called_once_with("bench-0001", "myapp", "WIP", branch_name="feat/x")
        self.assertEqual(result, {"step": "done"})


class TestRestartBenchForSite(unittest.TestCase):
    """Tests for restart_bench_for_site() in bench_dev_overview.py"""

    def setUp(self):
        self.mf = MagicMock()
        _bdo.frappe = self.mf

    def tearDown(self):
        _bdo.frappe = _frappe_stub

    def test_requires_team_access(self):
        with (
            patch.object(_bdo, "ensure_team_access", side_effect=PermissionError("Not allowed")) as guard,
            self.assertRaises(PermissionError),
        ):
            _bdo.restart_bench_for_site("bench-001")
        guard.assert_called_once_with(bench_name="bench-001")
        self.mf.get_doc.assert_not_called()

    def test_fetches_bench_by_name(self):
        bench = MagicMock()
        self.mf.get_doc.return_value = bench
        _bdo.restart_bench_for_site("bench-001")
        self.mf.get_doc.assert_called_with("Bench", "bench-001")

    def test_calls_restart_bench(self):
        bench = MagicMock()
        self.mf.get_doc.return_value = bench
        _bdo.restart_bench_for_site("bench-001")
        bench.restart_bench.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
