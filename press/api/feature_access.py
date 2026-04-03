"""Check if a team has access to a specific feature."""
import json

import frappe


@frappe.whitelist()
def has_feature(team=None, feature_id=""):
    """Check if the current team has a feature enabled."""
    if not team:
        from press.utils import get_current_team
        team = get_current_team()
    features_json = frappe.db.get_value("Team", team, "enabled_features") or "{}"
    features = json.loads(features_json)
    return bool(features.get(feature_id))


@frappe.whitelist()
def get_team_features(team=None):
    """Return all enabled features for a team."""
    if not team:
        from press.utils import get_current_team
        team = get_current_team()
    features_json = frappe.db.get_value("Team", team, "enabled_features") or "{}"
    return json.loads(features_json)
