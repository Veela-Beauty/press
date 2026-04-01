"""
Unit tests for get_recent_logs() in bench_dev_overview.py

Run:
  cd /home/eslam/data/erpnext-app-repos/press_local
  python3 -m unittest press.press.doctype.bench.test_bench_dev_logs -v
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


def _bench_doc(name):
    doc = MagicMock()
    doc.name = name
    return doc


def _docker_result(output, returncode=0):
    return {"status": "Success", "output": output, "returncode": returncode}


SAMPLE_LOG_OUTPUT = """2026-04-01 10:30:15,123 ERROR frappe.log: pymysql.err.OperationalError
2026-04-01 10:29:00,456 INFO worker.log: Job completed in 2.34s
2026-04-01 10:28:30,789 INFO scheduler.log: Scheduler tick: 14 tasks
"""


class TestGetRecentLogs(unittest.TestCase):

    @patch(PATCH)
    def test_requires_system_manager(self, mf):
        mf.only_for.side_effect = Exception("Not permitted")
        with self.assertRaises(Exception):
            _bdo.get_recent_logs("bench-001")

    @patch(PATCH)
    def test_returns_list_of_log_entries(self, mf):
        bench = _bench_doc("bench-001")
        mf.get_doc.return_value = bench
        bench.docker_execute.return_value = _docker_result(SAMPLE_LOG_OUTPUT)
        result = _bdo.get_recent_logs("bench-001")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    @patch(PATCH)
    def test_each_entry_has_required_keys(self, mf):
        bench = _bench_doc("bench-001")
        mf.get_doc.return_value = bench
        bench.docker_execute.return_value = _docker_result(SAMPLE_LOG_OUTPUT)
        result = _bdo.get_recent_logs("bench-001")
        for entry in result:
            for key in ("timestamp", "level", "source", "message"):
                self.assertIn(key, entry)

    @patch(PATCH)
    def test_parses_log_level(self, mf):
        bench = _bench_doc("bench-001")
        mf.get_doc.return_value = bench
        bench.docker_execute.return_value = _docker_result(SAMPLE_LOG_OUTPUT)
        result = _bdo.get_recent_logs("bench-001")
        levels = [e["level"] for e in result]
        self.assertIn("ERROR", levels)
        self.assertIn("INFO", levels)

    @patch(PATCH)
    def test_log_type_filter(self, mf):
        bench = _bench_doc("bench-001")
        mf.get_doc.return_value = bench
        bench.docker_execute.return_value = _docker_result(SAMPLE_LOG_OUTPUT)
        result = _bdo.get_recent_logs("bench-001", log_type="error")
        for entry in result:
            self.assertEqual(entry["level"], "ERROR")

    @patch(PATCH)
    def test_docker_failure_returns_empty_list(self, mf):
        bench = _bench_doc("bench-001")
        mf.get_doc.return_value = bench
        bench.docker_execute.side_effect = Exception("container down")
        result = _bdo.get_recent_logs("bench-001")
        self.assertEqual(result, [])

    @patch(PATCH)
    def test_empty_output_returns_empty_list(self, mf):
        bench = _bench_doc("bench-001")
        mf.get_doc.return_value = bench
        bench.docker_execute.return_value = _docker_result("")
        result = _bdo.get_recent_logs("bench-001")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
