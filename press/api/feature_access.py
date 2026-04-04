"""Check if a team has access to a specific feature."""
import json

import frappe


@frappe.whitelist()
def has_feature(team=None, feature_id=""):
    """Check if the current team has a feature enabled."""
    from press.utils import get_current_team
    current = get_current_team()
    if not team:
        team = current
    elif team != current and not frappe.has_permission("Team", doc=team, ptype="read"):
        frappe.throw("Not allowed to check another team's features", frappe.PermissionError)
    features_json = frappe.db.get_value("Team", team, "enabled_features") or "{}"
    features = json.loads(features_json)
    return bool(features.get(feature_id))


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
