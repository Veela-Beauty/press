"""
Unit tests for get_dev_panel_data() in bench_dev_overview.py

Run:
  cd /home/eslam/data/erpnext-app-repos/press_local
  python3 -m unittest press.press.doctype.bench.test_bench_dev_panel -v
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

import press.press.doctype.bench.bench_dev_overview as _bdo  # noqa: E402


class _FDict(dict):
    def __getattr__(self, k):
        try: return self[k]
        except KeyError: raise AttributeError(k)
    def __setattr__(self, k, v): self[k] = v


def _site_row(name, bench, status="Active", is_dev=0):
    return _FDict(name=name, bench=bench, status=status,
                  host_name=name + ".example.com", is_development_site=is_dev)

def _bench_doc(name, group="rg-001", apps=None):
    doc = MagicMock(); doc.name = name; doc.group = group
    doc.apps = apps or []
    return doc

def _release(hash_, message="fix: x", author="dev", timestamp="2026-01-01 10:00:00"):
    r = MagicMock(); r.hash = hash_; r.message = message
    r.author = author; r.timestamp = timestamp
    return r

def _activity(site, action="Migrate", creation="2026-01-10"):
    a = MagicMock(); a.site = site; a.action = action; a.creation = creation
    return a

def _cfg(parent, value):
    c = MagicMock(); c.parent = parent; c.value = value
    return c

def _candidate(name, status="Success", creation="2026-01-09"):
    return _FDict(name=name, status=status, creation=creation)

def _job(name, site, job_type="New Site", creation="2026-01-10"):
    return _FDict(name=name, site=site, job_type=job_type, creation=creation, status="Failure")


PATCH = "press.press.doctype.bench.bench_dev_overview.frappe"


class TestGetDevPanelData(unittest.TestCase):

    def _setup(self, mf, bench_name="bench-001", sites=None, activities=None,
               cfg=None, bench_apps=None, panel_releases=None,
               build_history=None, error_list=None):
        mf.only_for = MagicMock()
        bench_doc = _bench_doc(bench_name, apps=bench_apps or [])
        mf.get_doc.return_value = bench_doc

        def _get_all(doctype, *a, **kw):
            if doctype == "Site":             return sites or []
            if doctype == "Site Activity":    return activities or []
            if doctype == "Site Config":      return cfg or []
            if doctype == "App Release":      return panel_releases or []
            if doctype == "Deploy Candidate": return build_history or []
            if doctype == "Agent Job":        return error_list or []
            return []

        mf.get_all.side_effect = _get_all

    @patch(PATCH)
    def test_returns_all_four_top_level_keys(self, mf):
        self._setup(mf)
        r = _bdo.get_dev_panel_data("bench-001")
        for k in ("sites", "recent_commits", "build_history", "errors"):
            self.assertIn(k, r)
        self.assertIn("count",  r["errors"])
        self.assertIn("errors", r["errors"])

    @patch(PATCH)
    def test_requires_system_manager(self, mf):
        mf.only_for.side_effect = Exception("Not permitted")
        with self.assertRaises(Exception):
            _bdo.get_dev_panel_data("bench-001")

    @patch(PATCH)
    def test_migrated_true_when_activity_exists(self, mf):
        site = _site_row("s1", "bench-001")
        self._setup(mf, sites=[site], activities=[_activity("s1")])
        r = _bdo.get_dev_panel_data("bench-001")
        self.assertTrue(r["sites"][0]["migrated"])

    @patch(PATCH)
    def test_migrated_false_when_no_activity(self, mf):
        site = _site_row("s2", "bench-001")
        self._setup(mf, sites=[site], activities=[])
        r = _bdo.get_dev_panel_data("bench-001")
        self.assertFalse(r["sites"][0]["migrated"])

    @patch(PATCH)
    def test_scheduler_enabled_true_when_no_config(self, mf):
        site = _site_row("s3", "bench-001")
        self._setup(mf, sites=[site], cfg=[])
        r = _bdo.get_dev_panel_data("bench-001")
        self.assertTrue(r["sites"][0]["scheduler_enabled"])

    @patch(PATCH)
    def test_scheduler_disabled_when_paused_string_1(self, mf):
        site = _site_row("s4", "bench-001")
        self._setup(mf, sites=[site], cfg=[_cfg("s4", "1")])
        r = _bdo.get_dev_panel_data("bench-001")
        self.assertFalse(r["sites"][0]["scheduler_enabled"])

    @patch(PATCH)
    def test_scheduler_enabled_true_when_pause_scheduler_is_string_zero(self, mf):
        """THE BUG FIX: '0' must NOT be treated as paused (bool('0')==True was wrong)."""
        site = _site_row("s5", "bench-001")
        self._setup(mf, sites=[site], cfg=[_cfg("s5", "0")])
        r = _bdo.get_dev_panel_data("bench-001")
        self.assertTrue(r["sites"][0]["scheduler_enabled"],
                        "Regression: '0' must mean NOT paused")

    @patch(PATCH)
    def test_recent_commits_populated(self, mf):
        ae = MagicMock(); ae.app = "frappe"; ae.hash = "abcdef1234"
        rel = _release("abcdef1234", message="feat: new\nbody", author="bob")
        self._setup(mf, bench_apps=[ae], panel_releases=[rel])
        r = _bdo.get_dev_panel_data("bench-001")
        self.assertEqual(len(r["recent_commits"]), 1)
        c = r["recent_commits"][0]
        self.assertEqual(c["app"], "frappe")
        self.assertEqual(c["hash"], "abcdef1")
        self.assertEqual(c["message"], "feat: new")

    @patch(PATCH)
    def test_recent_commits_empty_when_no_apps(self, mf):
        self._setup(mf, bench_apps=[])
        r = _bdo.get_dev_panel_data("bench-001")
        self.assertEqual(r["recent_commits"], [])

    @patch(PATCH)
    def test_build_history_max_5(self, mf):
        cands = [_candidate(f"dc-{i}") for i in range(5)]
        self._setup(mf, build_history=cands)
        r = _bdo.get_dev_panel_data("bench-001")
        self.assertLessEqual(len(r["build_history"]), 5)

    @patch(PATCH)
    def test_build_history_items_have_required_fields(self, mf):
        self._setup(mf, build_history=[_candidate("dc-001")])
        r = _bdo.get_dev_panel_data("bench-001")
        item = r["build_history"][0]
        for f in ("name", "status", "creation"):
            self.assertIn(f, item)

    @patch(PATCH)
    def test_errors_count_matches_list_length(self, mf):
        site = _site_row("sf", "bench-001")
        jobs = [_job(f"AJ-{i}", "sf") for i in range(4)]
        self._setup(mf, sites=[site], error_list=jobs)
        r = _bdo.get_dev_panel_data("bench-001")
        self.assertEqual(r["errors"]["count"], 4)
        self.assertEqual(len(r["errors"]["errors"]), 4)

    @patch(PATCH)
    def test_errors_zero_when_no_failures(self, mf):
        self._setup(mf, error_list=[])
        r = _bdo.get_dev_panel_data("bench-001")
        self.assertEqual(r["errors"]["count"], 0)
        self.assertEqual(r["errors"]["errors"], [])

    @patch(PATCH)
    def test_errors_skipped_when_bench_has_no_sites(self, mf):
        self._setup(mf, sites=[])
        r = _bdo.get_dev_panel_data("bench-001")
        self.assertEqual(r["errors"]["count"], 0)

    @patch(PATCH)
    def test_build_history_filtered_by_bench_group(self, mf):
        """Deploy Candidate query must filter by bench.group, not bench name."""
        self._setup(mf, bench_name="bench-002")
        _bdo.get_dev_panel_data("bench-002")
        dc_call = next(
            c for c in mf.get_all.call_args_list
            if c.args[0] == "Deploy Candidate"
        )
        self.assertEqual(dc_call[1]["filters"]["group"], "rg-001")


if __name__ == "__main__":
    unittest.main(verbosity=2)
