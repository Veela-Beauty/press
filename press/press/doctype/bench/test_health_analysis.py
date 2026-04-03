"""
Unit tests for analyze_app_code() — external analysis service integration.
Dual output: HTML (human-readable) + JSON (AI-consumable).

Run:
  cd /home/eslam/data/erpnext-app-repos/press_local
  python3 -m unittest press.press.doctype.bench.test_health_analysis -v
"""
import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# ── Frappe stub ──────────────────────────────────────────────────────────
_frappe_stub = types.ModuleType("frappe")
_frappe_stub._ = lambda s: s
_frappe_stub.whitelist = lambda fn=None, **kw: (lambda f: f) if fn is None else fn
_frappe_stub.only_for = lambda role: None
_frappe_stub.get_doc = MagicMock()
_frappe_stub.get_all = MagicMock()
_frappe_stub.session = MagicMock()
_frappe_stub.session.user = "admin@test.com"
_frappe_stub.db = MagicMock()
_frappe_stub.cache = MagicMock()
_frappe_stub.cache.get_value = MagicMock(return_value=None)
_frappe_stub.cache.set_value = MagicMock()
_frappe_stub.throw = MagicMock(side_effect=Exception("Frappe throw"))
_frappe_stub.logger = lambda: MagicMock()
_frappe_stub.conf = MagicMock()
sys.modules.setdefault("frappe", _frappe_stub)

import press.press.doctype.bench.health_analysis as _ha  # noqa: E402

PATCH = "press.press.doctype.bench.health_analysis"


def _mock_response(status_code=200, json_data=None):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = status_code < 400
    resp.json.return_value = json_data or {}
    resp.text = json.dumps(json_data or {})
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


SAMPLE_ANALYSIS = {
    "html": "<div class='codegraph'><h3>File Structure</h3><ul><li>main.py (120 lines)</li></ul></div>",
    "json": {
        "files": [{"path": "main.py", "language": "python", "lines": 120, "symbols": 5}],
        "symbols": [{"name": "main", "type": "function", "file": "main.py", "line": 1}],
        "edges": [{"from": "main", "to": "helper", "type": "calls"}],
    },
    "meta": {
        "commit": "abc1234",
        "analyzed_at": "2026-04-03T12:00:00",
        "file_count": 1,
        "symbol_count": 5,
    },
}


class TestAnalyzeAppCodeAuth(unittest.TestCase):
    """Auth and permission tests."""

    def test_requires_system_manager(self):
        """Endpoint must enforce System Manager role."""
        _frappe_stub.only_for = MagicMock(side_effect=Exception("Not permitted"))
        with self.assertRaises(Exception):
            _ha.analyze_app_code("https://github.com/user/repo", "abc1234")
        _frappe_stub.only_for = MagicMock()  # restore

    @patch(f"{PATCH}._get_analysis_config")
    def test_rejects_when_no_service_url_configured(self, mock_config):
        """Must fail if analysis service URL is not configured."""
        mock_config.return_value = {"url": "", "token": "tok123"}
        result = _ha.analyze_app_code("https://github.com/user/repo", "abc1234")
        self.assertIn("error", result)
        self.assertIn("not configured", result["error"].lower())

    @patch(f"{PATCH}._get_analysis_config")
    def test_rejects_when_no_auth_token_configured(self, mock_config):
        """Must fail if auth token is not set."""
        mock_config.return_value = {"url": "http://analyzer:8000", "token": ""}
        result = _ha.analyze_app_code("https://github.com/user/repo", "abc1234")
        self.assertIn("error", result)
        self.assertIn("token", result["error"].lower())


class TestAnalyzeAppCodeParams(unittest.TestCase):
    """Parameter validation tests."""

    @patch(f"{PATCH}._get_analysis_config")
    def test_rejects_empty_git_url(self, mock_config):
        mock_config.return_value = {"url": "http://analyzer:8000", "token": "tok123"}
        result = _ha.analyze_app_code("", "abc1234")
        self.assertIn("error", result)

    @patch(f"{PATCH}._get_analysis_config")
    def test_rejects_empty_commit(self, mock_config):
        mock_config.return_value = {"url": "http://analyzer:8000", "token": "tok123"}
        result = _ha.analyze_app_code("https://github.com/user/repo", "")
        self.assertIn("error", result)

    @patch(f"{PATCH}._get_analysis_config")
    def test_accepts_valid_github_url(self, mock_config):
        """Should accept standard GitHub HTTPS URLs."""
        mock_config.return_value = {"url": "http://analyzer:8000", "token": "tok123"}
        with patch(f"{PATCH}._call_analysis_service", return_value=SAMPLE_ANALYSIS):
            result = _ha.analyze_app_code("https://github.com/frappe/erpnext", "abc1234")
            self.assertNotIn("error", result)

    @patch(f"{PATCH}._get_analysis_config")
    def test_accepts_git_ssh_url(self, mock_config):
        """Should accept git@github.com:user/repo.git URLs."""
        mock_config.return_value = {"url": "http://analyzer:8000", "token": "tok123"}
        with patch(f"{PATCH}._call_analysis_service", return_value=SAMPLE_ANALYSIS):
            result = _ha.analyze_app_code("git@github.com:frappe/erpnext.git", "abc1234")
            self.assertNotIn("error", result)


class TestAnalyzeAppCodeServiceCall(unittest.TestCase):
    """Tests that the service is called correctly."""

    @patch(f"{PATCH}._get_analysis_config")
    @patch(f"{PATCH}._call_analysis_service")
    def test_sends_git_url_and_commit(self, mock_call, mock_config):
        mock_config.return_value = {"url": "http://analyzer:8000", "token": "tok123"}
        mock_call.return_value = SAMPLE_ANALYSIS
        _ha.analyze_app_code("https://github.com/frappe/erpnext", "abc1234", output_format="json")
        mock_call.assert_called_once()
        args = mock_call.call_args
        self.assertEqual(args[0][0], "https://github.com/frappe/erpnext")
        self.assertEqual(args[0][1], "abc1234")

    @patch(f"{PATCH}._get_analysis_config")
    @patch(f"{PATCH}._call_analysis_service")
    def test_passes_auth_token_to_service(self, mock_call, mock_config):
        mock_config.return_value = {"url": "http://analyzer:8000", "token": "secret-tok"}
        mock_call.return_value = SAMPLE_ANALYSIS
        _ha.analyze_app_code("https://github.com/frappe/erpnext", "abc1234")
        args = mock_call.call_args
        # Config should be passed so service call can use the token
        config = args[0][2]  # third positional arg is config
        self.assertEqual(config["token"], "secret-tok")


class TestAnalyzeAppCodeDualFormat(unittest.TestCase):
    """Tests for dual output format (HTML + JSON)."""

    @patch(f"{PATCH}._get_analysis_config")
    @patch(f"{PATCH}._call_analysis_service")
    def test_returns_html_when_requested(self, mock_call, mock_config):
        mock_config.return_value = {"url": "http://analyzer:8000", "token": "tok123"}
        mock_call.return_value = SAMPLE_ANALYSIS
        result = _ha.analyze_app_code("https://github.com/user/repo", "abc1234", output_format="html")
        self.assertIn("html", result)
        self.assertIn("<div", result["html"])

    @patch(f"{PATCH}._get_analysis_config")
    @patch(f"{PATCH}._call_analysis_service")
    def test_returns_json_when_requested(self, mock_call, mock_config):
        mock_config.return_value = {"url": "http://analyzer:8000", "token": "tok123"}
        mock_call.return_value = SAMPLE_ANALYSIS
        result = _ha.analyze_app_code("https://github.com/user/repo", "abc1234", output_format="json")
        self.assertIn("json", result)
        self.assertIn("files", result["json"])
        self.assertIn("symbols", result["json"])
        self.assertIn("edges", result["json"])

    @patch(f"{PATCH}._get_analysis_config")
    @patch(f"{PATCH}._call_analysis_service")
    def test_returns_both_by_default(self, mock_call, mock_config):
        mock_config.return_value = {"url": "http://analyzer:8000", "token": "tok123"}
        mock_call.return_value = SAMPLE_ANALYSIS
        result = _ha.analyze_app_code("https://github.com/user/repo", "abc1234")
        self.assertIn("html", result)
        self.assertIn("json", result)
        self.assertIn("meta", result)

    @patch(f"{PATCH}._get_analysis_config")
    @patch(f"{PATCH}._call_analysis_service")
    def test_meta_includes_commit_and_timestamp(self, mock_call, mock_config):
        mock_config.return_value = {"url": "http://analyzer:8000", "token": "tok123"}
        mock_call.return_value = SAMPLE_ANALYSIS
        result = _ha.analyze_app_code("https://github.com/user/repo", "abc1234")
        self.assertIn("meta", result)
        self.assertEqual(result["meta"]["commit"], "abc1234")
        self.assertIn("analyzed_at", result["meta"])


class TestAnalyzeAppCodeCaching(unittest.TestCase):
    """Tests that results are cached by (git_url, commit)."""

    @patch(f"{PATCH}._get_analysis_config")
    @patch(f"{PATCH}._call_analysis_service")
    def test_caches_result_after_successful_call(self, mock_call, mock_config):
        mock_config.return_value = {"url": "http://analyzer:8000", "token": "tok123"}
        mock_call.return_value = SAMPLE_ANALYSIS
        _frappe_stub.cache.get_value.return_value = None  # no cache
        _ha.analyze_app_code("https://github.com/user/repo", "abc1234")
        _frappe_stub.cache.set_value.assert_called()

    @patch(f"{PATCH}._get_analysis_config")
    @patch(f"{PATCH}._call_analysis_service")
    def test_returns_cached_result_without_calling_service(self, mock_call, mock_config):
        mock_config.return_value = {"url": "http://analyzer:8000", "token": "tok123"}
        _frappe_stub.cache.get_value.return_value = json.dumps(SAMPLE_ANALYSIS)
        result = _ha.analyze_app_code("https://github.com/user/repo", "abc1234")
        mock_call.assert_not_called()
        self.assertIn("html", result)
        _frappe_stub.cache.get_value.return_value = None  # restore


class TestAnalyzeAppCodeErrors(unittest.TestCase):
    """Tests for error handling."""

    @patch(f"{PATCH}._get_analysis_config")
    @patch(f"{PATCH}._call_analysis_service")
    def test_returns_error_on_service_failure(self, mock_call, mock_config):
        mock_config.return_value = {"url": "http://analyzer:8000", "token": "tok123"}
        mock_call.side_effect = Exception("Connection refused")
        result = _ha.analyze_app_code("https://github.com/user/repo", "abc1234")
        self.assertIn("error", result)
        self.assertIn("Connection refused", result["error"])

    @patch(f"{PATCH}._get_analysis_config")
    @patch(f"{PATCH}._call_analysis_service")
    def test_does_not_cache_on_failure(self, mock_call, mock_config):
        mock_config.return_value = {"url": "http://analyzer:8000", "token": "tok123"}
        mock_call.side_effect = Exception("timeout")
        _frappe_stub.cache.set_value.reset_mock()
        _ha.analyze_app_code("https://github.com/user/repo", "abc1234")
        _frappe_stub.cache.set_value.assert_not_called()


class TestCallAnalysisService(unittest.TestCase):
    """Tests for the HTTP call to the external service."""

    @patch(f"{PATCH}.requests.post")
    def test_sends_post_with_bearer_token(self, mock_post):
        mock_post.return_value = _mock_response(200, SAMPLE_ANALYSIS)
        config = {"url": "http://analyzer:8000", "token": "secret-tok"}
        _ha._call_analysis_service("https://github.com/user/repo", "abc1234", config)
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        headers = call_kwargs[1].get("headers", call_kwargs.kwargs.get("headers", {}))
        self.assertIn("Authorization", headers)
        self.assertEqual(headers["Authorization"], "Bearer secret-tok")

    @patch(f"{PATCH}.requests.post")
    def test_sends_correct_payload(self, mock_post):
        mock_post.return_value = _mock_response(200, SAMPLE_ANALYSIS)
        config = {"url": "http://analyzer:8000", "token": "tok"}
        _ha._call_analysis_service("https://github.com/user/repo", "abc1234", config)
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1].get("json", call_kwargs.kwargs.get("json", {}))
        self.assertEqual(payload["git_url"], "https://github.com/user/repo")
        self.assertEqual(payload["commit_hash"], "abc1234")

    @patch(f"{PATCH}.requests.post")
    def test_raises_on_http_error(self, mock_post):
        mock_post.return_value = _mock_response(401, {"error": "Unauthorized"})
        config = {"url": "http://analyzer:8000", "token": "bad-tok"}
        with self.assertRaises(Exception):
            _ha._call_analysis_service("https://github.com/user/repo", "abc1234", config)

    @patch(f"{PATCH}.requests.post")
    def test_timeout_set(self, mock_post):
        """Service call must have a timeout to avoid hanging."""
        mock_post.return_value = _mock_response(200, SAMPLE_ANALYSIS)
        config = {"url": "http://analyzer:8000", "token": "tok"}
        _ha._call_analysis_service("https://github.com/user/repo", "abc1234", config)
        call_kwargs = mock_post.call_args
        timeout = call_kwargs[1].get("timeout", call_kwargs.kwargs.get("timeout", None))
        self.assertIsNotNone(timeout)
        self.assertGreater(timeout, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
