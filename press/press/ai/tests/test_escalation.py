"""Tests for escalation state machine — manages Cat 1/2 violation escalations.

TDD — tests written BEFORE implementation.

The escalation module:
  - Tracks escalation lifecycle: created → pending_tl → pending_admin → resolved/rejected
  - Validates state transitions (can't skip steps)
  - Records decision history with timestamps and reasons
  - Cat 1: always requires admin decision, AI never executes
  - Cat 2: TL can approve, admin reviews if TL rejects

Pure Python state machine — no Frappe dependency.
"""

import unittest
from datetime import datetime


class TestEscalationCreation(unittest.TestCase):

    def test_create_escalation(self):
        from press.press.ai.escalation import Escalation

        esc = Escalation(
            violation_category=1,
            pattern="DROP TABLE",
            description="DROP TABLE detected in AI response",
            user="dev@test.com",
            session_id="sess_abc",
            site_name="dev-site.example.com",
        )
        self.assertEqual(esc.status, "pending_tl")
        self.assertEqual(esc.violation_category, 1)
        self.assertEqual(esc.user, "dev@test.com")
        self.assertIsNotNone(esc.created_at)

    def test_create_requires_reason_field(self):
        from press.press.ai.escalation import Escalation

        esc = Escalation(
            violation_category=1,
            pattern="DROP TABLE",
            description="test",
            user="dev@test.com",
            session_id="s1",
            site_name="site.com",
        )
        # reason is empty at creation — user must fill before submitting
        self.assertEqual(esc.reason, "")


class TestEscalationStateMachine(unittest.TestCase):

    def _make(self, cat=1):
        from press.press.ai.escalation import Escalation
        return Escalation(
            violation_category=cat, pattern="test", description="test",
            user="dev@test.com", session_id="s1", site_name="site.com",
        )

    def test_submit_requires_reason(self):
        from press.press.ai.escalation import EscalationError
        esc = self._make()
        with self.assertRaises(EscalationError):
            esc.submit(reason="")

    def test_submit_with_reason_sets_pending_tl(self):
        esc = self._make()
        esc.submit(reason="Need to reset the table for testing")
        self.assertEqual(esc.status, "pending_tl")
        self.assertEqual(esc.reason, "Need to reset the table for testing")

    def test_tl_approve(self):
        esc = self._make()
        esc.submit(reason="test reason")
        esc.tl_decide(approved=True, tl_user="tl@test.com", tl_reason="Confirmed safe")
        self.assertEqual(esc.status, "pending_admin")
        self.assertEqual(esc.tl_user, "tl@test.com")

    def test_tl_reject(self):
        esc = self._make()
        esc.submit(reason="test")
        esc.tl_decide(approved=False, tl_user="tl@test.com", tl_reason="Not needed")
        self.assertEqual(esc.status, "rejected")

    def test_admin_approve_cat1(self):
        esc = self._make(cat=1)
        esc.submit(reason="test")
        esc.tl_decide(approved=True, tl_user="tl@test.com", tl_reason="ok")
        esc.admin_decide(approved=True, admin_user="admin@test.com", admin_reason="Manual execution approved")
        self.assertEqual(esc.status, "approved_manual")
        # Cat 1 = manual only, never auto-execute
        self.assertTrue(esc.manual_only)

    def test_admin_approve_cat2(self):
        esc = self._make(cat=2)
        esc.submit(reason="test")
        esc.tl_decide(approved=True, tl_user="tl@test.com", tl_reason="ok")
        esc.admin_decide(approved=True, admin_user="admin@test.com", admin_reason="Go ahead")
        self.assertEqual(esc.status, "approved")
        self.assertFalse(esc.manual_only)

    def test_admin_reject(self):
        esc = self._make()
        esc.submit(reason="test")
        esc.tl_decide(approved=True, tl_user="tl@test.com", tl_reason="ok")
        esc.admin_decide(approved=False, admin_user="admin@test.com", admin_reason="Too risky")
        self.assertEqual(esc.status, "rejected")

    def test_cannot_skip_tl(self):
        from press.press.ai.escalation import EscalationError
        esc = self._make()
        esc.submit(reason="test")
        with self.assertRaises(EscalationError):
            esc.admin_decide(approved=True, admin_user="admin@test.com", admin_reason="skip")

    def test_cannot_decide_after_rejected(self):
        from press.press.ai.escalation import EscalationError
        esc = self._make()
        esc.submit(reason="test")
        esc.tl_decide(approved=False, tl_user="tl@test.com", tl_reason="no")
        with self.assertRaises(EscalationError):
            esc.admin_decide(approved=True, admin_user="a@t.com", admin_reason="try")


class TestEscalationHistory(unittest.TestCase):

    def test_history_records_all_decisions(self):
        from press.press.ai.escalation import Escalation

        esc = Escalation(
            violation_category=2, pattern="bulk delete", description="test",
            user="dev@test.com", session_id="s1", site_name="site.com",
        )
        esc.submit(reason="need bulk cleanup")
        esc.tl_decide(approved=True, tl_user="tl@test.com", tl_reason="approved")
        esc.admin_decide(approved=True, admin_user="admin@test.com", admin_reason="go")

        history = esc.get_history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["action"], "submitted")
        self.assertEqual(history[1]["action"], "tl_approved")
        self.assertEqual(history[2]["action"], "admin_approved")

    def test_history_includes_timestamps(self):
        from press.press.ai.escalation import Escalation

        esc = Escalation(
            violation_category=1, pattern="test", description="test",
            user="u@t.com", session_id="s1", site_name="s.com",
        )
        esc.submit(reason="test")
        history = esc.get_history()
        self.assertIn("timestamp", history[0])


class TestEscalationSerialization(unittest.TestCase):

    def test_to_dict(self):
        from press.press.ai.escalation import Escalation

        esc = Escalation(
            violation_category=1, pattern="DROP TABLE", description="test",
            user="dev@test.com", session_id="sess_abc", site_name="site.com",
        )
        esc.submit(reason="need it")
        d = esc.to_dict()
        self.assertEqual(d["status"], "pending_tl")
        self.assertEqual(d["violation_category"], 1)
        self.assertEqual(d["user"], "dev@test.com")
        self.assertEqual(d["reason"], "need it")
        self.assertIn("created_at", d)
        self.assertIn("history", d)


if __name__ == "__main__":
    unittest.main()
