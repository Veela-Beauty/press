"""
Unit tests for get_db_processlist() and kill_db_process() in bench_dev_overview.py

Run:
  cd /home/eslam/data/erpnext-app-repos/press_local
  python3 -m unittest press.press.doctype.bench.test_bench_dev_processlist -v
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


PROCESSLIST_OUTPUT = """\
142\t_test_site\t0\tExecute\tSELECT name FROM tabUser
289\t_test_site\t4\tSending data\tSELECT * FROM `tabSales Invoice`
301\t_test_site\t0\tSleep\t"""


class TestGetDbProcesslist(unittest.TestCase):

    @patch(PATCH)
    def test_requires_system_manager(self, mf):
        mf.only_for.side_effect = Exception("Not permitted")
        with self.assertRaises(Exception):
            _bdo.get_db_processlist("test-site")

    @patch(PATCH)
    def test_returns_list_of_processes(self, mf):
        site = _site_doc("test-site")
        bench = _bench_doc("bench-001")
        mf.get_doc.side_effect = lambda dt, name: site if dt == "Site" else bench
        bench.docker_execute.return_value = {"status": "Success", "output": PROCESSLIST_OUTPUT}
        result = _bdo.get_db_processlist("test-site")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)

    @patch(PATCH)
    def test_each_process_has_required_keys(self, mf):
        site = _site_doc("test-site")
        bench = _bench_doc("bench-001")
        mf.get_doc.side_effect = lambda dt, name: site if dt == "Site" else bench
        bench.docker_execute.return_value = {"status": "Success", "output": PROCESSLIST_OUTPUT}
        result = _bdo.get_db_processlist("test-site")
        for proc in result:
            for key in ("id", "user", "time", "state", "query"):
                self.assertIn(key, proc)

    @patch(PATCH)
    def test_time_is_integer(self, mf):
        site = _site_doc("test-site")
        bench = _bench_doc("bench-001")
        mf.get_doc.side_effect = lambda dt, name: site if dt == "Site" else bench
        bench.docker_execute.return_value = {"status": "Success", "output": PROCESSLIST_OUTPUT}
        result = _bdo.get_db_processlist("test-site")
        self.assertEqual(result[1]["time"], 4)

    @patch(PATCH)
    def test_docker_failure_returns_empty_list(self, mf):
        site = _site_doc("test-site")
        bench = _bench_doc("bench-001")
        mf.get_doc.side_effect = lambda dt, name: site if dt == "Site" else bench
        bench.docker_execute.side_effect = Exception("container down")
        result = _bdo.get_db_processlist("test-site")
        self.assertEqual(result, [])


class TestKillDbProcess(unittest.TestCase):

    @patch(PATCH)
    def test_requires_system_manager(self, mf):
        mf.only_for.side_effect = Exception("Not permitted")
        with self.assertRaises(Exception):
            _bdo.kill_db_process("test-site", 142)

    @patch(PATCH)
    def test_executes_kill_command(self, mf):
        site = _site_doc("test-site")
        bench = _bench_doc("bench-001")
        mf.get_doc.side_effect = lambda dt, name: site if dt == "Site" else bench
        bench.docker_execute.return_value = {"status": "Success", "output": ""}
        _bdo.kill_db_process("test-site", 142)
        cmd = bench.docker_execute.call_args[0][0]
        self.assertIn("KILL", cmd)
        self.assertIn("142", cmd)

    @patch(PATCH)
    def test_process_id_must_be_integer(self, mf):
        site = _site_doc("test-site")
        bench = _bench_doc("bench-001")
        mf.get_doc.side_effect = lambda dt, name: site if dt == "Site" else bench
        with self.assertRaises((ValueError, TypeError)):
            _bdo.kill_db_process("test-site", "DROP TABLE tabUser")

    @patch(PATCH)
    def test_docker_failure_returns_error(self, mf):
        site = _site_doc("test-site")
        bench = _bench_doc("bench-001")
        mf.get_doc.side_effect = lambda dt, name: site if dt == "Site" else bench
        bench.docker_execute.side_effect = Exception("timeout")
        result = _bdo.kill_db_process("test-site", 142)
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
