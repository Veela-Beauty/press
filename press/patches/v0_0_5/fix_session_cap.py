"""One-shot: set simultaneous_sessions=0 for every enabled User.
Re-runs the intent of disable_team_member_session_cap to catch any
users created or reverted since the original patch ran.
"""
import frappe

def execute():
    rows = frappe.db.sql(
        "SELECT name, simultaneous_sessions FROM tabUser WHERE enabled=1 AND simultaneous_sessions!=0 AND name!=%s",
        ("Guest",), as_dict=True,
    )
    if not rows:
        print("fix_session_cap: nothing to do — all users already at 0")
        return
    for r in rows:
        frappe.db.set_value("User", r.name, "simultaneous_sessions", 0, update_modified=False)
        print(f"fix_session_cap: {r.name} -> 0 (was {r.simultaneous_sessions})")
    frappe.db.commit()
    print(f"fix_session_cap: {len(rows)} user(s) set to unlimited")
