import frappe
import subprocess

def fix():
    frappe.set_user("Administrator")
    team = frappe.get_all("Team", filters={"user": "Administrator"}, pluck="name")[0]
    dashboard_team = "sqkn1globp"

    # Update App Source to correct repo
    src = frappe.get_doc("App Source", "SRC-accubuild_core-001")
    old_url = src.repository_url
    old_branch = src.branch

    src.repository_url = "https://github.com/accurate-systems/accubuild"
    src.branch = "main"
    src.save(ignore_permissions=True)
    print(f"Updated App Source:")
    print(f"  Old: {old_url} ({old_branch})")
    print(f"  New: {src.repository_url} ({src.branch})")

    # Create new release with main branch commit
    commit = "25e917e261820a1c2da37de55c7eeadbbc22d3c7"
    existing = frappe.get_all("App Release", filters={
        "source": "SRC-accubuild_core-001", "hash": commit
    }, pluck="name")

    if not existing:
        rel = frappe.get_doc({
            "doctype": "App Release",
            "app": "accubuild_core",
            "source": "SRC-accubuild_core-001",
            "hash": commit,
            "team": team,
        })
        rel.insert(ignore_permissions=True)
        frappe.db.set_value("App Release", rel.name, "status", "Approved")
        print(f"New release created: {commit[:10]}")
    else:
        frappe.db.set_value("App Release", existing[0], "status", "Approved")
        print(f"Release exists: {existing[0]}")

    frappe.db.commit()

    # Mark old builds as failed and create new DC
    stuck = frappe.get_all("Deploy Candidate Build",
        filters={"deploy_candidate": ["like", "deploy-0005%"], "status": ["in", ["Preparing", "Running"]]},
        pluck="name")
    for b in stuck:
        frappe.db.set_value("Deploy Candidate Build", b, "status", "Failure")
        print(f"Marked {b} as Failure")
    frappe.db.commit()

    # Create new deploy candidate with correct source
    rg = frappe.get_doc("Release Group", "bench-0005")
    dc = rg.create_deploy_candidate()
    frappe.db.commit()
    print(f"\nNew DC: {dc.name}")
    for app in dc.apps:
        src_doc = frappe.get_doc("App Source", app.source)
        print(f"  {app.app}: {src_doc.repository_url} ({src_doc.branch})")

    dc.build()
    frappe.db.commit()
    print("\nBuild triggered!")
