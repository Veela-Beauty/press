import frappe

def fix():
    frappe.set_user("Administrator")
    dashboard_team = "sqkn1globp"

    # 1. Approve the AccuBuild release
    frappe.db.set_value("App Release", "7f9oq37ajl", "status", "Approved")
    print("AccuBuild release approved")

    # 2. Create the Release Group (the previous attempt failed mid-way)
    bench_apps = [
        {"app": "frappe", "source": "SRC-frappe-002"},
        {"app": "erpnext", "source": "SRC-erpnext-002"},
        {"app": "hrms", "source": "SRC-hrms-001"},
        {"app": "payments", "source": "SRC-payments-001"},
        {"app": "accubuild_core", "source": "SRC-accubuild_core-001"},
    ]

    # Check if "AccuBuild Demo" RG already exists
    existing = frappe.get_all("Release Group", filters={"title": "AccuBuild Demo"}, pluck="name")
    if existing:
        rg = frappe.get_doc("Release Group", existing[0])
        print(f"Release Group exists: {rg.name}")
    else:
        rg = frappe.get_doc({
            "doctype": "Release Group",
            "title": "AccuBuild Demo",
            "version": "Version 15",
            "team": dashboard_team,
            "enabled": 1,
            "apps": bench_apps,
            "servers": [{"server": "press-f1.demo.mvpstorm.com"}],
        })
        rg.insert(ignore_permissions=True)
        print(f"Release Group created: {rg.name}")

    frappe.db.commit()

    # 3. Create DC and build
    dc = rg.create_deploy_candidate()
    frappe.db.commit()
    print(f"Deploy Candidate: {dc.name}")
    for app in dc.apps:
        print(f"  {app.app}: {app.source}")

    dc.build()
    frappe.db.commit()
    print("Build triggered!")
