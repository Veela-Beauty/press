import frappe

def add():
    frappe.set_user("Administrator")

    rg = frappe.get_doc("Release Group", "bench-0003")
    existing_apps = [a.app for a in rg.apps]
    print(f"Existing apps: {existing_apps}")

    source_map = {}
    sources = frappe.get_all("App Source", fields=["name", "app"])
    for s in sources:
        source_map[s.app] = s.name

    # Add missing v15-compatible apps
    apps_to_add = ["erpnext", "hrms", "payments", "webshop", "lending"]
    added = []
    for app_name in apps_to_add:
        if app_name not in existing_apps and app_name in source_map:
            rg.append("apps", {"app": app_name, "source": source_map[app_name]})
            added.append(app_name)
            print(f"Added: {app_name}")

    if added:
        rg.save(ignore_permissions=True)
        frappe.db.commit()
        print(f"\nAdded {len(added)} apps. Total: {len(rg.apps)}")

        # Create new deploy candidate (the previous one only had frappe)
        dc = rg.create_deploy_candidate()
        frappe.db.commit()
        print(f"New Deploy Candidate: {dc.name}")

        dc.build()
        frappe.db.commit()
        print("Build triggered!")
    else:
        print("No new apps to add")
