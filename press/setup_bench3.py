import frappe

def setup():
    frappe.set_user("Administrator")

    # Check if bench-0003 exists
    if not frappe.db.exists("Release Group", "bench-0003"):
        print("bench-0003 does not exist")
        # List all release groups
        rgs = frappe.get_all("Release Group", fields=["name", "title", "team"])
        for r in rgs:
            print(f"  {r.name}: {r.title} team={r.team}")
        return

    rg = frappe.get_doc("Release Group", "bench-0003")
    print(f"Release Group: {rg.name} ({rg.title})")
    print(f"Current apps: {len(rg.apps)}")
    for a in rg.apps:
        print(f"  {a.app}: {a.source}")

    # If no apps, add the v15-compatible apps
    if len(rg.apps) == 0:
        source_map = {}
        sources = frappe.get_all("App Source", fields=["name", "app"])
        for s in sources:
            source_map[s.app] = s.name

        # Add apps in correct order (frappe first)
        apps_order = ["frappe", "erpnext", "hrms", "payments", "webshop", "lending"]
        for app_name in apps_order:
            if app_name in source_map:
                rg.append("apps", {"app": app_name, "source": source_map[app_name]})
                print(f"Added: {app_name} -> {source_map[app_name]}")

        rg.save(ignore_permissions=True)
        frappe.db.commit()
        print(f"\nRelease Group updated with {len(rg.apps)} apps")

        # Create deploy candidate and build
        dc = rg.create_deploy_candidate()
        frappe.db.commit()
        print(f"Deploy Candidate: {dc.name}")

        dc.build()
        frappe.db.commit()
        print("Build triggered!")
    else:
        print("Apps already present, skipping")

        # Check if there's a deploy candidate
        dcs = frappe.get_all("Deploy Candidate",
            filters={"group": rg.name},
            fields=["name"],
            order_by="creation desc", limit=1)
        if dcs:
            print(f"Latest DC: {dcs[0].name}")
        else:
            dc = rg.create_deploy_candidate()
            frappe.db.commit()
            print(f"Created DC: {dc.name}")
            dc.build()
            frappe.db.commit()
            print("Build triggered!")
