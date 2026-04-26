"""
Unit tests for get_vscode_remote_url() in bench_vscode.py

Run:
  cd /home/eslam/data/erpnext-app-repos/press_local
  python3 -m unittest press.press.doctype.bench.test_bench_vscode -v
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ─── Install frappe stub BEFORE importing bench_vscode ────────────────────────
_frappe_stub = types.ModuleType("frappe")
_frappe_stub._ = lambda s: s
_frappe_stub.whitelist = lambda fn=None, **kw: (lambda f: f) if fn is None else fn
_frappe_stub.throw = MagicMock(side_effect=Exception)
_frappe_stub.get_doc = MagicMock()
_frappe_stub.session = MagicMock()
_frappe_stub.session.user = "alice@x.com"
_frappe_stub.db = MagicMock()
sys.modules.setdefault("frappe", _frappe_stub)

import press.press.doctype.bench.bench_vscode as _bv  # noqa: E402


@patch("press.press.doctype.bench.bench_vscode._ensure_team_access", lambda **kw: None)
class TestGetVscodeRemoteUrl(unittest.TestCase):
    PATCH = "press.press.doctype.bench.bench_vscode.frappe"

    def _bench(self, name="bench-001", server="srv-001"):
        b = MagicMock(); b.name = name; b.server = server
        return b

    @patch(PATCH)
    def test_returns_full_vscode_uri(self, mf):
        mf.get_doc.return_value = self._bench()
        mf.db.get_value.return_value = "n1.proxy.example.com"
        url = _bv.get_vscode_remote_url("bench-001")
        self.assertEqual(
            url,
            "vscode://vscode-remote/ssh-remote+bench-001@n1.proxy.example.com:2222"
            "/home/frappe/frappe-bench",
        )

    @patch(PATCH)
    def test_raises_when_proxy_server_missing(self, mf):
        mf.get_doc.return_value = self._bench()
        mf.db.get_value.return_value = None
        mf.throw = MagicMock(side_effect=Exception("no proxy"))
        with self.assertRaises(Exception):
            _bv.get_vscode_remote_url("bench-001")
        mf.throw.assert_called_once()

    @patch(PATCH)
    def test_raises_when_bench_name_has_uri_special_chars(self, mf):
        mf.get_doc.return_value = self._bench(name="evil@host")
        mf.throw = MagicMock(side_effect=Exception("unsafe"))
        with self.assertRaises(Exception):
            _bv.get_vscode_remote_url("evil@host")
        mf.throw.assert_called_once()
        # Must throw BEFORE proxy lookup
        mf.db.get_value.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
