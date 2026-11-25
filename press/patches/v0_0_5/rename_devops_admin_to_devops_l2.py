"""DevOps Admin becomes DevOps L2, and DevOps L1 joins the role list (0.7.70).

Team Member.press_role is a Select custom field whose options were written once (team_roles.setup_role_field), so the
new list is written here. Members holding the old name move to the new one, and each team's Press Role titled the old
name is renamed in place, so its members, resources and docname stay. Idempotent.
"""

import frappe

from press.press.doctype.team.press_role_bridge import LEGACY_ROLE_TITLES, _rename_legacy_role
from press.press.doctype.team.team_roles import PRESS_ROLE_OPTIONS


def execute():
	if frappe.db.exists("Custom Field", "Team Member-press_role"):
		frappe.db.set_value("Custom Field", "Team Member-press_role", "options", PRESS_ROLE_OPTIONS)
	for old, new in LEGACY_ROLE_TITLES.items():
		for name in frappe.get_all("Team Member", {"press_role": old}, pluck="name"):
			frappe.db.set_value("Team Member", name, "press_role", new, update_modified=False)
		for team in frappe.get_all("Press Role", {"title": old}, pluck="team"):
			if not frappe.db.exists("Press Role", {"team": team, "title": new}):
				_rename_legacy_role(team, new)
	frappe.clear_cache(doctype="Team Member")
