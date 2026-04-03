import frappe

def fix():
    frappe.set_user("Administrator")
    dashboard_team = "sqkn1globp"
    
    # 1. Transfer Release Groups to dashboard team
    for rg_name in ["bench-0001", "bench-0002"]:
        frappe.db.set_value("Release Group", rg_name, "team", dashboard_team)
        print(f"Release Group {rg_name} -> team {dashboard_team}")
    
    # 2. Transfer Sites to dashboard team
    sites = frappe.get_all("Site", pluck="name")
    for site in sites:
        frappe.db.set_value("Site", site, "team", dashboard_team)
        print(f"Site {site} -> team {dashboard_team}")
    
    # 3. Create Marketplace Apps for all registered apps
    apps = frappe.get_all("App", fields=["name", "title"])
    for app in apps:
        if not frappe.db.exists("Marketplace App", app.name):
            sources = frappe.get_all("App Source", filters={"app": app.name}, fields=["name"])
            ma = frappe.get_doc({
                "doctype": "Marketplace App",
                "app": app.name,
                "title": app.title,
                "team": "f6o5jtfht1",
                "description": app.title,
                "category": "Other",
                "sources": [{"source": s.name, "version": "Version 15"} for s in sources],
            })
            try:
                ma.insert(ignore_permissions=True)
                # Publish it
                frappe.db.set_value("Marketplace App", ma.name, "status", "Published")
                print(f"Marketplace App created: {app.name}")
            except Exception as e:
                print(f"  Error creating Marketplace App {app.name}: {e}")
        else:
            print(f"Marketplace App exists: {app.name}")
    
    # 4. Transfer App Sources to dashboard team too
    sources = frappe.get_all("App Source", pluck="name")
    for s in sources:
        frappe.db.set_value("App Source", s, "team", dashboard_team)
    print(f"\nTransferred {len(sources)} App Sources to dashboard team")
    
    # 5. Transfer Server records to dashboard team
    for dt in ["Server", "Database Server", "Proxy Server"]:
        docs = frappe.get_all(dt, pluck="name")
        for d in docs:
            frappe.db.set_value(dt, d, "team", dashboard_team)
        print(f"Transferred {len(docs)} {dt} records to dashboard team")
    
    frappe.db.commit()
    print("\nDone! Dashboard user should now see everything.")

