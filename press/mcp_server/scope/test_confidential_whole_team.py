from unittest import TestCase
from unittest.mock import patch

import frappe

from press.mcp_server.scope.confidential import assert_team_unlocked

GET_ALL = "press.mcp_server.scope.confidential.frappe.get_all"


class TestAssertTeamUnlocked(TestCase):
	def run_with(self, confidential, unlocked):
		with (
			patch(GET_ALL, return_value=confidential) as get_all,
			patch.object(frappe.local, "mcp_token_confidential_sites", unlocked, create=True),
		):
			assert_team_unlocked("team-1")
		return get_all

	def test_names_every_locked_site_and_why(self):
		with self.assertRaises(frappe.PermissionError) as raised:
			self.run_with(["b.example.com", "a.example.com", "c.example.com"], ["c.example.com"])
		message = str(raised.exception)
		self.assertIn("reaches every site of your team", message)
		self.assertIn("a.example.com, b.example.com.", message)
		self.assertNotIn("c.example.com", message)

	def test_all_unlocked_passes(self):
		self.run_with(["a.example.com"], ["a.example.com"])

	def test_no_confidential_site_passes(self):
		self.run_with([], None)

	def test_reads_only_the_teams_live_confidential_sites(self):
		get_all = self.run_with([], None)
		self.assertEqual(
			get_all.call_args.kwargs["filters"],
			{"team": "team-1", "is_confidential": 1, "status": ("!=", "Archived")},
		)
