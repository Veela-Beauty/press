"""
Unit tests for get_bench_app_names() and push_app_to_github()
in bench_dev_overview.py

Run:
  cd /home/eslam/data/erpnext-app-repos/press_local
  python3 -m unittest press.press.doctype.bench.test_bench_dev_actions -v
"""
import sys
import types
import unittest
from unittest.mock import MagicMock

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

import press.press.doctype.bench.bench_dev_overview as _bdo  # noqa: E402


class TestGetBenchAppNames(unittest.TestCase):
    """Tests for get_bench_app_names() in bench_dev_overview.py"""

    def setUp(self):
        self.mf = MagicMock()
        _bdo.frappe = self.mf

    def tearDown(self):
        _bdo.frappe = _frappe_stub

    def test_requires_system_manager(self):
        """Must call frappe.only_for('System Manager')."""
        self.mf.get_all.return_value = []
        _bdo.get_bench_app_names("bench-0001")
        self.mf.only_for.assert_called_once_with("System Manager")

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
    """Tests for push_app_to_github() in bench_dev_overview.py"""

    def setUp(self):
        self.mf = MagicMock()
        _bdo.frappe = self.mf
        self.mf.session.user = "admin@example.com"

    def tearDown(self):
        _bdo.frappe = _frappe_stub

    def _make_bench(self):
        bench = MagicMock()
        bench.name = "bench-0001"
        bench.status = "Active"
        bench.docker_execute.return_value = {
            "status": "Success",
            "output": "Everything up-to-date",
            "returncode": 0,
        }
        return bench

    def test_requires_system_manager(self):
        self.mf.get_doc.return_value = self._make_bench()
        _bdo.push_app_to_github("bench-0001", "frappe", "WIP")
        self.mf.only_for.assert_called_once_with("System Manager")

    def test_fetches_bench_by_name(self):
        self.mf.get_doc.return_value = self._make_bench()
        _bdo.push_app_to_github("bench-0001", "frappe", "WIP")
        self.mf.get_doc.assert_called_with("Bench", "bench-0001")

    def test_calls_docker_execute(self):
        bench = self._make_bench()
        self.mf.get_doc.return_value = bench
        _bdo.push_app_to_github("bench-0001", "frappe", "WIP")
        bench.docker_execute.assert_called_once()

    def test_git_add_in_command(self):
        bench = self._make_bench()
        self.mf.get_doc.return_value = bench
        _bdo.push_app_to_github("bench-0001", "frappe", "WIP")
        self.assertIn("git add -A", bench.docker_execute.call_args[0][0])

    def test_git_commit_in_command(self):
        bench = self._make_bench()
        self.mf.get_doc.return_value = bench
        _bdo.push_app_to_github("bench-0001", "frappe", "WIP")
        self.assertIn("git commit", bench.docker_execute.call_args[0][0])

    def test_git_push_in_command(self):
        bench = self._make_bench()
        self.mf.get_doc.return_value = bench
        _bdo.push_app_to_github("bench-0001", "frappe", "WIP")
        self.assertIn("git push", bench.docker_execute.call_args[0][0])

    def test_message_in_commit_command(self):
        bench = self._make_bench()
        self.mf.get_doc.return_value = bench
        _bdo.push_app_to_github("bench-0001", "frappe", "my feature")
        self.assertIn("my feature", bench.docker_execute.call_args[0][0])

    def test_subdir_is_apps_slash_app(self):
        bench = self._make_bench()
        self.mf.get_doc.return_value = bench
        _bdo.push_app_to_github("bench-0001", "erpnext", "fix")
        self.assertEqual(bench.docker_execute.call_args[1].get("subdir"), "apps/erpnext")

    def test_returns_execute_result(self):
        bench = self._make_bench()
        self.mf.get_doc.return_value = bench
        result = _bdo.push_app_to_github("bench-0001", "frappe", "WIP")
        self.assertEqual(result["status"], "Success")
        self.assertEqual(result["returncode"], 0)

    def test_single_quote_in_message_escaped(self):
        bench = self._make_bench()
        self.mf.get_doc.return_value = bench
        _bdo.push_app_to_github("bench-0001", "frappe", "it's done")
        cmd = bench.docker_execute.call_args[0][0]
        self.assertNotIn("'it's done'", cmd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
