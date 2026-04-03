import frappe

def fix():
    frappe.set_user("Administrator")
    
    # Make all App Sources public and enabled
    sources = frappe.get_all("App Source", fields=["name", "app", "public", "enabled"])
    for s in sources:
        if not s.public or not s.enabled:
            frappe.db.set_value("App Source", s.name, {"public": 1, "enabled": 1})
            print(f"Fixed {s.name} ({s.app}): public=1 enabled=1")
        else:
            print(f"OK: {s.name} ({s.app})")
    
    # Make Frappe Version 15 public and default
    fv = frappe.get_all("Frappe Version", filters={"name": "Version 15"}, fields=["name", "public", "default"])
    for v in fv:
        if not v.public:
            frappe.db.set_value("Frappe Version", v.name, {"public": 1, "default": 1})
            print(f"Fixed Frappe Version {v.name}: public=1 default=1")
        else:
            print(f"Frappe Version {v.name}: already public={v.public}")
    
    # Also make Marketplace Apps published
    apps = frappe.get_all("Marketplace App", fields=["name", "status"])
    for a in apps:
        if a.status != "Published":
            frappe.db.set_value("Marketplace App", a.name, "status", "Published")
            print(f"Published: {a.name}")
    
    frappe.db.commit()
    print("\nDone!")
