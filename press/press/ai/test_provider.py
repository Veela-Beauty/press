"""Tests for OpenRouter provider integration.

Tests the _call_provider function with real API calls to OpenRouter.
Uses glm-4-plus model via OpenRouter.
"""

import unittest
import os


OPENROUTER_KEY = os.environ.get(
    "OPENROUTER_API_KEY",
    "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",
)


class TestOpenRouterProvider(unittest.TestCase):
    """Test real API calls to OpenRouter."""

    def test_simple_prompt(self):
        """TC-1: Simple prompt returns a response."""
        from press.press.ai.provider import call_provider

        result = call_provider(
            prompt="What is 2 + 2? Answer with just the number.",
            api_key=OPENROUTER_KEY,
            provider="openrouter",
            model="z-ai/glm-4.5-air",
        )
        self.assertIn("text", result)
        self.assertIn("4", result["text"])
        self.assertGreater(result["input_tokens"], 0)
        self.assertGreater(result["output_tokens"], 0)

    def test_frappe_context_prompt(self):
        """TC-2: Frappe-aware prompt with context."""
        from press.press.ai.provider import call_provider

        result = call_provider(
            prompt="Write a Python function that uses frappe.get_doc to fetch a Site document and return its status field. Just the function, no explanation.",
            api_key=OPENROUTER_KEY,
            provider="openrouter",
            model="z-ai/glm-4.5-air",
            system_prompt="You are a Frappe/ERPNext developer assistant. Frappe version: 15.103.0. Installed apps: frappe, erpnext.",
        )
        self.assertIn("text", result)
        self.assertIn("frappe", result["text"].lower())
        self.assertIn("get_doc", result["text"])

    def test_debug_traceback_prompt(self):
        """TC-3: Debug a traceback — returns explanation + fix."""
        from press.press.ai.provider import call_provider

        traceback = """Traceback (most recent call last):
  File "/home/frappe/frappe-bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py", line 245, in validate
    self.validate_reference_documents()
  File "/home/frappe/frappe-bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py", line 312, in validate_reference_documents
    ref_doc = frappe.get_doc(reference_doctype, reference_name)
frappe.exceptions.DoesNotExistError: Sales Invoice SI-2024-00123 does not exist"""

        result = call_provider(
            prompt=f"Debug this error and suggest a fix:\n```\n{traceback}\n```",
            api_key=OPENROUTER_KEY,
            provider="openrouter",
            model="z-ai/glm-4.5-air",
            system_prompt="You are a Frappe/ERPNext developer assistant.",
        )
        self.assertIn("text", result)
        # Should mention the error type or the missing document
        text_lower = result["text"].lower()
        self.assertTrue(
            "doesnotexist" in text_lower or "does not exist" in text_lower or "si-2024" in text_lower,
            f"Response should reference the error: {result['text'][:200]}"
        )

    def test_multi_file_scaffold(self):
        """TC-4: Scaffold a module — should return multiple files."""
        from press.press.ai.provider import call_provider

        result = call_provider(
            prompt="Create a simple Frappe DocType called 'Press AI Config' with fields: provider (Select: anthropic/openai/openrouter), api_key (Password), is_active (Check). Return the JSON definition and Python controller. Use code blocks.",
            api_key=OPENROUTER_KEY,
            provider="openrouter",
            model="z-ai/glm-4.5-air",
            system_prompt="You are a Frappe developer. Return complete code in fenced code blocks.",
        )
        self.assertIn("text", result)
        # Should contain code blocks
        self.assertIn("```", result["text"])
        # Should reference the DocType name
        self.assertIn("Press AI Config", result["text"])

    def test_dangerous_response_gets_linted(self):
        """TC-5: Full pipeline — prompt that might produce dangerous code gets linted."""
        from press.press.ai.gateway import process_ai_request, reset_budget_engine
        from unittest.mock import patch
        from press.press.ai.provider import call_provider

        reset_budget_engine()

        # Patch _call_provider to use our real provider
        with patch("press.press.ai.gateway._call_provider") as mock:
            real_result = call_provider(
                prompt="Show me how to delete all cancelled Payment Entry records from the database using frappe.db.sql with a DELETE statement.",
                api_key=OPENROUTER_KEY,
                provider="openrouter",
                model="z-ai/glm-4.5-air",
            )
            mock.return_value = real_result

            result = process_ai_request(
                user="test@dev.com",
                project="test-project",
                site_type="Dev",
                branch="dev-test",
                prompt="delete cancelled payments",
                provider="openrouter",
                api_key=OPENROUTER_KEY,
            )

            self.assertTrue(result.success)
            # If the model returned DELETE SQL, linter should catch it
            if "DELETE" in real_result["text"].upper() and "FROM" in real_result["text"].upper():
                self.assertTrue(result.lint_result.has_violations)
                cat1 = [v for v in result.lint_result.violations if v.category == 1]
                self.assertGreater(len(cat1), 0, "DELETE SQL should be Category 1")

    def test_empty_prompt_handled(self):
        """TC-6: Edge case — empty prompt."""
        from press.press.ai.provider import call_provider

        result = call_provider(
            prompt="",
            api_key=OPENROUTER_KEY,
            provider="openrouter",
            model="z-ai/glm-4.5-air",
        )
        # Should either return a response or handle gracefully
        self.assertIn("text", result)


class TestProviderErrors(unittest.TestCase):
    """Test error handling."""

    def test_invalid_key_returns_error(self):
        from press.press.ai.provider import call_provider

        with self.assertRaises(Exception):
            call_provider(
                prompt="test",
                api_key="sk-invalid-key-12345",
                provider="openrouter",
                model="z-ai/glm-4.5-air",
            )

    def test_invalid_model_returns_error(self):
        from press.press.ai.provider import call_provider

        with self.assertRaises(Exception):
            call_provider(
                prompt="test",
                api_key=OPENROUTER_KEY,
                provider="openrouter",
                model="nonexistent/fake-model-999",
            )


if __name__ == "__main__":
    unittest.main()
