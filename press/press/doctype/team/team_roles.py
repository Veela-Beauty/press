"""Press team role system — role definitions and permission checks."""
import frappe

from press.api.admin_panel import DEFAULT_FEATURES

# Role definitions with hierarchy
PRESS_ROLES = {
    "Platform Admin": {"level": 100, "label": "Platform Admin", "description": "Full access to everything"},
    "DevOps Admin": {"level": 80, "label": "DevOps Admin", "description": "Manage servers, benches, deploys"},
    "DevOps User": {"level": 60, "label": "DevOps User", "description": "View servers, trigger deploys"},
    "Developer": {"level": 40, "label": "Developer", "description": "Create dev/staging sites, use dev tools"},
    "Implementor": {"level": 20, "label": "Implementor", "description": "Configure sites, install apps"},
    "Viewer": {"level": 10, "label": "Viewer", "description": "Read-only access"},
}

PRESS_ROLE_OPTIONS = "\n".join(PRESS_ROLES.keys())


def setup_role_field():
    """Add press_role custom field to Team Member DocType."""
    cf_name = "Team Member-press_role"
    if frappe.db.exists("Custom Field", cf_name):
        return
    frappe.get_doc({
        "doctype": "Custom Field",
        "dt": "Team Member",
        "fieldname": "press_role",
        "label": "Press Role",
        "fieldtype": "Select",
        "options": PRESS_ROLE_OPTIONS,
        "default": "Viewer",
        "insert_after": "user",
        "in_list_view": 1,
    }).insert(ignore_permissions=True)
    frappe.db.commit()


def get_user_role(team=None, user=None):
    """Get the press_role for a user in a team."""
    if not user:
        user = frappe.session.user
    if user == "Administrator":
        return "Platform Admin"
    if not team:
        from press.utils import get_current_team
        team = get_current_team()

    role = frappe.db.get_value(
        "Team Member", {"parent": team, "user": user}, "press_role",
    )
    return role or "Viewer"


def get_role_level(role_name):
    """Return numeric level for a role (higher = more access)."""
    return PRESS_ROLES.get(role_name, {}).get("level", 0)


def has_role_access(required_role, team=None, user=None):
    """Check if user's role level >= required role level."""
    user_role = get_user_role(team, user)
    return get_role_level(user_role) >= get_role_level(required_role)


def can_access_feature(feature_id, team=None, user=None):
    """Check if user's role is allowed to access a feature (per registry)."""
    if user == "Administrator" or frappe.session.user == "Administrator":
        return True

    feature = DEFAULT_FEATURES.get(feature_id)
    if not feature:
        return False

    user_role = get_user_role(team, user)
    return user_role in feature.get("roles", [])
