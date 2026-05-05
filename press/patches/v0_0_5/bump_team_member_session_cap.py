"""One-shot: raise simultaneous_sessions to MIN_SIMULTANEOUS_SESSIONS for
every existing Team Member's User.

Frappe's default of 2 silently evicts older sessions when a user opens a 3rd
tab — surfacing as a misleading "Function ... is not whitelisted" 403 in the
dashboard. Going forward the after_insert hook on Team Member handles this;
this patch backfills users invited before the hook existed.
"""
import frappe

from press.press.doctype.team.team_roles import TEAM_MEMBER_SESSION_CAP as MIN_SIMULTANEOUS_SESSIONS


def execute():
    rows = frappe.db.sql(
        """
        SELECT DISTINCT tm.user
        FROM `tabTeam Member` tm
        JOIN `tabUser` u ON u.name = tm.user
        WHERE u.enabled = 1
          AND tm.user != 'Guest'
          AND (u.simultaneous_sessions IS NULL OR u.simultaneous_sessions < %(cap)s)
        """,
        {"cap": MIN_SIMULTANEOUS_SESSIONS},
        as_dict=True,
    )
    if not rows:
        print("bump_team_member_session_cap: nothing to do")
        return
    for r in rows:
        frappe.db.set_value(
            "User", r.user, "simultaneous_sessions", MIN_SIMULTANEOUS_SESSIONS,
            update_modified=False,
        )
        print(f"bump_team_member_session_cap: {r.user} -> {MIN_SIMULTANEOUS_SESSIONS}")
    frappe.db.commit()
    print(f"bump_team_member_session_cap: bumped {len(rows)} user(s)")
