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


@frappe.whitelist()
def update_team_ai_rules(team: str, settings: str | dict) -> dict:
	"""Persist per-team AI governance rules (block_prod, block_app_mgmt, escalation_tl).

	Called by dashboard/src/components/admin/AiTeamRules.vue (the Admin Panel
	AI policy editor). Accepts settings as a JSON string OR a dict — Vue
	stringifies before send. Storage uses frappe.defaults keyed by the
	team's docname so we don't introduce a schema change.

	Without this method the AiTeamRules.vue panel 500s with "has no attribute
	'update_team_ai_rules'". Caught by
	scripts/audit_dashboard_method_exists.py on 2026-05-19.

	Auth: caller must be a System User OR own/admin the team. Press has many
	teams; we check the caller's current team matches the target.
	"""
	import json

	from press.utils import get_current_team

	if frappe.session.data.user_type != "System User":
		current = get_current_team()
		if current != team:
			frappe.throw(
				f"You can only update AI rules for your own team (got {team!r}, "
				f"current team is {current!r})",
				frappe.PermissionError,
			)

	# Vue stringifies the settings dict before sending — handle both shapes
	if isinstance(settings, str):
		settings = json.loads(settings)
	if not isinstance(settings, dict):
		frappe.throw("settings must be a JSON object", frappe.ValidationError)

	# Persist via frappe.defaults — no schema change, no fixture sync
	frappe.defaults.set_user_default("ai_team_rules", json.dumps(settings), user=team)
	return {"team": team, "settings": settings}
