"""
Unit tests for get_dev_overview_benches() in bench_dev_overview.py

Run:
  cd /home/eslam/data/erpnext-app-repos/press_local
  python3 -m unittest press.press.doctype.bench.test_bench_dev_overview -v

Sibling test files:
  test_bench_dev_panel.py   — get_dev_panel_data() tests
  test_bench_dev_actions.py — get_bench_app_names() + push_app_to_github() tests
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



class TestGetVscodeRemoteUrl(unittest.TestCase):
    PATCH = "press.press.doctype.bench.bench_dev_overview.frappe"

    @staticmethod
    def _bypass_team_access(mf):
        """_ensure_team_access early-returns for System Users — short-circuits the team lookup."""
        mf.session.data.user_type = "System User"

    @patch(PATCH)
    def test_returns_full_vscode_uri(self, mf):
        """URL must equal the exact composed string — catches any separator/order regressions."""
        self._bypass_team_access(mf)
        bench_doc = MagicMock(server="srv-001")
        bench_doc.name = "bench-0005-000026"
        mf.get_doc.return_value = bench_doc
        mf.db.get_value.return_value = "proxy.example.com"

        expected = (
            "vscode://vscode-remote/ssh-remote+bench-0005-000026"
            "@proxy.example.com:2222/home/frappe/frappe-bench"
        )
        self.assertEqual(_bdo.get_vscode_remote_url("bench-0005-000026"), expected)
        # proxy_server lookup uses Server.proxy_server, not Bench.proxy_server
        mf.db.get_value.assert_called_once_with("Server", "srv-001", "proxy_server")

    @patch(PATCH)
    def test_raises_when_proxy_server_missing(self, mf):
        self._bypass_team_access(mf)
        bench_doc = MagicMock(server="srv-002")
        bench_doc.name = "b-002"
        mf.get_doc.return_value = bench_doc
        mf.db.get_value.return_value = None
        mf.throw.side_effect = Exception("no proxy")

        with self.assertRaises(Exception):
            _bdo.get_vscode_remote_url("b-002")
        mf.throw.assert_called_once()

    @patch(PATCH)
    def test_raises_for_nonexistent_bench(self, mf):
        self._bypass_team_access(mf)

        class _DoesNotExistError(Exception):
            pass
        mf.DoesNotExistError = _DoesNotExistError
        mf.get_doc.side_effect = _DoesNotExistError("Bench not found")

        with self.assertRaises(_DoesNotExistError):
            _bdo.get_vscode_remote_url("nonexistent-bench-zzz-9999")

    @patch(PATCH)
    def test_raises_when_bench_name_has_uri_special_chars(self, mf):
        """Bench names with @, ?, #, / etc. must be rejected — they would corrupt the URI."""
        self._bypass_team_access(mf)
        bench_doc = MagicMock(server="srv-003")
        bench_doc.name = "evil@host"
        mf.get_doc.return_value = bench_doc
        mf.throw.side_effect = Exception("unsafe name")

        with self.assertRaises(Exception):
            _bdo.get_vscode_remote_url("evil@host")
        mf.throw.assert_called_once()
        # Must reject before composing the URL — no proxy lookup should happen
        mf.db.get_value.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
