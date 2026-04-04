"""
Unit tests for scan_single_app() — per-app incremental scan.
Scans one app at a time, returns scores + compliance, cached by commit.

Run:
  cd /home/eslam/data/erpnext-app-repos/press_local
  python3 -m unittest press.press.doctype.bench.test_scan_single_app -v
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
SCORE_PATCH = "press.press.doctype.bench.health_scoring"


def _bench_doc(name="bench-001"):
    doc = MagicMock()
    doc.name = name
    doc.docker_execute.return_value = {"output": "", "status": "Success"}
    return doc


def _mock_exec_output(output):
    return {"output": output, "status": "Success"}


class TestScanSingleAppExists(unittest.TestCase):
    """The API function must exist and be callable."""

    def test_function_exists(self):
        self.assertTrue(hasattr(_bch, "scan_single_app"))
        self.assertTrue(callable(_bch.scan_single_app))


class TestScanSingleAppParams(unittest.TestCase):
    """Input validation."""

    @patch(f"{PATCH}.frappe")
    def test_rejects_empty_app_name(self, mf):
        mf.only_for = MagicMock()
        mf.throw = MagicMock(side_effect=Exception("throw"))
        mf.get_doc = MagicMock(return_value=_bench_doc())
        with self.assertRaises(Exception):
            _bch.scan_single_app("bench-001", "")

    @patch(f"{PATCH}.frappe")
    def test_rejects_unsafe_app_name(self, mf):
        mf.only_for = MagicMock()
        mf.throw = MagicMock(side_effect=Exception("throw"))
        mf.get_doc = MagicMock(return_value=_bench_doc())
        with self.assertRaises(Exception):
            _bch.scan_single_app("bench-001", "foo; rm -rf /")


class TestScanSingleAppReturnStructure(unittest.TestCase):
    """Return value must have scores + compliance keys."""

    @patch(f"{SCORE_PATCH}.score_claude", return_value=80)
    @patch(f"{SCORE_PATCH}.score_readme", return_value=70)
    @patch(f"{SCORE_PATCH}.score_docs", return_value=60)
    @patch(f"{SCORE_PATCH}.score_tests", return_value=50)
    @patch(f"{SCORE_PATCH}.score_clean", return_value=90)
    @patch(f"{SCORE_PATCH}.score_patterns", return_value=85)
    @patch(f"{SCORE_PATCH}.score_lessons", return_value=100)
    @patch(f"{SCORE_PATCH}.score_security", return_value=75)
    @patch(f"{PATCH}._get_app_commits", return_value={"myapp": "abc123"})
    @patch(f"{PATCH}._exec")
    @patch(f"{PATCH}.frappe")
    def test_returns_scores_dict(self, mf, mock_exec, mock_commits, *score_mocks):
        mf.only_for = MagicMock()
        mf.get_doc = MagicMock(return_value=_bench_doc())
        mf.cache.get_value = MagicMock(return_value=None)
        mf.cache.set_value = MagicMock()
        mock_exec.return_value = _mock_exec_output("PASS")

        result = _bch.scan_single_app("bench-001", "myapp")

        self.assertIn("scores", result)
        scores = result["scores"]
        self.assertIn("claude_md", scores)
        self.assertIn("readme", scores)
        self.assertIn("documentation", scores)
        self.assertIn("tests", scores)
        self.assertIn("clean_code", scores)
        self.assertIn("code_patterns", scores)
        self.assertIn("lessons", scores)
        self.assertIn("security", scores)
        self.assertIn("overall", scores)

    @patch(f"{SCORE_PATCH}.score_claude", return_value=80)
    @patch(f"{SCORE_PATCH}.score_readme", return_value=70)
    @patch(f"{SCORE_PATCH}.score_docs", return_value=60)
    @patch(f"{SCORE_PATCH}.score_tests", return_value=50)
    @patch(f"{SCORE_PATCH}.score_clean", return_value=90)
    @patch(f"{SCORE_PATCH}.score_patterns", return_value=85)
    @patch(f"{SCORE_PATCH}.score_lessons", return_value=100)
    @patch(f"{SCORE_PATCH}.score_security", return_value=75)
    @patch(f"{PATCH}._get_app_commits", return_value={"myapp": "abc123"})
    @patch(f"{PATCH}._exec")
    @patch(f"{PATCH}.frappe")
    def test_returns_compliance_dict(self, mf, mock_exec, mock_commits, *score_mocks):
        mf.only_for = MagicMock()
        mf.get_doc = MagicMock(return_value=_bench_doc())
        mf.cache.get_value = MagicMock(return_value=None)
        mf.cache.set_value = MagicMock()
        mock_exec.return_value = _mock_exec_output("PASS")

        result = _bch.scan_single_app("bench-001", "myapp")

        self.assertIn("compliance", result)
        comp = result["compliance"]
        self.assertIn("checks", comp)
        self.assertIn("compliance_pct", comp)
        self.assertIn("app", comp)

    @patch(f"{SCORE_PATCH}.score_claude", return_value=80)
    @patch(f"{SCORE_PATCH}.score_readme", return_value=70)
    @patch(f"{SCORE_PATCH}.score_docs", return_value=60)
    @patch(f"{SCORE_PATCH}.score_tests", return_value=50)
    @patch(f"{SCORE_PATCH}.score_clean", return_value=90)
    @patch(f"{SCORE_PATCH}.score_patterns", return_value=85)
    @patch(f"{SCORE_PATCH}.score_lessons", return_value=100)
    @patch(f"{SCORE_PATCH}.score_security", return_value=75)
    @patch(f"{PATCH}._get_app_commits", return_value={"myapp": "abc123"})
    @patch(f"{PATCH}._exec")
    @patch(f"{PATCH}.frappe")
    def test_overall_score_is_average(self, mf, mock_exec, mock_commits, *score_mocks):
        mf.only_for = MagicMock()
        mf.get_doc = MagicMock(return_value=_bench_doc())
        mf.cache.get_value = MagicMock(return_value=None)
        mf.cache.set_value = MagicMock()
        mock_exec.return_value = _mock_exec_output("PASS")

        result = _bch.scan_single_app("bench-001", "myapp")
        scores = result["scores"]
        expected = round((80 + 70 + 60 + 50 + 90 + 85 + 100 + 75) / 8)
        self.assertEqual(scores["overall"], expected)

    @patch(f"{SCORE_PATCH}.score_claude", return_value=80)
    @patch(f"{SCORE_PATCH}.score_readme", return_value=70)
    @patch(f"{SCORE_PATCH}.score_docs", return_value=60)
    @patch(f"{SCORE_PATCH}.score_tests", return_value=50)
    @patch(f"{SCORE_PATCH}.score_clean", return_value=90)
    @patch(f"{SCORE_PATCH}.score_patterns", return_value=85)
    @patch(f"{SCORE_PATCH}.score_lessons", return_value=100)
    @patch(f"{SCORE_PATCH}.score_security", return_value=75)
    @patch(f"{PATCH}._get_app_commits", return_value={"myapp": "abc123"})
    @patch(f"{PATCH}._exec")
    @patch(f"{PATCH}.frappe")
    def test_returns_app_name(self, mf, mock_exec, mock_commits, *score_mocks):
        mf.only_for = MagicMock()
        mf.get_doc = MagicMock(return_value=_bench_doc())
        mf.cache.get_value = MagicMock(return_value=None)
        mf.cache.set_value = MagicMock()
        mock_exec.return_value = _mock_exec_output("PASS")

        result = _bch.scan_single_app("bench-001", "myapp")
        self.assertEqual(result["scores"]["app"], "myapp")
        self.assertEqual(result["compliance"]["app"], "myapp")


class TestScanSingleAppCaching(unittest.TestCase):
    """Results cached by (app, commit_hash)."""

    @patch(f"{SCORE_PATCH}.score_claude", return_value=80)
    @patch(f"{SCORE_PATCH}.score_readme", return_value=70)
    @patch(f"{SCORE_PATCH}.score_docs", return_value=60)
    @patch(f"{SCORE_PATCH}.score_tests", return_value=50)
    @patch(f"{SCORE_PATCH}.score_clean", return_value=90)
    @patch(f"{SCORE_PATCH}.score_patterns", return_value=85)
    @patch(f"{SCORE_PATCH}.score_lessons", return_value=100)
    @patch(f"{SCORE_PATCH}.score_security", return_value=75)
    @patch(f"{PATCH}._get_app_commits", return_value={"myapp": "abc123"})
    @patch(f"{PATCH}._exec")
    @patch(f"{PATCH}.frappe")
    def test_caches_result_on_success(self, mf, mock_exec, mock_commits, *score_mocks):
        mf.only_for = MagicMock()
        mf.get_doc = MagicMock(return_value=_bench_doc())
        mf.cache.get_value = MagicMock(return_value=None)
        mf.cache.set_value = MagicMock()
        mock_exec.return_value = _mock_exec_output("PASS")

        _bch.scan_single_app("bench-001", "myapp")
        mf.cache.set_value.assert_called()

    @patch(f"{PATCH}._get_app_commits", return_value={"myapp": "abc123"})
    @patch(f"{PATCH}.frappe")
    def test_returns_cached_without_scoring(self, mf, mock_commits):
        cached_data = json.dumps({
            "scores": {"app": "myapp", "claude_md": 80, "overall": 76},
            "compliance": {"app": "myapp", "compliance_pct": 67, "checks": []},
        })
        mf.only_for = MagicMock()
        mf.get_doc = MagicMock(return_value=_bench_doc())
        mf.cache.get_value = MagicMock(return_value=cached_data)

        with patch(f"{SCORE_PATCH}.score_claude") as mock_score:
            result = _bch.scan_single_app("bench-001", "myapp")
            mock_score.assert_not_called()

        self.assertEqual(result["scores"]["overall"], 76)


if __name__ == "__main__":
    unittest.main(verbosity=2)
