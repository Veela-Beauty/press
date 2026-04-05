"""AI governance API — whitelisted endpoints for Press dashboard.

Minimal API layer for the Admin Panel Vue components.
"""

import frappe


@frappe.whitelist()
def acknowledge_policy():
	"""Record that the current user acknowledged the AI usage policy."""
	user = frappe.session.user
	# Store in user defaults (no schema change needed)
	frappe.defaults.set_user_default("ai_policy_acknowledged", "1", user=user)
	frappe.defaults.set_user_default("ai_policy_version", "1.0", user=user)
	frappe.defaults.set_user_default("ai_policy_acknowledged_at", frappe.utils.now(), user=user)
	return {"success": True, "user": user}


@frappe.whitelist()
def get_ai_config():
	"""Get AI configuration for the current user/team."""
	user = frappe.session.user
	acknowledged = frappe.defaults.get_user_default("ai_policy_acknowledged", user=user)
	return {
		"user": user,
		"policy_acknowledged": acknowledged == "1",
		"policy_version": frappe.defaults.get_user_default("ai_policy_version", user=user),
	}
