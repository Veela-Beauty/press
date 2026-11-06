import unittest
from unittest.mock import Mock, patch

import frappe

from press.press.doctype.team.press_role_bridge import require_team_role_flag

OWNER = "owner@example.com"
MEMBER = "member@example.com"


def _raise(msg, exc=Exception):
	raise exc(msg)


class TestRequireTeamRoleFlag(unittest.TestCase):
	"""Pure-mock: no site, no DB. The dev toggles let the team owner through;
	every other gate (confidential, admin PIN) still needs a real role flag."""

	def _call(self, user, owner_passes, roles=(), role_rows=()):
		db = Mock()
		db.get_value.return_value = OWNER
		db.sql.return_value = list(role_rows)
		with (
			patch.object(frappe, "session", Mock(user=user)),
			patch.object(frappe, "get_roles", return_value=list(roles)),
			patch.object(frappe, "db", db),
			patch.object(frappe, "throw", side_effect=_raise),
		):
			require_team_role_flag("team1", "admin_access", owner_passes=owner_passes)
		return db

	def test_owner_passes_when_opted_in(self):
		db = self._call(OWNER, owner_passes=True)
		db.sql.assert_not_called()

	def test_owner_without_role_denied_by_default(self):
		with self.assertRaises(frappe.PermissionError):
			self._call(OWNER, owner_passes=False)

	def test_non_owner_without_role_denied_even_when_opted_in(self):
		with self.assertRaises(frappe.PermissionError):
			self._call(MEMBER, owner_passes=True)

	def test_member_with_role_flag_passes(self):
		self._call(MEMBER, owner_passes=False, role_rows=[("role1",)])

	def test_system_manager_passes(self):
		db = self._call(MEMBER, owner_passes=False, roles=["System Manager"])
		db.get_value.assert_not_called()
