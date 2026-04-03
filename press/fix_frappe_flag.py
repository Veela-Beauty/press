import frappe

def fix():
    frappe.set_user("Administrator")

    # All apps from github.com/frappe/ should have frappe=1
    sources = frappe.get_all("App Source",
        filters={"repository_url": ["like", "%github.com/frappe/%"]},
        fields=["name", "app", "repository_url", "frappe"]
    )

    for s in sources:
        if not s.frappe:
            frappe.db.set_value("App Source", s.name, "frappe", 1)
            print(f"Fixed {s.name} ({s.app}): frappe=1")
        else:
            print(f"OK: {s.name} ({s.app})")

    frappe.db.commit()
    print("\nDone! Refresh the dashboard.")
