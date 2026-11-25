from unittest import TestCase
from unittest.mock import patch

import frappe

from press.api.admin_panel import DEFAULT_FEATURES
from press.press.doctype.team import press_role_bridge as bridge
from press.press.doctype.team.team_roles import PRESS_ROLES, normalize_press_role

SCOPE = ("all_servers", "all_sites", "all_release_groups")


class TestDevopsLevels(TestCase):
	def test_old_name_reads_as_devops_l2(self):
		self.assertEqual(normalize_press_role("DevOps Admin"), "DevOps L2")
		self.assertNotIn("DevOps Admin", PRESS_ROLES)

	def test_l1_sits_below_l2(self):
		self.assertLess(PRESS_ROLES["DevOps L1"]["level"], PRESS_ROLES["DevOps L2"]["level"])

	def test_l1_has_l2_rights_but_sees_only_its_list_and_no_server_creation(self):
		l1, l2 = bridge.ROLE_TO_FLAGS["DevOps L1"], bridge.ROLE_TO_FLAGS["DevOps L2"]
		self.assertTrue(all(l1[f] == 0 for f in SCOPE) and all(l2[f] == 1 for f in SCOPE))
		differ = {f for f in l2 if l1[f] != l2[f]}
		self.assertEqual(differ, {*SCOPE, "allow_server_creation"})

	def test_l1_never_gets_server_level_features(self):
		for feature in ("servers", "binlog_browser", "db_analyzer", "daman_backup", "security_portal"):
			self.assertNotIn("DevOps L1", DEFAULT_FEATURES[feature]["roles"], feature)
		self.assertIn("DevOps L1", DEFAULT_FEATURES["ssh_access"]["roles"])

	def test_old_titled_role_is_renamed_in_place(self):
		with (
			patch.object(frappe.db, "get_value", return_value="role-1") as get_value,
			patch.object(frappe.db, "set_value") as set_value,
		):
			self.assertEqual(bridge._rename_legacy_role("team-1", "DevOps L2"), "role-1")
		get_value.assert_called_once_with("Press Role", {"team": "team-1", "title": "DevOps Admin"}, "name")
		set_value.assert_called_once_with("Press Role", "role-1", "title", "DevOps L2", update_modified=False)

	def test_no_rename_for_a_title_that_was_never_renamed(self):
		with patch.object(frappe.db, "get_value") as get_value:
			self.assertIsNone(bridge._rename_legacy_role("team-1", "DevOps L1"))
		get_value.assert_not_called()
