"""Check if a team has access to a specific feature (team toggle + role check)."""
import json

import frappe


@frappe.whitelist()
def has_feature(team=None, feature_id=""):
    """Check if feature is enabled for team AND user's role allows it."""
    from press.utils import get_current_team
    current = get_current_team()
    if not team:
        team = current
    elif team != current and not frappe.has_permission("Team", doc=team, ptype="read"):
        frappe.throw("Not allowed to check another team's features", frappe.PermissionError)

    # 1. Team-level toggle
    features_json = frappe.db.get_value("Team", team, "enabled_features") or "{}"
    features = json.loads(features_json)
    # Empty features = all enabled (backward compat)
    if features and not features.get(feature_id):
        return False

    # 2. Role-level check
    from press.press.doctype.team.team_roles import can_access_feature
    return can_access_feature(feature_id, team)


@frappe.whitelist()
def get_team_features(team=None):
    """Return all enabled features for a team."""
    from press.utils import get_current_team
    current = get_current_team()
    if not team:
        team = current
    elif team != current and not frappe.has_permission("Team", doc=team, ptype="read"):
        frappe.throw("Not allowed to check another team's features", frappe.PermissionError)
    features_json = frappe.db.get_value("Team", team, "enabled_features") or "{}"
    return json.loads(features_json)
