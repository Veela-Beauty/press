"""
Unit tests for persistent scan storage (DB + Redis dual layer).

Run:
  cd /home/eslam/data/erpnext-app-repos/press_local
  python3 -m unittest press.press.doctype.bench.test_health_storage -v
"""
import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch, call

# ── Frappe stub ──────────────────────────────────────────────────────────
_frappe_stub = types.ModuleType("frappe")
_frappe_stub._ = lambda s: s
_frappe_stub.whitelist = lambda fn=None, **kw: (lambda f: f) if fn is None else fn
_frappe_stub.only_for = lambda role: None
_frappe_stub.throw = MagicMock(side_effect=Exception("Frappe throw"))
_frappe_stub.get_doc = MagicMock()
_frappe_stub.get_all = MagicMock(return_value=[])
_frappe_stub.new_doc = MagicMock()
_frappe_stub.session = MagicMock()
_frappe_stub.session.user = "admin@test.com"
_frappe_stub.db = MagicMock()
_frappe_stub.db.commit = MagicMock()
_frappe_stub.cache = MagicMock()
_frappe_stub.cache.get_value = MagicMock(return_value=None)
_frappe_stub.cache.set_value = MagicMock()
_frappe_stub.conf = MagicMock()
_frappe_stub.logger = lambda: MagicMock()
_frappe_stub.utils = MagicMock()
_frappe_stub.utils.now_datetime = MagicMock(return_value="2026-04-04 12:00:00")
sys.modules.setdefault("frappe", _frappe_stub)
sys.modules.setdefault("frappe.model", types.ModuleType("frappe.model"))
sys.modules.setdefault("frappe.model.document", types.ModuleType("frappe.model.document"))
sys.modules["frappe.model.document"].Document = type("Document", (), {})

# Import after stub
from press.press.doctype.bench import bench_code_health as _bch  # noqa: E402

PATCH = "press.press.doctype.bench.bench_code_health"
SAMPLE_DATA = {"scores": {"app": "myapp", "overall": 52}, "compliance": {"app": "myapp", "compliance_pct": 67}}


class _CleanupMixin:
    def setUp(self):
        _frappe_stub.cache = MagicMock()
        _frappe_stub.cache.get_value = MagicMock(return_value=None)
        _frappe_stub.cache.set_value = MagicMock()
        _frappe_stub.get_all = MagicMock(return_value=[])
        _frappe_stub.db = MagicMock()


class TestPersistScanExists(_CleanupMixin, unittest.TestCase):
    def test_persist_function_exists(self):
        self.assertTrue(hasattr(_bch, "_persist_scan"))
        self.assertTrue(callable(_bch._persist_scan))

    def test_load_persisted_function_exists(self):
        self.assertTrue(hasattr(_bch, "_load_persisted"))
        self.assertTrue(callable(_bch._load_persisted))


class TestPersistScan(_CleanupMixin, unittest.TestCase):
    @patch(f"{PATCH}.frappe")
    def test_creates_db_record(self, mf):
        mock_doc = MagicMock()
        mf.new_doc = MagicMock(return_value=mock_doc)
        mf.get_all = MagicMock(return_value=[])
        mf.db = MagicMock()

        _bch._persist_scan("bench-001", "myapp", "abc123", "single_app", SAMPLE_DATA)
        mf.new_doc.assert_called_with("Code Health Scan")
        mock_doc.insert.assert_called_once()

    @patch(f"{PATCH}.frappe")
    def test_sets_all_fields(self, mf):
        mock_doc = MagicMock()
        mf.new_doc = MagicMock(return_value=mock_doc)
        mf.get_all = MagicMock(return_value=[])
        mf.db = MagicMock()

        _bch._persist_scan("bench-001", "myapp", "abc123", "scores", {"overall": 50})
        self.assertEqual(mock_doc.bench, "bench-001")
        self.assertEqual(mock_doc.app_name, "myapp")
        self.assertEqual(mock_doc.commit_hash, "abc123")
        self.assertEqual(mock_doc.scan_type, "scores")
        self.assertEqual(mock_doc.status, "Success")

    @patch(f"{PATCH}.frappe")
    def test_also_writes_redis_cache(self, mf):
        mock_doc = MagicMock()
        mf.new_doc = MagicMock(return_value=mock_doc)
        mf.get_all = MagicMock(return_value=[])
        mf.cache = MagicMock()
        mf.db = MagicMock()

        _bch._persist_scan("bench-001", "myapp", "abc123", "single_app", SAMPLE_DATA)
        mf.cache.set_value.assert_called()

    @patch(f"{PATCH}.frappe")
    def test_updates_existing_record(self, mf):
        existing = MagicMock()
        existing.name = "SCAN-001"
        mf.get_all = MagicMock(return_value=[existing])
        mf.get_doc = MagicMock(return_value=existing)
        mf.db = MagicMock()
        mf.cache = MagicMock()

        _bch._persist_scan("bench-001", "myapp", "abc123", "scores", {"overall": 60})
        existing.save.assert_called_once()


class TestLoadPersisted(_CleanupMixin, unittest.TestCase):
    @patch(f"{PATCH}.frappe")
    def test_returns_redis_cache_first(self, mf):
        mf.cache.get_value = MagicMock(return_value=json.dumps(SAMPLE_DATA))
        result = _bch._load_persisted("single_app", "myapp", "abc123")
        self.assertEqual(result["scores"]["overall"], 52)
        mf.get_all.assert_not_called()

    @patch(f"{PATCH}.frappe")
    def test_falls_back_to_db(self, mf):
        mf.cache.get_value = MagicMock(return_value=None)
        db_record = MagicMock()
        db_record.result_json = json.dumps(SAMPLE_DATA)
        mf.get_all = MagicMock(return_value=[db_record])

        result = _bch._load_persisted("single_app", "myapp", "abc123")
        self.assertEqual(result["scores"]["overall"], 52)

    @patch(f"{PATCH}.frappe")
    def test_returns_none_when_no_data(self, mf):
        mf.cache.get_value = MagicMock(return_value=None)
        mf.get_all = MagicMock(return_value=[])
        result = _bch._load_persisted("single_app", "myapp", "abc123")
        self.assertIsNone(result)

    @patch(f"{PATCH}.frappe")
    def test_repopulates_redis_from_db(self, mf):
        mf.cache.get_value = MagicMock(return_value=None)
        db_record = MagicMock()
        db_record.result_json = json.dumps(SAMPLE_DATA)
        mf.get_all = MagicMock(return_value=[db_record])
        mf.cache.set_value = MagicMock()

        _bch._load_persisted("single_app", "myapp", "abc123")
        mf.cache.set_value.assert_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
