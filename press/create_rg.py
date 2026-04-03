import frappe

def create_full_release_group():
    frappe.set_user("Administrator")
    team = frappe.get_all("Team", filters={"user": "Administrator"}, pluck="name")[0]
    
    # Get all app sources
    sources = frappe.get_all("App Source", fields=["name", "app", "app_title"])
    print(f"Available sources: {len(sources)}")
    for s in sources:
        print(f"  {s.app}: {s.name}")
    
    # Build the apps list for the Release Group
    # frappe must be first
    apps_order = ["frappe", "erpnext", "hrms", "payments", "webshop", "print_designer",
                  "wiki", "lms", "builder", "helpdesk", "crm", "insights", "lending", "drive", "gameplan"]
    
    source_map = {s.app: s.name for s in sources}
    
    rg_apps = []
    for app_name in apps_order:
        if app_name in source_map:
            rg_apps.append({"app": app_name, "source": source_map[app_name]})
    
    print(f"\nApps for Release Group: {len(rg_apps)}")
    
    # Create Release Group
    rg = frappe.get_doc({
        "doctype": "Release Group",
        "title": "Full Stack v15",
        "version": "Version 15",
        "team": team,
        "enabled": 1,
        "apps": rg_apps,
        "servers": [{"server": "press-f1.demo.mvpstorm.com"}],
    })
    rg.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"\nRelease Group created: {rg.name}")
    print(f"Title: {rg.title}")
    print(f"Apps: {len(rg.apps)}")
    
