"""mint_dashboard_login_url logs in the team's test user, never the token's human.

The tool mints a dashboard session for whoever it runs as. Run as the token's user, a
System Manager, that session saw every team and the Desk, undoing the team scope of the
token that asked for it. A team names one low-privilege account for browser tests by
giving it the role below.
"""

from __future__ import annotations

import frappe

TEST_USER_ROLE = "Press MCP Test User"
_HOW = (
	f"give exactly one Website User of this team the {TEST_USER_ROLE!r} role "
	"(Desk > User > Roles); that account must not belong to any other team"
)


def login_user_for(team: str) -> str:
	members = frappe.get_all("Team Member", filters={"parent": team, "parenttype": "Team"}, pluck="user")
	with_role = set(
		frappe.get_all(
			"Has Role",
			filters={"parent": ["in", members or [""]], "parenttype": "User", "role": TEST_USER_ROLE},
			pluck="parent",
		)
	)
	candidates = frappe.get_all(
		"User",
		filters={"name": ["in", list(with_role) or [""]], "enabled": 1, "user_type": "Website User"},
		pluck="name",
	)
	if len(candidates) != 1:
		found = "no test user" if not candidates else f"{len(candidates)} test users"
		raise frappe.PermissionError(f"this team has {found} for dashboard logins; {_HOW}")
	user = candidates[0]
	if frappe.db.count("Team Member", {"user": user, "parenttype": "Team", "parent": ["!=", team]}):
		raise frappe.PermissionError(f"test user {user!r} also belongs to another team; {_HOW}")
	return user
