"""Tests for site scope guard — enforces dev/staging/prod AI behavior rules.

dev-*: AI can write (after diff preview)
staging: AI can write only with explicit confirm
production: HARD BLOCK — read-only, apply hidden

Pure Python — no Frappe dependency.
"""

import unittest


class TestScopeGuardAllow(unittest.TestCase):
    """Test that dev sites allow AI actions."""

    def test_dev_site_allows_write(self):
        from press.press.ai.site_scope_guard import check_scope

        result = check_scope(site_type="Dev", action="write_file")
        self.assertTrue(result.allowed)
        self.assertFalse(result.needs_confirm)

    def test_dev_site_allows_execute(self):
        from press.press.ai.site_scope_guard import check_scope

        result = check_scope(site_type="Dev", action="bench_execute")
        self.assertTrue(result.allowed)

    def test_dev_site_allows_git_commit(self):
        from press.press.ai.site_scope_guard import check_scope

        result = check_scope(site_type="Dev", action="git_commit")
        self.assertTrue(result.allowed)


class TestScopeGuardStaging(unittest.TestCase):
    """Test that staging sites require explicit confirmation."""

    def test_staging_requires_confirm_for_write(self):
        from press.press.ai.site_scope_guard import check_scope

        result = check_scope(site_type="Staging", action="write_file")
        self.assertTrue(result.allowed)
        self.assertTrue(result.needs_confirm)
        self.assertIn("confirm", result.message.lower())

    def test_staging_requires_confirm_for_execute(self):
        from press.press.ai.site_scope_guard import check_scope

        result = check_scope(site_type="Staging", action="bench_execute")
        self.assertTrue(result.allowed)
        self.assertTrue(result.needs_confirm)

    def test_staging_allows_read(self):
        from press.press.ai.site_scope_guard import check_scope

        result = check_scope(site_type="Staging", action="read")
        self.assertTrue(result.allowed)
        self.assertFalse(result.needs_confirm)


class TestScopeGuardProduction(unittest.TestCase):
    """Test that production sites are hard-blocked."""

    def test_production_blocks_write(self):
        from press.press.ai.site_scope_guard import check_scope

        result = check_scope(site_type="Production", action="write_file")
        self.assertFalse(result.allowed)
        self.assertIn("production", result.message.lower())

    def test_production_blocks_execute(self):
        from press.press.ai.site_scope_guard import check_scope

        result = check_scope(site_type="Production", action="bench_execute")
        self.assertFalse(result.allowed)

    def test_production_blocks_git_commit(self):
        from press.press.ai.site_scope_guard import check_scope

        result = check_scope(site_type="Production", action="git_commit")
        self.assertFalse(result.allowed)

    def test_production_allows_read(self):
        from press.press.ai.site_scope_guard import check_scope

        result = check_scope(site_type="Production", action="read")
        self.assertTrue(result.allowed)
        self.assertFalse(result.needs_confirm)

    def test_production_blocks_demo_data(self):
        from press.press.ai.site_scope_guard import check_scope

        result = check_scope(site_type="Production", action="demo_data")
        self.assertFalse(result.allowed)


class TestScopeGuardDemo(unittest.TestCase):
    """Demo sites behave like Dev."""

    def test_demo_allows_write(self):
        from press.press.ai.site_scope_guard import check_scope

        result = check_scope(site_type="Demo", action="write_file")
        self.assertTrue(result.allowed)
        self.assertFalse(result.needs_confirm)


class TestScopeGuardBranchCheck(unittest.TestCase):
    """AI commits only allowed on dev-* branches."""

    def test_dev_branch_allows_commit(self):
        from press.press.ai.site_scope_guard import check_branch

        result = check_branch("dev-payment-fix")
        self.assertTrue(result.allowed)

    def test_main_branch_blocks_commit(self):
        from press.press.ai.site_scope_guard import check_branch

        result = check_branch("main")
        self.assertFalse(result.allowed)
        self.assertIn("dev-", result.message)

    def test_master_branch_blocks_commit(self):
        from press.press.ai.site_scope_guard import check_branch

        result = check_branch("master")
        self.assertFalse(result.allowed)

    def test_feature_branch_blocks_commit(self):
        from press.press.ai.site_scope_guard import check_branch

        result = check_branch("feature/new-module")
        self.assertFalse(result.allowed)

    def test_develop_branch_allows_commit(self):
        """develop is not a protected branch — allowed."""
        from press.press.ai.site_scope_guard import check_branch

        result = check_branch("develop")
        self.assertFalse(result.allowed)

    def test_dev_prefix_various(self):
        from press.press.ai.site_scope_guard import check_branch

        self.assertTrue(check_branch("dev-fix").allowed)
        self.assertTrue(check_branch("dev-eslam-test").allowed)
        self.assertTrue(check_branch("dev-v15-migration").allowed)


class TestScopeResult(unittest.TestCase):
    """Test ScopeResult data structure."""

    def test_result_has_all_fields(self):
        from press.press.ai.site_scope_guard import check_scope

        result = check_scope(site_type="Dev", action="write_file")
        self.assertIsInstance(result.allowed, bool)
        self.assertIsInstance(result.needs_confirm, bool)
        self.assertIsInstance(result.message, str)

    def test_unknown_site_type_defaults_to_blocked(self):
        from press.press.ai.site_scope_guard import check_scope

        result = check_scope(site_type="Unknown", action="write_file")
        self.assertFalse(result.allowed)

    def test_unknown_action_defaults_to_blocked(self):
        from press.press.ai.site_scope_guard import check_scope

        result = check_scope(site_type="Dev", action="unknown_action")
        self.assertFalse(result.allowed)


if __name__ == "__main__":
    unittest.main()
