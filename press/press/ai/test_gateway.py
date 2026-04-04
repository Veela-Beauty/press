"""Tests for AI gateway — orchestrates linter + budget + scope guard + provider call.

The gateway is the single entry point for all AI requests. It:
1. Checks site scope (dev/staging/prod)
2. Checks branch (dev-* only for commits)
3. Checks token budget (user cap + project pool)
4. Reserves tokens optimistically
5. Calls the LLM provider
6. Lints the response
7. Reconciles actual token usage
8. Returns the sanitized result

Provider calls are mocked — the gateway orchestration is what we test.
"""

import unittest
from unittest.mock import AsyncMock, patch, MagicMock


class TestGatewayOrchestration(unittest.TestCase):
    """Test the gateway orchestrates all checks correctly."""

    def setUp(self):
        from press.press.ai.gateway import reset_budget_engine
        reset_budget_engine()

    def test_blocks_production_site(self):
        from press.press.ai.gateway import process_ai_request

        result = process_ai_request(
            user="dev@test.com",
            project="project-1",
            site_type="Production",
            branch="dev-feature",
            prompt="fix the bug",
            provider="anthropic",
            api_key="sk-ant-test",
        )
        self.assertFalse(result.success)
        self.assertIn("production", result.error.lower())

    def test_blocks_non_dev_branch(self):
        from press.press.ai.gateway import process_ai_request

        result = process_ai_request(
            user="dev@test.com",
            project="project-1",
            site_type="Dev",
            branch="main",
            prompt="add a field",
            provider="anthropic",
            api_key="sk-ant-test",
        )
        self.assertFalse(result.success)
        self.assertIn("dev-", result.error.lower())

    def test_blocks_when_over_budget(self):
        from press.press.ai.gateway import process_ai_request, get_budget_engine

        engine = get_budget_engine()
        engine.set_user_cap("dev@test.com", daily_cap=100)
        engine.record_usage("dev@test.com", "project-1", tokens=100)

        result = process_ai_request(
            user="dev@test.com",
            project="project-1",
            site_type="Dev",
            branch="dev-feature",
            prompt="anything",
            provider="anthropic",
            api_key="sk-ant-test",
        )
        self.assertFalse(result.success)
        self.assertIn("budget", result.error.lower())

    def test_returns_no_key_error(self):
        from press.press.ai.gateway import process_ai_request

        result = process_ai_request(
            user="dev@test.com",
            project="project-1",
            site_type="Dev",
            branch="dev-feature",
            prompt="help",
            provider="anthropic",
            api_key=None,
        )
        self.assertFalse(result.success)
        self.assertIn("key", result.error.lower())

    def test_successful_request_returns_response(self):
        from press.press.ai.gateway import process_ai_request

        with patch("press.press.ai.gateway._call_provider") as mock_call:
            mock_call.return_value = {
                "text": "Here is a safe code fix:\n```python\nprint('hello')\n```",
                "input_tokens": 500,
                "output_tokens": 200,
                "model": "claude-sonnet-4-20250514",
            }
            result = process_ai_request(
                user="dev@test.com",
                project="project-1",
                site_type="Dev",
                branch="dev-feature",
                prompt="fix the bug",
                provider="anthropic",
                api_key="sk-ant-test-key",
            )
            self.assertTrue(result.success)
            self.assertIn("hello", result.response_text)
            self.assertFalse(result.lint_result.has_violations)

    def test_lints_response_and_returns_violations(self):
        from press.press.ai.gateway import process_ai_request

        with patch("press.press.ai.gateway._call_provider") as mock_call:
            mock_call.return_value = {
                "text": "Try this:\n```python\nfrappe.db.sql('DELETE FROM tabSite')\n```",
                "input_tokens": 500,
                "output_tokens": 200,
                "model": "claude-sonnet-4-20250514",
            }
            result = process_ai_request(
                user="dev@test.com",
                project="project-1",
                site_type="Dev",
                branch="dev-feature",
                prompt="clean old data",
                provider="anthropic",
                api_key="sk-ant-test-key",
            )
            self.assertTrue(result.success)
            self.assertTrue(result.lint_result.has_violations)
            # Cat 1 block removed from sanitized text
            self.assertNotIn("DELETE FROM", result.response_text)

    def test_records_usage_after_success(self):
        from press.press.ai.gateway import process_ai_request, get_budget_engine

        engine = get_budget_engine()
        initial = engine.get_user_usage("dev@test.com")

        with patch("press.press.ai.gateway._call_provider") as mock_call:
            mock_call.return_value = {
                "text": "Safe response",
                "input_tokens": 1000,
                "output_tokens": 500,
                "model": "claude-sonnet-4-20250514",
            }
            process_ai_request(
                user="dev@test.com",
                project="project-1",
                site_type="Dev",
                branch="dev-feature",
                prompt="test",
                provider="anthropic",
                api_key="sk-ant-test-key",
            )

        final = engine.get_user_usage("dev@test.com")
        self.assertEqual(final - initial, 1500)  # 1000 + 500


class TestGatewayResult(unittest.TestCase):
    """Test GatewayResult structure."""

    def setUp(self):
        from press.press.ai.gateway import reset_budget_engine
        reset_budget_engine()

    def test_failed_result_has_error(self):
        from press.press.ai.gateway import process_ai_request

        result = process_ai_request(
            user="dev@test.com",
            project="project-1",
            site_type="Production",
            branch="dev-test",
            prompt="x",
            provider="anthropic",
            api_key="sk-test",
        )
        self.assertFalse(result.success)
        self.assertTrue(len(result.error) > 0)
        self.assertEqual(result.response_text, "")


if __name__ == "__main__":
    unittest.main()
