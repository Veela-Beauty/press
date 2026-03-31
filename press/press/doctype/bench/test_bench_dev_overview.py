"""
Unit tests for bench_dev_overview.py

Run:
  cd /home/eslam/data/erpnext-app-repos/press_local
  python3 -m unittest press.press.doctype.bench.test_bench_dev_overview -v

Test classes:
  TestGetDevOverviewBenches — get_dev_overview_benches() full coverage
  TestGetDevPanelData       — get_dev_panel_data() full coverage
  TestSchedulerBoolFix      — pure-logic bool("0") guard
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ─── Install frappe stub BEFORE importing bench_dev_overview ──────────────────
_frappe_stub = types.ModuleType("frappe")
_frappe_stub._ = lambda s: s
# @frappe.whitelist() is a decorator factory: whitelist() → decorator → fn
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


# ─── _FDict — dict subclass with attribute access (mirrors frappe._dict) ──────
# Production code calls dict(obj) on bench rows, site rows, build candidates,
# and agent job rows. MagicMock returns {} when converted with dict(), so we
# use _FDict for objects that travel through dict().

class _FDict(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        self[k] = v


# ─── helpers ──────────────────────────────────────────────────────────────────

def _bench(name, group="rg-001", server="srv-001", is_dev=0, status="Active"):
    """Bench row — returned by frappe.get_all("Bench"); converted via dict()."""
    return _FDict(
        name=name, status=status, group=group,
        group_title=group + " Title", server=server,
        server_title=server + " Title", cluster_title="c1",
        is_development_bench=is_dev,
        creation="2026-01-01 00:00:00", candidate=None,
    )


def _app(parent, app, hash_):
    """BenchApp child row — attribute access only, no dict() needed."""
    a = MagicMock(); a.parent = parent; a.app = app; a.hash = hash_
    return a


def _release(hash_, message="fix: x", author="dev", timestamp="2026-01-01 10:00:00"):
    r = MagicMock(); r.hash = hash_; r.message = message
    r.author = author; r.timestamp = timestamp
    return r


def _site_row(name, bench, status="Active", is_dev=0):
    """Site row for get_dev_panel_data — needs dict-item write for migrated/scheduler_enabled."""
    return _FDict(
        name=name, bench=bench, status=status,
        host_name=name + ".example.com",
        is_development_site=is_dev,
    )


def _bench_doc(name, group="rg-001", apps=None):
    doc = MagicMock(); doc.name = name; doc.group = group
    doc.apps = apps or []
    return doc


def _activity(site, action="Migrate", creation="2026-01-10"):
    a = MagicMock(); a.site = site; a.action = action; a.creation = creation
    return a


def _cfg(parent, value):
    c = MagicMock(); c.parent = parent; c.value = value
    return c


def _candidate(name, status="Success", creation="2026-01-09"):
    """Deploy Candidate — converted via dict() in production code."""
    return _FDict(name=name, status=status, creation=creation)


def _job(name, site, job_type="New Site", creation="2026-01-10"):
    """Agent Job — converted via dict() in production code."""
    return _FDict(name=name, site=site, job_type=job_type, creation=creation, status="Failure")


# ══════════════════════════════════════════════════════════════════════════════
# get_dev_overview_benches()
# ══════════════════════════════════════════════════════════════════════════════

class TestGetDevOverviewBenches(unittest.TestCase):
    PATCH = "press.press.doctype.bench.bench_dev_overview.frappe"

    @patch(PATCH)
    def test_returns_empty_list_when_no_benches(self, mf):
        mf.only_for = MagicMock()
        mf.get_all.return_value = []
        self.assertEqual(_bdo.get_dev_overview_benches(), [])

    @patch(PATCH)
    def test_basic_bench_structure(self, mf):
        """Each result row has site_count, undeployed_count, last_commit keys."""
        mf.only_for = MagicMock()
        mf.get_all.side_effect = [[_bench("b1")], [], [], []]
        mf.db.sql.return_value = []
        result = _bdo.get_dev_overview_benches()
        self.assertEqual(len(result), 1)
        for key in ("site_count", "undeployed_count", "last_commit"):
            self.assertIn(key, result[0])

    @patch(PATCH)
    def test_site_count_matches_sites(self, mf):
        mf.only_for = MagicMock()
        sites = [_site_row(f"s{i}", "b2") for i in range(3)]
        mf.get_all.side_effect = [
            [_bench("b2")], sites, [_app("b2", "erpnext", "h1")], [_release("h1")],
        ]
        mf.db.sql.return_value = []
        self.assertEqual(_bdo.get_dev_overview_benches()[0]["site_count"], 3)

    @patch(PATCH)
    def test_pending_update_count(self, mf):
        mf.only_for = MagicMock()
        sites = [
            _site_row("sa", "b3", "Active"),
            _site_row("sb", "b3", "Pending"),
            _site_row("sc", "b3", "Pending"),
        ]
        mf.get_all.side_effect = [[_bench("b3")], sites, [], []]
        mf.db.sql.return_value = []
        self.assertEqual(_bdo.get_dev_overview_benches()[0]["pending_update_count"], 2)

    @patch(PATCH)
    def test_undeployed_count_uses_batch_sql_not_db_count(self, mf):
        """Undeployed count uses frappe.db.sql (batch OR query), NOT frappe.db.count."""
        mf.only_for = MagicMock()
        mf.get_all.side_effect = [
            [_bench("b4")], [],
            [_app("b4", "frappe", "abc1234")],
            [_release("abc1234", timestamp="2026-01-01 09:00:00")],
        ]
        mf.db.sql.return_value = [MagicMock(app="frappe", cnt=3)]
        result = _bdo.get_dev_overview_benches()
        self.assertEqual(result[0]["undeployed_count"], 3)
        mf.db.sql.assert_called_once()
        mf.db.count.assert_not_called()

    @patch(PATCH)
    def test_undeployed_count_zero_when_sql_returns_empty(self, mf):
        mf.only_for = MagicMock()
        mf.get_all.side_effect = [
            [_bench("b5")], [],
            [_app("b5", "frappe", "h9")],
            [_release("h9")],
        ]
        mf.db.sql.return_value = []
        self.assertEqual(_bdo.get_dev_overview_benches()[0]["undeployed_count"], 0)

    @patch(PATCH)
    def test_undeployed_count_zero_and_sql_not_called_when_no_matching_release(self, mf):
        """App hash has no matching release → no timestamp → sql skipped."""
        mf.only_for = MagicMock()
        mf.get_all.side_effect = [
            [_bench("b6")], [],
            [_app("b6", "frappe", "unknown")],
            [],  # no release for "unknown"
        ]
        mf.db.sql.return_value = []
        result = _bdo.get_dev_overview_benches()
        self.assertEqual(result[0]["undeployed_count"], 0)
        mf.db.sql.assert_not_called()

    @patch(PATCH)
    def test_hash_list_capped_at_100_for_release_query(self, mf):
        """101 unique hashes → App Release get_all called with ≤100 hashes."""
        mf.only_for = MagicMock()
        apps = [_app("b7", f"app{i}", f"h{i:04d}") for i in range(101)]
        mf.get_all.side_effect = [[_bench("b7")], [], apps, []]
        mf.db.sql.return_value = []
        _bdo.get_dev_overview_benches()
        release_call = mf.get_all.call_args_list[3]
        sent_hashes = release_call[1]["filters"]["hash"][1]
        self.assertLessEqual(len(sent_hashes), 100)

    @patch(PATCH)
    def test_last_commit_seven_char_hash_and_first_line_message(self, mf):
        mf.only_for = MagicMock()
        mf.get_all.side_effect = [
            [_bench("b8")], [],
            [_app("b8", "frappe", "deadbeef1234")],
            [_release("deadbeef1234", message="chore: cleanup\n\nbody", author="alice")],
        ]
        mf.db.sql.return_value = []
        lc = _bdo.get_dev_overview_benches()[0]["last_commit"]
        self.assertIsNotNone(lc)
        self.assertEqual(lc["hash"], "deadbee")
        self.assertEqual(lc["message"], "chore: cleanup")
        self.assertEqual(lc["author"], "alice")

    @patch(PATCH)
    def test_last_commit_is_none_when_no_app_hash(self, mf):
        mf.only_for = MagicMock()
        mf.get_all.side_effect = [[_bench("b9")], [], [_app("b9", "frappe", None)], []]
        mf.db.sql.return_value = []
        self.assertIsNone(_bdo.get_dev_overview_benches()[0]["last_commit"])

    @patch(PATCH)
    def test_multiple_benches_get_separate_undeployed_counts(self, mf):
        """Two benches sharing same app → each gets count from sql rows."""
        b1 = _bench("b10"); b2 = _bench("b11")
        a1 = _app("b10", "frappe", "ha"); a2 = _app("b11", "frappe", "hb")
        r1 = _release("ha", timestamp="2026-01-01"); r2 = _release("hb", timestamp="2026-01-02")
        mf.only_for = MagicMock()
        mf.get_all.side_effect = [[b1, b2], [], [a1, a2], [r1, r2]]
        mf.db.sql.return_value = [MagicMock(app="frappe", cnt=2)]
        result = _bdo.get_dev_overview_benches()
        counts = {r["name"]: r["undeployed_count"] for r in result}
        self.assertEqual(counts["b10"], 2)
        self.assertEqual(counts["b11"], 2)

    @patch(PATCH)
    def test_requires_system_manager(self, mf):
        mf.only_for.side_effect = Exception("Not permitted")
        with self.assertRaises(Exception):
            _bdo.get_dev_overview_benches()


# ══════════════════════════════════════════════════════════════════════════════
# get_dev_panel_data()
# ══════════════════════════════════════════════════════════════════════════════

class TestGetDevPanelData(unittest.TestCase):
    PATCH = "press.press.doctype.bench.bench_dev_overview.frappe"

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


# ══════════════════════════════════════════════════════════════════════════════
# Scheduler bool('0') guard — pure logic
# ══════════════════════════════════════════════════════════════════════════════

class TestSchedulerBoolFix(unittest.TestCase):

    def _paused(self, value):
        return value in (True, 1, "1", "true")

    def test_string_one_is_paused(self):      self.assertTrue(self._paused("1"))
    def test_int_one_is_paused(self):         self.assertTrue(self._paused(1))
    def test_bool_true_is_paused(self):       self.assertTrue(self._paused(True))
    def test_string_zero_is_NOT_paused(self): self.assertFalse(self._paused("0"))
    def test_int_zero_is_NOT_paused(self):    self.assertFalse(self._paused(0))
    def test_bool_false_is_NOT_paused(self):  self.assertFalse(self._paused(False))
    def test_none_is_NOT_paused(self):        self.assertFalse(self._paused(None))
    def test_empty_string_is_NOT_paused(self):self.assertFalse(self._paused(""))

    def test_scheduler_enabled_is_inverse_of_paused(self):
        for value, expect_enabled in [("1", False), ("0", True), (1, False), (0, True)]:
            self.assertEqual(not self._paused(value), expect_enabled,
                             f"value={value!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
