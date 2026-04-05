"""Tests for rollback_trigger — Press-side proxy to site rollback API.

TDD — tests written BEFORE implementation.

The rollback_trigger module:
  - Builds agent commands for rollback operations
  - Validates site type (only dev/staging, never production)
  - Generates enable_versioning, rollback, and cleanup commands
  - Pure Python command builder — actual agent calls are separate

Press controls WHEN rollback happens, Sanad AI controls HOW.
"""

import unittest


class TestRollbackCommandBuilder(unittest.TestCase):

    def test_build_enable_versioning_command(self):
        from press.press.ai.rollback_trigger import build_enable_versioning_cmd

        cmd = build_enable_versioning_cmd(
            site_name="dev-site.sandbox.com",
            doctypes=["Payment Entry", "Sales Order"],
        )
        self.assertIn("enable_versioning", cmd["method"])
        self.assertEqual(cmd["site_name"], "dev-site.sandbox.com")
        self.assertEqual(len(cmd["doctypes"]), 2)

    def test_build_rollback_command(self):
        from press.press.ai.rollback_trigger import build_rollback_cmd

        cmd = build_rollback_cmd(
            site_name="dev-site.sandbox.com",
            session_id="rs_abc123",
        )
        self.assertIn("rollback", cmd["method"])
        self.assertEqual(cmd["session_id"], "rs_abc123")

    def test_build_cleanup_command(self):
        from press.press.ai.rollback_trigger import build_cleanup_cmd

        cmd = build_cleanup_cmd(site_name="dev-site.sandbox.com")
        self.assertIn("cleanup", cmd["method"])


class TestSiteTypeValidation(unittest.TestCase):

    def test_dev_site_allowed(self):
        from press.press.ai.rollback_trigger import validate_rollback_site

        result = validate_rollback_site("Dev")
        self.assertTrue(result.allowed)

    def test_staging_site_allowed_with_confirm(self):
        from press.press.ai.rollback_trigger import validate_rollback_site

        result = validate_rollback_site("Staging")
        self.assertTrue(result.allowed)
        self.assertTrue(result.needs_confirm)

    def test_production_site_blocked(self):
        from press.press.ai.rollback_trigger import validate_rollback_site

        result = validate_rollback_site("Production")
        self.assertFalse(result.allowed)
        self.assertIn("production", result.message.lower())

    def test_unknown_site_type_blocked(self):
        from press.press.ai.rollback_trigger import validate_rollback_site

        result = validate_rollback_site("Unknown")
        self.assertFalse(result.allowed)


class TestRollbackPayload(unittest.TestCase):

    def test_full_rollback_payload(self):
        from press.press.ai.rollback_trigger import build_full_rollback_payload

        payload = build_full_rollback_payload(
            site_name="dev-site.sandbox.com",
            session_id="rs_abc123",
            include_git_revert=True,
            bench_name="bench-0015-000007-press-f1",
            app_name="accubuild_core",
            commit_hash="def456",
        )
        self.assertEqual(payload["site_name"], "dev-site.sandbox.com")
        self.assertEqual(payload["session_id"], "rs_abc123")
        self.assertTrue(payload["include_git_revert"])
        self.assertEqual(payload["commit_hash"], "def456")

    def test_db_only_rollback_payload(self):
        from press.press.ai.rollback_trigger import build_full_rollback_payload

        payload = build_full_rollback_payload(
            site_name="dev-site.sandbox.com",
            session_id="rs_abc123",
        )
        self.assertFalse(payload.get("include_git_revert", False))
        self.assertIsNone(payload.get("commit_hash"))


if __name__ == "__main__":
    unittest.main()
