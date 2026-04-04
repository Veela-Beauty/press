"""Tests for token budget engine — per-user caps + project pools.

Hybrid budget: both user cap AND project pool enforced simultaneously.
Optimistic reservation prevents race conditions.

Pure Python — uses in-memory state for testing.
"""

import unittest


class TestBudgetCheck(unittest.TestCase):
    """Test budget enforcement before API calls."""

    def test_allows_when_under_budget(self):
        from press.press.ai.token_budget import BudgetEngine

        engine = BudgetEngine()
        engine.set_user_cap("dev@test.com", daily_cap=100_000)
        engine.set_project_pool("project-1", daily_pool=500_000)
        result = engine.check_budget("dev@test.com", "project-1", estimated_tokens=5000)
        self.assertTrue(result.allowed)
        self.assertFalse(result.warning)

    def test_blocks_when_user_cap_exceeded(self):
        from press.press.ai.token_budget import BudgetEngine

        engine = BudgetEngine()
        engine.set_user_cap("dev@test.com", daily_cap=10_000)
        engine.record_usage("dev@test.com", "project-1", tokens=10_000)
        result = engine.check_budget("dev@test.com", "project-1", estimated_tokens=1000)
        self.assertFalse(result.allowed)
        self.assertIn("user", result.reason.lower())

    def test_blocks_when_project_pool_exceeded(self):
        from press.press.ai.token_budget import BudgetEngine

        engine = BudgetEngine()
        engine.set_user_cap("dev@test.com", daily_cap=500_000)
        engine.set_project_pool("project-1", daily_pool=20_000)
        engine.record_usage("dev@test.com", "project-1", tokens=20_000)
        result = engine.check_budget("dev@test.com", "project-1", estimated_tokens=1000)
        self.assertFalse(result.allowed)
        self.assertIn("project", result.reason.lower())

    def test_warns_at_80_percent(self):
        from press.press.ai.token_budget import BudgetEngine

        engine = BudgetEngine()
        engine.set_user_cap("dev@test.com", daily_cap=100_000)
        engine.set_project_pool("project-1", daily_pool=500_000)
        engine.record_usage("dev@test.com", "project-1", tokens=85_000)
        result = engine.check_budget("dev@test.com", "project-1", estimated_tokens=1000)
        self.assertTrue(result.allowed)
        self.assertTrue(result.warning)

    def test_zero_cap_means_unlimited(self):
        from press.press.ai.token_budget import BudgetEngine

        engine = BudgetEngine()
        engine.set_user_cap("admin@test.com", daily_cap=0)
        engine.set_project_pool("project-1", daily_pool=0)
        engine.record_usage("admin@test.com", "project-1", tokens=999_999)
        result = engine.check_budget("admin@test.com", "project-1", estimated_tokens=50_000)
        self.assertTrue(result.allowed)
        self.assertFalse(result.warning)

    def test_default_cap_when_not_set(self):
        from press.press.ai.token_budget import BudgetEngine

        engine = BudgetEngine(default_user_cap=100_000, default_project_pool=500_000)
        result = engine.check_budget("new@test.com", "new-project", estimated_tokens=5000)
        self.assertTrue(result.allowed)


class TestOptimisticReservation(unittest.TestCase):
    """Test token reservation to prevent race conditions."""

    def test_reserve_then_reconcile(self):
        from press.press.ai.token_budget import BudgetEngine

        engine = BudgetEngine()
        engine.set_user_cap("dev@test.com", daily_cap=100_000)
        engine.set_project_pool("project-1", daily_pool=500_000)

        # Reserve 10K tokens
        reservation = engine.reserve("dev@test.com", "project-1", estimated_tokens=10_000)
        self.assertIsNotNone(reservation.reservation_id)

        # Check budget — reserved tokens should count against cap
        result = engine.check_budget("dev@test.com", "project-1", estimated_tokens=91_000)
        self.assertFalse(result.allowed)  # 10K reserved + 91K > 100K cap

        # Reconcile with actual usage (was only 7K)
        engine.reconcile(reservation.reservation_id, actual_tokens=7_000)
        # Now 7K used, 93K remaining
        result = engine.check_budget("dev@test.com", "project-1", estimated_tokens=91_000)
        self.assertTrue(result.allowed)

    def test_cancel_reservation(self):
        from press.press.ai.token_budget import BudgetEngine

        engine = BudgetEngine()
        engine.set_user_cap("dev@test.com", daily_cap=50_000)
        engine.set_project_pool("project-1", daily_pool=500_000)

        reservation = engine.reserve("dev@test.com", "project-1", estimated_tokens=40_000)
        # Cancel — API call failed
        engine.cancel_reservation(reservation.reservation_id)
        # Full budget available again
        result = engine.check_budget("dev@test.com", "project-1", estimated_tokens=49_000)
        self.assertTrue(result.allowed)


class TestUsageTracking(unittest.TestCase):
    """Test usage recording and querying."""

    def test_get_user_usage_today(self):
        from press.press.ai.token_budget import BudgetEngine

        engine = BudgetEngine()
        engine.record_usage("dev@test.com", "project-1", tokens=5000)
        engine.record_usage("dev@test.com", "project-1", tokens=3000)
        usage = engine.get_user_usage("dev@test.com")
        self.assertEqual(usage, 8000)

    def test_get_project_usage_today(self):
        from press.press.ai.token_budget import BudgetEngine

        engine = BudgetEngine()
        engine.record_usage("dev1@test.com", "project-1", tokens=5000)
        engine.record_usage("dev2@test.com", "project-1", tokens=3000)
        usage = engine.get_project_usage("project-1")
        self.assertEqual(usage, 8000)

    def test_usage_includes_cost_estimate(self):
        from press.press.ai.token_budget import BudgetEngine

        engine = BudgetEngine()
        engine.record_usage(
            "dev@test.com", "project-1",
            tokens=10_000,
            input_tokens=8_000,
            output_tokens=2_000,
            provider="anthropic",
            model="claude-sonnet-4-20250514",
        )
        usage = engine.get_usage_detail("dev@test.com", "project-1")
        self.assertEqual(usage["total_tokens"], 10_000)
        self.assertGreater(usage["estimated_cost"], 0)


class TestBudgetResult(unittest.TestCase):
    """Test BudgetResult data structure."""

    def test_result_fields(self):
        from press.press.ai.token_budget import BudgetEngine

        engine = BudgetEngine(default_user_cap=100_000, default_project_pool=500_000)
        result = engine.check_budget("dev@test.com", "project-1", estimated_tokens=5000)
        self.assertIsInstance(result.allowed, bool)
        self.assertIsInstance(result.warning, bool)
        self.assertIsInstance(result.user_remaining, int)
        self.assertIsInstance(result.project_remaining, int)
        self.assertIsInstance(result.reason, str)


if __name__ == "__main__":
    unittest.main()
