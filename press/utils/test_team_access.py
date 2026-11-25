from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

import press.guards.role_guard  # noqa: F401  press.guards is a namespace package: the patch needs the attribute set
from press.utils import team_access

VALUES = {
	("Site", "quest-dev.example.com", "team"): "team-1",
	("Site", "prime.example.com", "team"): "team-1",
	("Bench", "bench-0080-000001", "group"): "bench-0080",
	("Bench", "bench-0080-000001", "team"): "team-1",
}


class TestEnsureTeamAccess(TestCase):
	def run_check(self, limited=True, allowed=(), user_type="Website User", **target):
		g = MagicMock()
		g.is_restricted.return_value = limited
		g.skip_roles.return_value = False
		g.check.side_effect = lambda doctype, name: (doctype, name) in set(allowed)
		with (
			patch.object(
				frappe,
				"session",
				SimpleNamespace(data=SimpleNamespace(user_type=user_type), user="dev@x.com"),
			),
			patch.object(frappe, "get_roles", return_value=["Press Member"]),
			patch("press.utils.get_current_team", return_value="team-1"),
			patch.object(
				frappe.db,
				"get_value",
				side_effect=lambda dt, name, field, **kw: VALUES.get((dt, name, field)),
			),
			patch("press.guards.role_guard", g),
		):
			team_access.ensure_team_access(**target)
		return g

	def test_listed_site_passes(self):
		self.run_check(allowed=[("Site", "quest-dev.example.com")], site_name="quest-dev.example.com")

	def test_unlisted_site_of_the_same_team_is_refused(self):
		with self.assertRaises(frappe.PermissionError):
			self.run_check(allowed=[("Site", "quest-dev.example.com")], site_name="prime.example.com")

	def test_bench_is_checked_through_its_release_group(self):
		g = self.run_check(allowed=[("Release Group", "bench-0080")], bench_name="bench-0080-000001")
		g.check.assert_called_once_with("Release Group", "bench-0080")

	def test_unlimited_member_passes_without_a_role_check(self):
		g = self.run_check(limited=False, site_name="prime.example.com")
		g.check.assert_not_called()

	def test_system_user_returns_before_any_check(self):
		g = self.run_check(user_type="System User", site_name="prime.example.com")
		g.is_restricted.assert_not_called()

	def test_a_listed_site_cannot_carry_an_unlisted_bench(self):
		with self.assertRaises(frappe.PermissionError):
			self.run_check(
				allowed=[("Site", "quest-dev.example.com")],
				site_name="quest-dev.example.com",
				bench_name="bench-0080-000001",
			)

	def test_other_team_is_refused(self):
		with self.assertRaises(frappe.PermissionError):
			self.run_check(limited=False, site_name="unknown.example.com")
