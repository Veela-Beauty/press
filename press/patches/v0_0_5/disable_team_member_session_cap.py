"""One-shot: disable the simultaneous_sessions cap (set to 0 = unlimited)
for every existing Team Member's User.

Replaces the bumping logic of v0_0_5/bump_team_member_session_cap. The
previous patch raised the cap to a positive number (10, then 50); this one
disables it entirely because the cap was triggering a death-spiral with
the Vue dashboard's auto-logout loop on press-ctrl.

0 = unlimited per Frappe's clear_old_sessions early-return semantics.
Sessions still expire naturally after session_expiry (default 170 hours).
"""
import frappe

from press.press.doctype.team.team_roles import TEAM_MEMBER_SESSION_CAP


def execute():
    rows = frappe.db.sql(
        """
        SELECT DISTINCT tm.user
        FROM `tabTeam Member` tm
        JOIN `tabUser` u ON u.name = tm.user
        WHERE u.enabled = 1
          AND tm.user != 'Guest'
          AND u.simultaneous_sessions != %(cap)s
        """,
        {"cap": TEAM_MEMBER_SESSION_CAP},
        as_dict=True,
    )
    if not rows:
        print("disable_team_member_session_cap: nothing to do")
        return
    for r in rows:
        frappe.db.set_value(
            "User", r.user, "simultaneous_sessions", TEAM_MEMBER_SESSION_CAP,
            update_modified=False,
        )
        print(f"disable_team_member_session_cap: {r.user} -> {TEAM_MEMBER_SESSION_CAP} (unlimited)")
    frappe.db.commit()
    print(f"disable_team_member_session_cap: {len(rows)} user(s) set to unlimited")
