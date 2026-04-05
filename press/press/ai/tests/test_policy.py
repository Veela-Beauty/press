"""Tests for policy gate — AI usage policy acknowledgment.

TDD — tests written BEFORE implementation.

The policy module:
  - Tracks which users have acknowledged the AI usage policy
  - Blocks AI actions until policy is acknowledged
  - Records acknowledgment timestamp
  - Supports policy version changes (re-acknowledge on new version)

Pure Python — no Frappe dependency.
"""

import unittest
from datetime import datetime, timedelta


class TestPolicyCheck(unittest.TestCase):

    def test_unacknowledged_user_blocked(self):
        from press.press.ai.policy import PolicyGate

        gate = PolicyGate()
        result = gate.check("dev@test.com")
        self.assertFalse(result.allowed)
        self.assertIn("acknowledge", result.message.lower())

    def test_acknowledged_user_allowed(self):
        from press.press.ai.policy import PolicyGate

        gate = PolicyGate()
        gate.acknowledge("dev@test.com")
        result = gate.check("dev@test.com")
        self.assertTrue(result.allowed)

    def test_acknowledge_records_timestamp(self):
        from press.press.ai.policy import PolicyGate

        gate = PolicyGate()
        gate.acknowledge("dev@test.com")
        record = gate.get_acknowledgment("dev@test.com")
        self.assertIsNotNone(record)
        self.assertIn("timestamp", record)
        self.assertIn("version", record)

    def test_different_users_independent(self):
        from press.press.ai.policy import PolicyGate

        gate = PolicyGate()
        gate.acknowledge("dev1@test.com")
        self.assertTrue(gate.check("dev1@test.com").allowed)
        self.assertFalse(gate.check("dev2@test.com").allowed)


class TestPolicyVersioning(unittest.TestCase):

    def test_new_version_requires_reacknowledge(self):
        from press.press.ai.policy import PolicyGate

        gate = PolicyGate(current_version="1.0")
        gate.acknowledge("dev@test.com")
        self.assertTrue(gate.check("dev@test.com").allowed)

        # Policy updated
        gate.current_version = "2.0"
        result = gate.check("dev@test.com")
        self.assertFalse(result.allowed)
        self.assertIn("updated", result.message.lower())

    def test_reacknowledge_updates_version(self):
        from press.press.ai.policy import PolicyGate

        gate = PolicyGate(current_version="1.0")
        gate.acknowledge("dev@test.com")
        gate.current_version = "2.0"
        gate.acknowledge("dev@test.com")
        record = gate.get_acknowledgment("dev@test.com")
        self.assertEqual(record["version"], "2.0")


class TestPolicyRules(unittest.TestCase):

    def test_default_rules(self):
        from press.press.ai.policy import POLICY_RULES

        self.assertIsInstance(POLICY_RULES, list)
        self.assertGreater(len(POLICY_RULES), 0)
        # Each rule has text and icon
        for rule in POLICY_RULES:
            self.assertIn("text", rule)
            self.assertIn("icon", rule)

    def test_rules_cover_key_areas(self):
        from press.press.ai.policy import POLICY_RULES

        texts = " ".join(r["text"].lower() for r in POLICY_RULES)
        self.assertIn("destructive", texts)
        self.assertIn("production", texts)
        self.assertIn("review", texts)


class TestPolicySerialization(unittest.TestCase):

    def test_get_status_for_user(self):
        from press.press.ai.policy import PolicyGate

        gate = PolicyGate()
        gate.acknowledge("dev@test.com")
        status = gate.get_status("dev@test.com")
        self.assertTrue(status["acknowledged"])
        self.assertEqual(status["user"], "dev@test.com")

    def test_get_status_unacknowledged(self):
        from press.press.ai.policy import PolicyGate

        gate = PolicyGate()
        status = gate.get_status("new@test.com")
        self.assertFalse(status["acknowledged"])
        self.assertIn("rules", status)


if __name__ == "__main__":
    unittest.main()
