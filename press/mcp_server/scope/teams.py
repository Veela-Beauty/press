"""Keep every MCP call inside the team its token was issued for.

MCP tools run as the token's user, and Frappe skips permission checks for System Users,
so without this a token issued for one team could read and change another team's sites,
benches and servers just by naming them.
"""

import frappe

# One message for "missing" and "another team's": a distinct error for each would tell
# a token which names exist in the other team.
_NOT_VISIBLE = "{doctype} {name!r} was not found, or is not in this token's team"


def not_visible(doctype: str, name: str | None) -> str:
	return _NOT_VISIBLE.format(doctype=doctype, name=name)


def assert_in_team(team: str | None, doctype: str, name: str | None) -> None:
	if not name:
		return
	if not team:
		raise frappe.PermissionError("this token is not tied to a team; issue a new token")
	if frappe.db.get_value(doctype, name, "team") != team:
		raise frappe.PermissionError(not_visible(doctype, name))
