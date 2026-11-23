"""
Unit tests for get_app_git_status() in bench_dev_overview.py

Run:
  cd /home/eslam/data/erpnext-app-repos/press_local
  python3 -m unittest press.press.doctype.bench.test_bench_dev_git_status -v
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

PATCH = "press.press.doctype.bench.dev_overview.panel.frappe"
GUARD = "press.press.doctype.bench.dev_overview.panel.ensure_team_access"


def _app_entry(app, hash_="abc123"):
    ae = MagicMock()
    ae.app = app
    ae.hash = hash_
    return ae


def _bench_doc(name, apps):
    doc = MagicMock()
    doc.name = name
    doc.apps = apps
    return doc


def _docker_result(output, returncode=0):
    return {"status": "Success", "output": output, "returncode": returncode}


def _git(log="HEAD -> main:::", porcelain="", ahead="0", remote_rc=0):
    """docker_execute side effect: what each git command of get_app_git_status prints."""
    def run(cmd, **kwargs):
        if " log -1 " in cmd:
            return _docker_result(log)
        if " remote get-url " in cmd:
            return _docker_result("git@github.com:org/app.git", remote_rc)
        if " status --porcelain" in cmd:
            return _docker_result(porcelain)
        if " rev-list --count " in cmd:
            return _docker_result(ahead)
        raise AssertionError(f"unexpected command {cmd}")
    return run


class TestGetAppGitStatus(unittest.TestCase):
    """Tests for the batched get_app_git_status() — single docker_execute call."""

    @patch(PATCH)
    def test_requires_team_access(self, mf):
        with (
            patch(GUARD, side_effect=PermissionError("Not allowed")) as guard,
            self.assertRaises(PermissionError),
        ):
            _bdo.get_app_git_status("bench-001")
        guard.assert_called_once_with(bench_name="bench-001")
        mf.get_doc.assert_not_called()

    @patch(PATCH)
    def test_returns_list_of_apps(self, mf):
        bench = _bench_doc("bench-001", [_app_entry("frappe"), _app_entry("erpnext")])
        mf.get_doc.return_value = bench
        bench.docker_execute.return_value = _docker_result(
            "frappe:version-15:0:0:fix: cleanup\nerpnext:version-15:1:0:feat: new"
        )
        result = _bdo.get_app_git_status("bench-001")
        self.assertEqual(len(result), 2)

    @patch(PATCH)
    def test_result_has_required_keys(self, mf):
        bench = _bench_doc("bench-001", [_app_entry("frappe")])
        mf.get_doc.return_value = bench
        bench.docker_execute.return_value = _docker_result("frappe:version-15:3:2:feat: new")
        result = _bdo.get_app_git_status("bench-001")
        for key in ("app", "branch", "ahead", "dirty", "last_msg"):
            self.assertIn(key, result[0])

    @patch(PATCH)
    def test_parses_ahead_and_dirty_counts(self, mf):
        bench = _bench_doc("bench-001", [_app_entry("erpnext")])
        mf.get_doc.return_value = bench
        bench.docker_execute.side_effect = _git(
            log="HEAD -> version-15, origin/version-15:::fix: tax",
            porcelain="\n".join(f" M file{i}.py" for i in range(7)),
            ahead="4",
        )
        result = _bdo.get_app_git_status("bench-001")
        self.assertEqual(result[0]["ahead"], 4)
        self.assertEqual(result[0]["dirty"], 7)
        self.assertEqual(result[0]["branch"], "version-15")

    @patch(PATCH)
    def test_last_msg_captured(self, mf):
        bench = _bench_doc("bench-001", [_app_entry("press")])
        mf.get_doc.return_value = bench
        bench.docker_execute.side_effect = _git(log="HEAD -> main:::feat: add git status")
        result = _bdo.get_app_git_status("bench-001")
        self.assertEqual(result[0]["last_msg"], "feat: add git status")

    @patch(PATCH)
    def test_one_docker_execute_per_git_command(self, mf):
        """Subshells do not expand inside docker exec: log, remote, status, rev-list run as 4 calls per app."""
        bench = _bench_doc("bench-001", [_app_entry("frappe"), _app_entry("erpnext"), _app_entry("press")])
        mf.get_doc.return_value = bench
        bench.docker_execute.side_effect = _git()
        _bdo.get_app_git_status("bench-001")
        self.assertEqual(bench.docker_execute.call_count, 12)

    @patch(PATCH)
    def test_no_remote_skips_ahead_count(self, mf):
        bench = _bench_doc("bench-001", [_app_entry("myapp")])
        mf.get_doc.return_value = bench
        bench.docker_execute.side_effect = _git(remote_rc=2)
        result = _bdo.get_app_git_status("bench-001")
        self.assertEqual(bench.docker_execute.call_count, 3)
        self.assertEqual((result[0]["has_remote"], result[0]["ahead"]), (False, 0))

    @patch(PATCH)
    def test_docker_execute_no_log(self, mf):
        """git status polls must not flood the bench shell log."""
        bench = _bench_doc("bench-001", [_app_entry("frappe")])
        mf.get_doc.return_value = bench
        bench.docker_execute.return_value = _docker_result("frappe:v15:0:0:")
        _bdo.get_app_git_status("bench-001")
        call_kwargs = bench.docker_execute.call_args[1]
        self.assertFalse(call_kwargs.get("create_log", True))

    @patch(PATCH)
    def test_docker_failure_returns_safe_defaults(self, mf):
        bench = _bench_doc("bench-001", [_app_entry("frappe")])
        mf.get_doc.return_value = bench
        bench.docker_execute.side_effect = Exception("container not found")
        result = _bdo.get_app_git_status("bench-001")
        self.assertEqual(result[0]["ahead"], 0)
        self.assertEqual(result[0]["dirty"], 0)
        self.assertEqual(result[0]["branch"], "?")

    @patch(PATCH)
    def test_empty_bench_returns_empty_list(self, mf):
        bench = _bench_doc("bench-001", [])
        mf.get_doc.return_value = bench
        result = _bdo.get_app_git_status("bench-001")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
