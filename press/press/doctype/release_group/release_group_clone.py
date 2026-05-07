# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from datetime import timedelta

import frappe
from frappe.utils import now_datetime

from press.press.doctype.release_group.release_group import new_release_group

VALID_LIFETIMES = ("sandbox", "persistent")
SANDBOX_TTL_HOURS = 24


@frappe.whitelist()
def clone_release_group(
	release_group: str,
	new_title: str,
	lifetime: str = "persistent",
) -> str:
	"""Clone a Release Group on the same server with the same apps + version.

	Returns the name of the new Release Group.
	"""
	if lifetime not in VALID_LIFETIMES:
		frappe.throw(
			f"lifetime must be one of {VALID_LIFETIMES}, got {lifetime!r}",
			frappe.ValidationError,
		)

	source = frappe.get_doc("Release Group", release_group)

	is_system_user = frappe.session.data.user_type == "System User"
	if not is_system_user:
		from press.utils import get_current_team

		team = get_current_team(get_doc=True)
		_check_team_access(source, team)
		team_name = team.name
	else:
		# System Users (Administrator, background jobs) inherit the source team
		team_name = source.team

	apps = [{"app": a.app, "source": a.source} for a in source.apps]
	server = source.servers[0].server if source.servers else None

	clone = new_release_group(
		title=new_title,
		version=source.version,
		apps=apps,
		team=team_name,
		cluster=None,
		saas_app=source.saas_app or "",
		server=server,
	)

	clone.cloned_from = source.name
	clone.clone_lifetime = lifetime
	if lifetime == "sandbox":
		clone.clone_expires_at = now_datetime() + timedelta(hours=SANDBOX_TTL_HOURS)
	clone.save(ignore_permissions=True)

	return clone.name


def _check_team_access(source, team) -> None:
	if source.team != team.name:
		frappe.throw(
			f"You don't have access to Release Group {source.name}",
			frappe.PermissionError,
		)
