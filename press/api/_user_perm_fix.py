"""Find + promote internal team members to full System Manager access on
the Press controller site. Used in the 2026-05-10 'lost benches list'
incident — easier than tracing why Team Member access dropped.
"""
from __future__ import annotations

import frappe


def find_marco_mahmoud():
	"""Best-effort search across User, Team, Team Member for anything matching
	'marco' or 'mahmoud' in name/email/full_name."""
	out = {"users": [], "team_members": [], "press_team_members": []}
	# Frappe User table
	rows = frappe.db.sql(
		"""
		SELECT name, email, full_name, enabled, user_type
		FROM `tabUser`
		WHERE LOWER(name) LIKE %(p)s
		   OR LOWER(email) LIKE %(p)s
		   OR LOWER(full_name) LIKE %(p)s
		""",
		{"p": "%marco%"},
		as_dict=True,
	)
	rows += frappe.db.sql(
		"""
		SELECT name, email, full_name, enabled, user_type
		FROM `tabUser`
		WHERE LOWER(name) LIKE %(p)s
		   OR LOWER(email) LIKE %(p)s
		   OR LOWER(full_name) LIKE %(p)s
		""",
		{"p": "%mahmoud%"},
		as_dict=True,
	)
	out["users"] = rows
	# Press Team Member table (child)
	for u in {r["name"] for r in rows}:
		teams = frappe.db.sql(
			"""
			SELECT parent, user, role, press_role
			FROM `tabTeam Member`
			WHERE user = %s
			""",
			(u,),
			as_dict=True,
		)
		out["team_members"].extend(teams)
	return out


def promote_to_system_manager(email: str):
	"""Make `email` a System Manager + System User. Idempotent."""
	if not frappe.db.exists("User", email):
		return f"NOT_FOUND: {email}"
	user = frappe.get_doc("User", email)
	user.user_type = "System User"
	user.enabled = 1
	# Ensure System Manager role
	existing_roles = {r.role for r in user.roles}
	added = []
	for role in ("System Manager", "Press Admin", "Press Member"):
		if role in existing_roles:
			continue
		if not frappe.db.exists("Role", role):
			continue
		user.append("roles", {"role": role})
		added.append(role)
	user.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"user": email,
		"user_type": user.user_type,
		"enabled": user.enabled,
		"roles_added": added,
		"all_roles": [r.role for r in user.roles],
	}
