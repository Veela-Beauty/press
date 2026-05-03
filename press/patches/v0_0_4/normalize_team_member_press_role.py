"""One-shot: coerce any unknown press_role on Team Member rows to 'Viewer'.

Background: an unknown role (e.g. 'Admin' written by direct SQL or a stale
dashboard build) makes get_role_level() return 0 — *below* Viewer (10) —
silently locking the user out of every feature gated by the role hierarchy.
"""
import frappe

from press.press.doctype.team.team_roles import PRESS_ROLES, DEFAULT_ROLE


def execute():
    valid = list(PRESS_ROLES.keys())
    rows = frappe.db.sql(
        """
        SELECT name, parent, user, press_role
        FROM `tabTeam Member`
        WHERE press_role IS NOT NULL
          AND press_role != ''
          AND press_role NOT IN %(valid)s
        """,
        {"valid": valid},
        as_dict=True,
    )

    if not rows:
        print("normalize_team_member_press_role: no invalid rows found")
        return

    for r in rows:
        print(
            f"normalize_team_member_press_role: team={r.parent} user={r.user} "
            f"press_role={r.press_role!r} -> {DEFAULT_ROLE!r}"
        )
        frappe.db.set_value("Team Member", r.name, "press_role", DEFAULT_ROLE)

    frappe.db.commit()
    print(f"normalize_team_member_press_role: fixed {len(rows)} row(s)")
