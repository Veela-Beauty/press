"""Tests for site_scope_guard — kept from original, moved to tests/ folder."""

import unittest


class TestSiteScope(unittest.TestCase):

    def test_dev_allows_write(self):
        from press.press.ai.site_scope_guard import check_scope
        r = check_scope("Dev", "write_file")
        self.assertTrue(r.allowed)
        self.assertFalse(r.needs_confirm)

    def test_staging_write_needs_confirm(self):
        from press.press.ai.site_scope_guard import check_scope
        r = check_scope("Staging", "write_file")
        self.assertTrue(r.allowed)
        self.assertTrue(r.needs_confirm)

    def test_production_blocks_write(self):
        from press.press.ai.site_scope_guard import check_scope
        r = check_scope("Production", "write_file")
        self.assertFalse(r.allowed)

    def test_production_allows_read(self):
        from press.press.ai.site_scope_guard import check_scope
        r = check_scope("Production", "read")
        self.assertTrue(r.allowed)

    def test_unknown_action_blocked(self):
        from press.press.ai.site_scope_guard import check_scope
        r = check_scope("Dev", "hack_server")
        self.assertFalse(r.allowed)

    def test_unknown_site_type_blocked(self):
        from press.press.ai.site_scope_guard import check_scope
        r = check_scope("Mystery", "read")
        self.assertFalse(r.allowed)

    def test_dev_branch_allowed(self):
        from press.press.ai.site_scope_guard import check_branch
        r = check_branch("dev-payment-fix")
        self.assertTrue(r.allowed)

    def test_main_branch_blocked(self):
        from press.press.ai.site_scope_guard import check_branch
        r = check_branch("main")
        self.assertFalse(r.allowed)


if __name__ == "__main__":
    unittest.main()
