"""
Unit tests for get_health_trends() — health score history over commits.

Run:
  cd /home/eslam/data/erpnext-app-repos/press_local
  python3 -m unittest press.press.doctype.bench.test_health_trends -v
"""
import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ── Frappe stub ──────────────────────────────────────────────────────────
_frappe_stub = types.ModuleType("frappe")
_frappe_stub._ = lambda s: s
_frappe_stub.whitelist = lambda fn=None, **kw: (lambda f: f) if fn is None else fn
_frappe_stub.only_for = lambda role: None
_frappe_stub.throw = MagicMock(side_effect=Exception("Frappe throw"))
_frappe_stub.get_doc = MagicMock()
_frappe_stub.get_all = MagicMock(return_value=[])
_frappe_stub.session = MagicMock()
_frappe_stub.db = MagicMock()
_frappe_stub.cache = MagicMock()
_frappe_stub.cache.get_value = MagicMock(return_value=None)
_frappe_stub.cache.set_value = MagicMock()
_frappe_stub.conf = MagicMock()
_frappe_stub.logger = lambda: MagicMock()
_frappe_stub.utils = MagicMock()
sys.modules.setdefault("frappe", _frappe_stub)
sys.modules.setdefault("frappe.model", types.ModuleType("frappe.model"))
sys.modules.setdefault("frappe.model.document", types.ModuleType("frappe.model.document"))
sys.modules["frappe.model.document"].Document = type("Document", (), {})

import press.press.doctype.bench.bench_code_health as _bch  # noqa: E402

PATCH = "press.press.doctype.bench.bench_code_health"


class _CleanupMixin:
    def tearDown(self):
        _frappe_stub.only_for = lambda role: None
        _frappe_stub.cache = MagicMock()
        _frappe_stub.cache.get_value = MagicMock(return_value=None)
        _frappe_stub.get_all = MagicMock(return_value=[])


class TestGetHealthTrendsExists(_CleanupMixin, unittest.TestCase):
    def test_function_exists(self):
        self.assertTrue(hasattr(_bch, "get_health_trends"))
        self.assertTrue(callable(_bch.get_health_trends))


class TestGetHealthTrendsReturn(_CleanupMixin, unittest.TestCase):
    @patch(f"{PATCH}.frappe")
    def test_returns_list(self, mf):
        mf.only_for = MagicMock()
        mf.get_all = MagicMock(return_value=[])
        result = _bch.get_health_trends("bench-001", "myapp")
        self.assertIsInstance(result, list)

    @patch(f"{PATCH}.frappe")
    def test_returns_data_from_db(self, mf):
        mf.only_for = MagicMock()
        mf.get_all = MagicMock(return_value=[
            MagicMock(commit_hash="aaa111", scanned_at="2026-04-01 10:00:00",
                      result_json=json.dumps({"scores": {"overall": 52}})),
            MagicMock(commit_hash="bbb222", scanned_at="2026-04-02 10:00:00",
                      result_json=json.dumps({"scores": {"overall": 58}})),
            MagicMock(commit_hash="ccc333", scanned_at="2026-04-03 10:00:00",
                      result_json=json.dumps({"scores": {"overall": 65}})),
        ])
        result = _bch.get_health_trends("bench-001", "myapp")
        self.assertEqual(len(result), 3)

    @patch(f"{PATCH}.frappe")
    def test_each_entry_has_required_fields(self, mf):
        mf.only_for = MagicMock()
        mf.get_all = MagicMock(return_value=[
            MagicMock(commit_hash="aaa111", scanned_at="2026-04-01 10:00:00",
                      result_json=json.dumps({"scores": {"overall": 52}})),
        ])
        result = _bch.get_health_trends("bench-001", "myapp")
        entry = result[0]
        self.assertIn("commit", entry)
        self.assertIn("scanned_at", entry)
        self.assertIn("overall", entry)

    @patch(f"{PATCH}.frappe")
    def test_extracts_overall_score(self, mf):
        mf.only_for = MagicMock()
        mf.get_all = MagicMock(return_value=[
            MagicMock(commit_hash="aaa111", scanned_at="2026-04-01",
                      result_json=json.dumps({"scores": {"overall": 72}})),
        ])
        result = _bch.get_health_trends("bench-001", "myapp")
        self.assertEqual(result[0]["overall"], 72)

    @patch(f"{PATCH}.frappe")
    def test_limits_to_20_entries(self, mf):
        mf.only_for = MagicMock()
        mf.get_all = MagicMock(return_value=[])
        _bch.get_health_trends("bench-001", "myapp")
        call_kwargs = mf.get_all.call_args
        self.assertLessEqual(call_kwargs[1].get("limit", call_kwargs.kwargs.get("limit", 100)), 20)

    @patch(f"{PATCH}.frappe")
    def test_orders_by_scanned_at(self, mf):
        mf.only_for = MagicMock()
        mf.get_all = MagicMock(return_value=[])
        _bch.get_health_trends("bench-001", "myapp")
        call_kwargs = mf.get_all.call_args
        order = call_kwargs[1].get("order_by", call_kwargs.kwargs.get("order_by", ""))
        self.assertIn("scanned_at", order)

    @patch(f"{PATCH}.frappe")
    def test_handles_missing_scores_gracefully(self, mf):
        mf.only_for = MagicMock()
        mf.get_all = MagicMock(return_value=[
            MagicMock(commit_hash="aaa111", scanned_at="2026-04-01",
                      result_json=json.dumps({"no_scores": True})),
        ])
        result = _bch.get_health_trends("bench-001", "myapp")
        self.assertEqual(result[0]["overall"], 0)

    @patch(f"{PATCH}.frappe")
    def test_returns_empty_for_unknown_app(self, mf):
        mf.only_for = MagicMock()
        mf.get_all = MagicMock(return_value=[])
        result = _bch.get_health_trends("bench-001", "nonexistent")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
