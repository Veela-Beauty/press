import frappe

def fix():
    frappe.set_user("Administrator")
    frappe.db.set_single_value("Press Settings", "github_app_public_link", "https://github.com/apps/mvpstorm-press")
    frappe.db.commit()
    print("Updated github_app_public_link to: https://github.com/apps/mvpstorm-press")
