"""Tests for AI context injector — builds context payload for LLM prompts.

The injector collects bench/site metadata and sanitizes it before injection.
Pure Python unit tests — Frappe calls are mocked.
"""

import unittest
from unittest.mock import patch, MagicMock


class TestContextBuilder(unittest.TestCase):
    """Test context payload assembly."""

    def test_builds_basic_context(self):
        from press.press.ai.context_injector import build_context

        ctx = build_context(
            frappe_version="15.103.0",
            installed_apps=["frappe", "erpnext", "accubuild_core"],
            site_name="dev-site.localhost",
        )
        self.assertIn("frappe_version", ctx)
        self.assertEqual(ctx["frappe_version"], "15.103.0")
        self.assertEqual(ctx["installed_apps"], ["frappe", "erpnext", "accubuild_core"])
        self.assertEqual(ctx["site_name"], "dev-site.localhost")

    def test_includes_system_prompt(self):
        from press.press.ai.context_injector import build_context

        ctx = build_context(
            frappe_version="15.103.0",
            installed_apps=["frappe"],
            site_name="dev.localhost",
        )
        self.assertIn("system_prompt", ctx)
        self.assertIsInstance(ctx["system_prompt"], str)
        self.assertIn("Frappe", ctx["system_prompt"])
        self.assertIn("15.103.0", ctx["system_prompt"])

    def test_context_without_optional_fields(self):
        from press.press.ai.context_injector import build_context

        ctx = build_context(
            frappe_version="14.0.0",
            installed_apps=["frappe"],
            site_name="test.localhost",
        )
        self.assertNotIn("error_log", ctx)
        self.assertNotIn("doctype_schema", ctx)

    def test_context_with_error_log(self):
        from press.press.ai.context_injector import build_context

        error = "Traceback (most recent call last):\n  File ...\nKeyError: 'custom_field'"
        ctx = build_context(
            frappe_version="15.0.0",
            installed_apps=["frappe"],
            site_name="dev.localhost",
            error_log=error,
        )
        self.assertIn("error_log", ctx)
        self.assertIn("KeyError", ctx["error_log"])
        self.assertIn("Latest Error", ctx["system_prompt"])

    def test_context_with_doctype_schema(self):
        from press.press.ai.context_injector import build_context

        schema = {
            "name": "Sales Invoice",
            "fields": [
                {"fieldname": "customer", "fieldtype": "Link", "options": "Customer"},
                {"fieldname": "total", "fieldtype": "Currency"},
            ],
        }
        ctx = build_context(
            frappe_version="15.0.0",
            installed_apps=["frappe", "erpnext"],
            site_name="dev.localhost",
            doctype_schema=schema,
        )
        self.assertIn("doctype_schema", ctx)
        self.assertEqual(ctx["doctype_schema"]["name"], "Sales Invoice")
        self.assertIn("Sales Invoice", ctx["system_prompt"])


class TestSiteConfigFilter(unittest.TestCase):
    """Test that site_config is filtered to remove credentials."""

    def test_removes_db_password(self):
        from press.press.ai.context_injector import filter_site_config

        config = {
            "db_name": "my_site",
            "db_password": "secret123",
            "db_host": "localhost",
            "developer_mode": 1,
        }
        filtered = filter_site_config(config)
        self.assertNotIn("db_password", filtered)
        self.assertIn("db_name", filtered)
        self.assertIn("developer_mode", filtered)

    def test_removes_all_secrets(self):
        from press.press.ai.context_injector import filter_site_config

        config = {
            "db_password": "secret",
            "encryption_key": "abc123",
            "secret_key": "xyz",
            "admin_password": "pass",
            "mail_password": "mail_pass",
            "rq_password": "rq_pass",
            "redis_password": "redis",
            "developer_mode": 0,
            "logging": 1,
        }
        filtered = filter_site_config(config)
        # All password/secret/key fields removed
        for key in filtered:
            self.assertNotIn("password", key.lower())
            self.assertNotIn("secret", key.lower())
            self.assertNotIn("encryption_key", key.lower())
        # Safe fields preserved
        self.assertIn("developer_mode", filtered)
        self.assertIn("logging", filtered)

    def test_removes_api_keys(self):
        from press.press.ai.context_injector import filter_site_config

        config = {
            "api_key": "sk-abc123",
            "api_secret": "def456",
            "site_name": "test.localhost",
        }
        filtered = filter_site_config(config)
        self.assertNotIn("api_key", filtered)
        self.assertNotIn("api_secret", filtered)
        self.assertIn("site_name", filtered)

    def test_empty_config(self):
        from press.press.ai.context_injector import filter_site_config

        filtered = filter_site_config({})
        self.assertEqual(filtered, {})

    def test_preserves_safe_fields(self):
        from press.press.ai.context_injector import filter_site_config

        config = {
            "developer_mode": 1,
            "logging": 1,
            "auto_email_id": "noreply@example.com",
            "disable_website_cache": 1,
            "maintenance_mode": 0,
            "server_script_enabled": 1,
            "limits": {"space": 500},
        }
        filtered = filter_site_config(config)
        self.assertEqual(len(filtered), len(config))


class TestErrorLogTruncation(unittest.TestCase):
    """Test that error logs are truncated to safe size."""

    def test_truncates_long_error_log(self):
        from press.press.ai.context_injector import truncate_error_log

        long_log = "ERROR line\n" * 200  # 200 lines
        truncated = truncate_error_log(long_log, max_lines=50)
        lines = truncated.strip().split("\n")
        self.assertLessEqual(len(lines), 51)  # 50 + possible truncation notice

    def test_preserves_short_error_log(self):
        from press.press.ai.context_injector import truncate_error_log

        short_log = "Traceback:\n  File test.py\nKeyError: 'field'"
        truncated = truncate_error_log(short_log, max_lines=50)
        self.assertEqual(truncated, short_log)

    def test_empty_error_log(self):
        from press.press.ai.context_injector import truncate_error_log

        self.assertEqual(truncate_error_log("", max_lines=50), "")

    def test_truncation_keeps_last_lines(self):
        """The most useful info (the actual error) is at the end of the traceback."""
        from press.press.ai.context_injector import truncate_error_log

        lines = [f"Line {i}" for i in range(100)]
        log = "\n".join(lines)
        truncated = truncate_error_log(log, max_lines=10)
        # Should contain the LAST lines (most relevant part of traceback)
        self.assertIn("Line 99", truncated)
        self.assertNotIn("Line 0", truncated)


class TestSystemPromptGeneration(unittest.TestCase):
    """Test the system prompt template."""

    def test_prompt_includes_version(self):
        from press.press.ai.context_injector import generate_system_prompt

        prompt = generate_system_prompt(
            frappe_version="15.103.0",
            installed_apps=["frappe", "erpnext"],
            site_name="dev.localhost",
        )
        self.assertIn("15.103.0", prompt)

    def test_prompt_includes_apps(self):
        from press.press.ai.context_injector import generate_system_prompt

        prompt = generate_system_prompt(
            frappe_version="15.0.0",
            installed_apps=["frappe", "erpnext", "accubuild_core"],
            site_name="dev.localhost",
        )
        self.assertIn("accubuild_core", prompt)

    def test_prompt_includes_safety_rules(self):
        from press.press.ai.context_injector import generate_system_prompt

        prompt = generate_system_prompt(
            frappe_version="15.0.0",
            installed_apps=["frappe"],
            site_name="dev.localhost",
        )
        # Must contain safety instructions
        self.assertIn("DELETE", prompt)
        self.assertIn("production", prompt.lower())

    def test_prompt_with_error_includes_debug_section(self):
        from press.press.ai.context_injector import generate_system_prompt

        prompt = generate_system_prompt(
            frappe_version="15.0.0",
            installed_apps=["frappe"],
            site_name="dev.localhost",
            error_log="KeyError: 'missing_field'",
        )
        self.assertIn("KeyError", prompt)
        self.assertIn("missing_field", prompt)

    def test_prompt_with_doctype_includes_schema(self):
        from press.press.ai.context_injector import generate_system_prompt

        schema = {"name": "ToDo", "fields": [{"fieldname": "description", "fieldtype": "Text"}]}
        prompt = generate_system_prompt(
            frappe_version="15.0.0",
            installed_apps=["frappe"],
            site_name="dev.localhost",
            doctype_schema=schema,
        )
        self.assertIn("ToDo", prompt)


if __name__ == "__main__":
    unittest.main()
