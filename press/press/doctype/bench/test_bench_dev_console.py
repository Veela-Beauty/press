"""
Unit tests for run_sql_on_site() and run_python_on_site() in bench_dev_overview.py

Run:
  cd /home/eslam/data/erpnext-app-repos/press_local
  python3 -m unittest press.press.doctype.bench.test_bench_dev_console -v
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

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

PATCH = "press.press.doctype.bench.bench_dev_overview.frappe"


def _site_doc(name, bench_name="bench-001"):
    doc = MagicMock()
    doc.name = name
    doc.bench = bench_name
    return doc


def _bench_doc(name):
    doc = MagicMock()
    doc.name = name
    return doc


def _docker_result(output, returncode=0):
    return {"status": "Success", "output": output, "returncode": returncode}


class TestRunSqlOnSite(unittest.TestCase):

    @patch(PATCH)
    def test_requires_system_manager(self, mf):
        mf.only_for.side_effect = Exception("Not permitted")
        with self.assertRaises(Exception):
            _bdo.run_sql_on_site("test-site", "SELECT 1")

    @patch(PATCH)
    def test_returns_output_string(self, mf):
        site = _site_doc("test-site")
        bench = _bench_doc("bench-001")
        mf.get_doc.side_effect = lambda dt, name: site if dt == "Site" else bench
        bench.docker_execute.return_value = _docker_result("name\nAdministrator\n")
        result = _bdo.run_sql_on_site("test-site", "SELECT name FROM tabUser")
        self.assertEqual(result["output"], "name\nAdministrator\n")

    @patch(PATCH)
    def test_passes_site_name_to_mysql_command(self, mf):
        site = _site_doc("test-site")
        bench = _bench_doc("bench-001")
        mf.get_doc.side_effect = lambda dt, name: site if dt == "Site" else bench
        bench.docker_execute.return_value = _docker_result("")
        _bdo.run_sql_on_site("test-site", "SELECT 1")
        cmd = bench.docker_execute.call_args[0][0]
        self.assertIn("test-site", cmd)

    @patch(PATCH)
    def test_rejects_write_query_without_commit_flag(self, mf):
        site = _site_doc("test-site")
        bench = _bench_doc("bench-001")
        mf.get_doc.side_effect = lambda dt, name: site if dt == "Site" else bench
        result = _bdo.run_sql_on_site("test-site", "DELETE FROM tabUser", commit=False)
        self.assertIn("error", result)

    @patch(PATCH)
    def test_allows_write_query_with_commit_flag(self, mf):
        site = _site_doc("test-site")
        bench = _bench_doc("bench-001")
        mf.get_doc.side_effect = lambda dt, name: site if dt == "Site" else bench
        bench.docker_execute.return_value = _docker_result("Query OK")
        result = _bdo.run_sql_on_site("test-site", "UPDATE tabUser SET enabled=1", commit=True)
        self.assertNotIn("error", result)

    @patch(PATCH)
    def test_docker_failure_returns_error(self, mf):
        site = _site_doc("test-site")
        bench = _bench_doc("bench-001")
        mf.get_doc.side_effect = lambda dt, name: site if dt == "Site" else bench
        bench.docker_execute.side_effect = Exception("container down")
        result = _bdo.run_sql_on_site("test-site", "SELECT 1")
        self.assertIn("error", result)


class TestRunPythonOnSite(unittest.TestCase):

    @patch(PATCH)
    def test_requires_system_manager(self, mf):
        mf.only_for.side_effect = Exception("Not permitted")
        with self.assertRaises(Exception):
            _bdo.run_python_on_site("test-site", "print(1)")

    @patch(PATCH)
    def test_returns_output(self, mf):
        site = _site_doc("test-site")
        bench = _bench_doc("bench-001")
        mf.get_doc.side_effect = lambda dt, name: site if dt == "Site" else bench
        bench.docker_execute.return_value = _docker_result("hello world\n")
        result = _bdo.run_python_on_site("test-site", "print('hello world')")
        self.assertEqual(result["output"], "hello world\n")

    @patch(PATCH)
    def test_uses_bench_console_command(self, mf):
        site = _site_doc("test-site")
        bench = _bench_doc("bench-001")
        mf.get_doc.side_effect = lambda dt, name: site if dt == "Site" else bench
        bench.docker_execute.return_value = _docker_result("")
        _bdo.run_python_on_site("test-site", "print(1)")
        cmd = bench.docker_execute.call_args[0][0]
        self.assertIn("bench", cmd)
        self.assertIn("test-site", cmd)

    @patch(PATCH)
    def test_docker_failure_returns_error(self, mf):
        site = _site_doc("test-site")
        bench = _bench_doc("bench-001")
        mf.get_doc.side_effect = lambda dt, name: site if dt == "Site" else bench
        bench.docker_execute.side_effect = Exception("timeout")
        result = _bdo.run_python_on_site("test-site", "print(1)")
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
