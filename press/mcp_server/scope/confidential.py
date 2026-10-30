"""Confidential sites: an MCP token reaches one only if the Admin PIN unlocked it when the token was issued.

A token's Allowed Sites list is self-service, so naming a site is not enough. The PIN is typed
by the human in the Issue Token dialog; the agent holding the token never sees it.
"""

from __future__ import annotations

import frappe


def confidential_sites(names, team: str | None = None) -> list[str]:
	names = [n for n in (names or ()) if n]
	if not names:
		return []
	filters = {"name": ("in", names), "is_confidential": 1}
	if team:
		filters["team"] = team
	return frappe.get_all("Site", filters=filters, pluck="name")


def unlock(allowed_sites, pin: str | None, reason: str, team: str | None) -> list[str]:
	"""Check the Admin PIN for the confidential sites a new token names, and return them.

	Only the token's own team counts: another team's site name gets no PIN prompt, so the
	prompt cannot reveal which foreign sites exist or are confidential.
	"""
	if not team:
		return []
	locked = confidential_sites(allowed_sites, team)
	if locked:
		# Same gate as Login as Administrator: global PIN, 3-strike lockout, alert mail.
		frappe.get_doc("Site", locked[0])._check_confidential_pin(pin, reason)
	return locked


def assert_team_unlocked(team: str) -> None:
	assert_unlocked(
		frappe.get_all(
			"Site", filters={"team": team, "is_confidential": 1, "status": ("!=", "Archived")}, pluck="name"
		)
	)


def assert_unlocked(sites, benches=()) -> None:
	unlocked = set(getattr(frappe.local, "mcp_token_confidential_sites", None) or ())
	for site in confidential_sites(sites):
		if site not in unlocked:
			raise frappe.PermissionError(
				f"site {site!r} is confidential; issue a token that names it in Allowed Sites "
				"and enter the Admin PIN"
			)
	# Code or file access inside a bench container reaches every site on that bench.
	for bench in benches:
		hosted = frappe.get_all(
			"Site",
			filters={"bench": bench, "is_confidential": 1, "status": ("!=", "Archived")},
			pluck="name",
		)
		for site in hosted:
			if site not in unlocked:
				raise frappe.PermissionError(
					f"bench {bench!r} hosts confidential site {site!r}; in-container access needs a "
					"token that unlocked it with the Admin PIN"
				)
