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

DEFAULT_ROLE = "Viewer"


def normalize_press_role(role):
    """Return role if it is a valid press_role, else DEFAULT_ROLE.

    Hardens against legacy data, direct SQL, or upstream/dashboard bugs that
    write unrecognized values into Team Member.press_role. Without this an
    unknown role drops the user to level 0 — *below* Viewer — silently locking
    them out of every feature.
    """
    if role in PRESS_ROLES:
        return role
    return DEFAULT_ROLE


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
    if role and role not in PRESS_ROLES:
        frappe.log_error(
            title="Invalid press_role",
            message=f"Team Member {user} on team {team} has invalid press_role={role!r}; coercing to {DEFAULT_ROLE}",
        )
        return DEFAULT_ROLE
    return role or DEFAULT_ROLE


def get_role_level(role_name):
    """Return numeric level for a role (higher = more access).

    Unknown roles fall back to DEFAULT_ROLE's level instead of 0 so that a
    typo or stale value never grants *less* access than the documented floor.
    """
    return PRESS_ROLES.get(role_name, PRESS_ROLES[DEFAULT_ROLE])["level"]


def validate_team_member_role(doc, method=None):
    """doc_events validate hook — block invalid press_role at save time."""
    if doc.get("press_role") and doc.press_role not in PRESS_ROLES:
        frappe.throw(
            frappe._("Invalid press_role {0!r}. Allowed: {1}").format(
                doc.press_role, ", ".join(PRESS_ROLES.keys())
            )
        )


# 0 = unlimited per Frappe's clear_old_sessions early-return semantics.
# Press-ctrl is internal admin tooling — the simultaneous_sessions cap was
# triggering a death-spiral with the Vue dashboard's auto-logout loop (each
# fresh login evicted older session SIDs, kicking active tabs, which made
# the dashboard auto-logout again, fresh login, repeat). For an internal
# instance with a small trusted team this is the right trade-off:
# session_expiry (default 170h / ~7d) still cleans inactive sessions
# naturally, and we no longer fight Frappe's eviction on every login.
TEAM_MEMBER_SESSION_CAP = 0


def ensure_session_cap(doc, method=None):
    """after_insert hook on Team Member — disable simultaneous_sessions cap
    for the invited User.

    Frappe's clear_old_sessions returns early when the value is falsy, so
    setting to 0 means no per-login eviction. Sessions still expire naturally
    after session_expiry. Idempotent — re-running on an already-0 user is a
    no-op (the field is unchanged).
    """
    user = doc.get("user")
    if not user or not frappe.db.exists("User", user):
        return
    current = frappe.db.get_value("User", user, "simultaneous_sessions")
    if current != TEAM_MEMBER_SESSION_CAP:
        frappe.db.set_value(
            "User", user, "simultaneous_sessions", TEAM_MEMBER_SESSION_CAP,
            update_modified=False,
        )


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
