"""One-shot: copy admin_access -> allow_invite_team_members + allow_manage_team_members.
allow_manage_team_roles stays 0 — genuinely new power, requires explicit grant."""
import frappe

def execute():
    frappe.reload_doc("press", "doctype", "press_role")
    frappe.db.sql("""
        UPDATE `tabPress Role`
           SET allow_invite_team_members = 1,
               allow_manage_team_members = 1
         WHERE admin_access = 1
    """)
    frappe.db.commit()