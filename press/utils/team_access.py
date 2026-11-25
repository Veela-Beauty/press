"""Permission check shared by the bench- and site-side developer helpers (console, logs, git, files, SSH, code server).

Moved out of press/utils/__init__.py in press 0.7.70 (re-exported there, so `from press.utils import
ensure_team_access` keeps working) and widened: besides the team, a member whose Press Role lists only some benches
and sites (DevOps L1, Viewer) is held to that list, as the dashboard holds him.
"""

import frappe


def ensure_team_access(bench_name=None, site_name=None):
	"""Allow System Managers, or members of the bench's or site's team whose role covers it.
	Raises frappe.PermissionError otherwise.

	Pass bench_name OR site_name (not both). Resolves the target team via
	the Bench's team (falling back to its Release Group team) or the Site's
	team, then compares against the current session's team.
	"""
	from press.utils import get_current_team

	if frappe.session.data and frappe.session.data.user_type == "System User":
		return
	if "System Manager" in frappe.get_roles(frappe.session.user):
		return
	current_team = get_current_team()
	target_team = None
	group = None
	if bench_name:
		group = frappe.db.get_value("Bench", bench_name, "group")
		target_team = frappe.db.get_value("Bench", bench_name, "team") or frappe.db.get_value(
			"Release Group", group, "team"
		)
	elif site_name:
		target_team = frappe.db.get_value("Site", site_name, "team")
	if not target_team or target_team != current_team:
		frappe.throw("Not allowed", frappe.PermissionError)
	if not _role_covers(group=group, site_name=site_name):
		frappe.throw("Not allowed", frappe.PermissionError)


def _role_covers(group=None, site_name=None) -> bool:
	"""The dashboard's own role check: owners, admins and members with an all-sites/all-benches role pass."""
	from press.guards import role_guard

	if not role_guard.is_restricted() or role_guard.skip_roles():
		return True
	if site_name and not role_guard.check("Site", site_name):
		return False
	if group and not role_guard.check("Release Group", group):
		return False
	return bool(site_name or group)
