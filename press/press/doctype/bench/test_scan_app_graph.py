"""
Unit tests for scan_app_graph() — codegraph-based module/function dependency graph.

Run:
  cd /home/eslam/data/erpnext-app-repos/press_local
  python3 -m unittest press.press.doctype.bench.test_scan_app_graph -v
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
_frappe_stub.get_all = MagicMock()
_frappe_stub.session = MagicMock()
_frappe_stub.session.user = "admin@test.com"
_frappe_stub.db = MagicMock()
_frappe_stub.cache = MagicMock()
_frappe_stub.cache.get_value = MagicMock(return_value=None)
_frappe_stub.cache.set_value = MagicMock()
_frappe_stub.conf = MagicMock()
_frappe_stub.logger = lambda: MagicMock()
sys.modules.setdefault("frappe", _frappe_stub)

import press.press.doctype.bench.bench_code_health as _bch  # noqa: E402

PATCH = "press.press.doctype.bench.bench_code_health"

# Sample codegraph output (simulates extract from .codegraph/codegraph.db)
SAMPLE_GRAPH = {
    "nodes": [
        {"id": "accounting", "label": "accounting", "type": "module", "files": 5, "classes": 3, "functions": 20},
        {"id": "stock", "label": "stock", "type": "module", "files": 4, "classes": 2, "functions": 15},
        {"id": "accounting/PaymentEntry", "label": "PaymentEntry", "type": "class", "module": "accounting", "file": "payment_entry.py", "line": 10},
        {"id": "accounting/make_payment", "label": "make_payment", "type": "function", "module": "accounting", "file": "payment_entry.py", "line": 50},
    ],
    "edges": [
        {"source": "accounting", "target": "stock", "weight": 5, "layer": "import"},
        {"source": "accounting/PaymentEntry", "target": "stock/StockEntry", "weight": 2, "layer": "call"},
    ],
}


def _bench_doc(name="bench-001"):
    doc = MagicMock()
    doc.name = name
    doc.docker_execute.return_value = {"output": "", "status": "Success"}
    return doc


class _CleanupMixin:
    def tearDown(self):
        _frappe_stub.only_for = lambda role: None
        _frappe_stub.throw = MagicMock(side_effect=Exception("Frappe throw"))
        _frappe_stub.cache = MagicMock()
        _frappe_stub.cache.get_value = MagicMock(return_value=None)
        _frappe_stub.cache.set_value = MagicMock()


class TestScanAppGraphExists(_CleanupMixin, unittest.TestCase):
    def test_function_exists(self):
        self.assertTrue(hasattr(_bch, "scan_app_graph"))
        self.assertTrue(callable(_bch.scan_app_graph))


class TestScanAppGraphParams(_CleanupMixin, unittest.TestCase):
    @patch(f"{PATCH}.frappe")
    def test_rejects_empty_app_name(self, mf):
        mf.only_for = MagicMock()
        mf.throw = MagicMock(side_effect=Exception("throw"))
        mf.get_doc = MagicMock(return_value=_bench_doc())
        with self.assertRaises(Exception):
            _bch.scan_app_graph("bench-001", "")

    @patch(f"{PATCH}.frappe")
    def test_rejects_unsafe_app_name(self, mf):
        mf.only_for = MagicMock()
        mf.throw = MagicMock(side_effect=Exception("throw"))
        mf.get_doc = MagicMock(return_value=_bench_doc())
        with self.assertRaises(Exception):
            _bch.scan_app_graph("bench-001", "foo; rm -rf /")


class TestScanAppGraphReturnStructure(_CleanupMixin, unittest.TestCase):
    @patch(f"press.press.doctype.bench.health_graph.extract_codegraph", return_value=SAMPLE_GRAPH)
    @patch(f"{PATCH}._get_app_commits", return_value={"myapp": "abc123"})
    @patch(f"{PATCH}.frappe")
    def test_returns_nodes_key(self, mf, mock_commits, mock_extract):
        mf.only_for = MagicMock()
        mf.get_doc = MagicMock(return_value=_bench_doc())
        mf.cache.get_value = MagicMock(return_value=None)
        mf.cache.set_value = MagicMock()

        result = _bch.scan_app_graph("bench-001", "myapp")
        self.assertIn("nodes", result)
        self.assertIsInstance(result["nodes"], list)

    @patch(f"press.press.doctype.bench.health_graph.extract_codegraph", return_value=SAMPLE_GRAPH)
    @patch(f"{PATCH}._get_app_commits", return_value={"myapp": "abc123"})
    @patch(f"{PATCH}.frappe")
    def test_returns_edges_key(self, mf, mock_commits, mock_extract):
        mf.only_for = MagicMock()
        mf.get_doc = MagicMock(return_value=_bench_doc())
        mf.cache.get_value = MagicMock(return_value=None)
        mf.cache.set_value = MagicMock()

        result = _bch.scan_app_graph("bench-001", "myapp")
        self.assertIn("edges", result)
        self.assertIsInstance(result["edges"], list)

    @patch(f"press.press.doctype.bench.health_graph.extract_codegraph", return_value=SAMPLE_GRAPH)
    @patch(f"{PATCH}._get_app_commits", return_value={"myapp": "abc123"})
    @patch(f"{PATCH}.frappe")
    def test_nodes_have_required_fields(self, mf, mock_commits, mock_extract):
        mf.only_for = MagicMock()
        mf.get_doc = MagicMock(return_value=_bench_doc())
        mf.cache.get_value = MagicMock(return_value=None)
        mf.cache.set_value = MagicMock()

        result = _bch.scan_app_graph("bench-001", "myapp")
        for node in result["nodes"]:
            self.assertIn("id", node)
            self.assertIn("type", node)
            self.assertIn(node["type"], ("module", "class", "function"))

    @patch(f"press.press.doctype.bench.health_graph.extract_codegraph", return_value=SAMPLE_GRAPH)
    @patch(f"{PATCH}._get_app_commits", return_value={"myapp": "abc123"})
    @patch(f"{PATCH}.frappe")
    def test_edges_have_required_fields(self, mf, mock_commits, mock_extract):
        mf.only_for = MagicMock()
        mf.get_doc = MagicMock(return_value=_bench_doc())
        mf.cache.get_value = MagicMock(return_value=None)
        mf.cache.set_value = MagicMock()

        result = _bch.scan_app_graph("bench-001", "myapp")
        for edge in result["edges"]:
            self.assertIn("source", edge)
            self.assertIn("target", edge)
            self.assertIn("weight", edge)


class TestScanAppGraphCaching(_CleanupMixin, unittest.TestCase):
    @patch(f"press.press.doctype.bench.health_graph.extract_codegraph", return_value=SAMPLE_GRAPH)
    @patch(f"{PATCH}._get_app_commits", return_value={"myapp": "abc123"})
    @patch(f"{PATCH}.frappe")
    def test_caches_result(self, mf, mock_commits, mock_extract):
        mf.only_for = MagicMock()
        mf.get_doc = MagicMock(return_value=_bench_doc())
        mf.cache.get_value = MagicMock(return_value=None)
        mf.cache.set_value = MagicMock()

        _bch.scan_app_graph("bench-001", "myapp")
        mf.cache.set_value.assert_called()

    @patch(f"{PATCH}._get_app_commits", return_value={"myapp": "abc123"})
    @patch(f"{PATCH}.frappe")
    def test_returns_cached_without_extraction(self, mf, mock_commits):
        cached = json.dumps(SAMPLE_GRAPH)
        mf.only_for = MagicMock()
        mf.get_doc = MagicMock(return_value=_bench_doc())
        mf.cache.get_value = MagicMock(return_value=cached)

        with patch(f"press.press.doctype.bench.health_graph.extract_codegraph") as mock_extract:
            result = _bch.scan_app_graph("bench-001", "myapp")
            mock_extract.assert_not_called()

        self.assertEqual(len(result["nodes"]), 4)
        self.assertEqual(len(result["edges"]), 2)


class TestScanAppGraphFallback(_CleanupMixin, unittest.TestCase):
    """When codegraph is not installed, fall back to AST-based extraction."""

    @patch(f"press.press.doctype.bench.health_graph.extract_codegraph", side_effect=Exception("codegraph not found"))
    @patch(f"press.press.doctype.bench.health_graph.extract_ast_graph", return_value=SAMPLE_GRAPH)
    @patch(f"{PATCH}._get_app_commits", return_value={"myapp": "abc123"})
    @patch(f"{PATCH}.frappe")
    def test_falls_back_to_ast(self, mf, mock_commits, mock_ast, mock_cg):
        mf.only_for = MagicMock()
        mf.get_doc = MagicMock(return_value=_bench_doc())
        mf.cache.get_value = MagicMock(return_value=None)
        mf.cache.set_value = MagicMock()

        result = _bch.scan_app_graph("bench-001", "myapp")
        mock_ast.assert_called_once()
        self.assertIn("nodes", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
