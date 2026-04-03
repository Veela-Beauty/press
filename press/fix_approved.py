import frappe

def fix():
    frappe.set_user("Administrator")

    # Mark all marketplace apps as frappe_approved
    apps = frappe.get_all("Marketplace App", fields=["name", "app", "frappe_approved"])
    for a in apps:
        if not a.frappe_approved:
            frappe.db.set_value("Marketplace App", a.name, "frappe_approved", 1)
            print(f"Approved: {a.name} ({a.app})")
        else:
            print(f"Already approved: {a.name}")

    frappe.db.commit()
    print("\nDone! All marketplace apps are now frappe_approved.")
