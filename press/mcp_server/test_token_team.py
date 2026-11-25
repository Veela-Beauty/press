from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe

from press.mcp_server import auth


def on_team(user_type="Website User", owner="owner@x.com", members=()):
	values = {("User", "dev@x.com", "user_type"): user_type, ("Team", "team-1", "user"): owner}
	return (
		patch.object(
			frappe.db, "get_value", side_effect=lambda dt, name, field, **kw: values.get((dt, name, field))
		),
		patch.object(frappe.db, "exists", side_effect=lambda dt, filters: filters.get("user") in members),
	)


class TestTokenTeam(TestCase):
	def still(self, **kwargs):
		get_value, exists = on_team(**kwargs)
		with get_value, exists:
			return auth._still_on_team("dev@x.com", "team-1")

	def test_member_is_on_the_team(self):
		self.assertTrue(self.still(members={"dev@x.com"}))

	def test_owner_is_on_the_team(self):
		self.assertTrue(self.still(owner="dev@x.com"))

	def test_system_user_works_across_teams(self):
		self.assertTrue(self.still(user_type="System User"))

	def test_removed_member_is_refused(self):
		get_value, exists = on_team()
		with get_value, exists, self.assertRaises(frappe.PermissionError) as raised:
			auth._assert_token_team(SimpleNamespace(user="dev@x.com", team="team-1"))
		self.assertIn("no longer on its team", str(raised.exception))

	def test_token_without_a_team_is_refused(self):
		with self.assertRaises(frappe.PermissionError):
			auth._assert_token_team(SimpleNamespace(user="dev@x.com", team=None))
