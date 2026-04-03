import frappe

def rebuild():
    frappe.set_user("Administrator")
    dashboard_team = "sqkn1globp"
    new_server = "press-f1.sandbox.mvpstorm.com"

    # Re-enable bench-0005 (AccuBuild Demo)
    rg = frappe.get_doc("Release Group", "bench-0005")
    rg.enabled = 1

    # Update server reference
    rg.servers = []
    rg.append("servers", {"server": new_server})
    rg.save(ignore_permissions=True)
    frappe.db.commit()

    print(f"Release Group: {rg.name} ({rg.title})")
    print(f"  Server: {new_server}")
    print(f"  Apps: {[a.app for a in rg.apps]}")

    # Create deploy candidate and build+deploy
    dc = rg.create_deploy_candidate()
    frappe.db.commit()
    print(f"  DC: {dc.name}")

    build_name = dc.build_and_deploy()
    frappe.db.commit()
    print(f"  Build+Deploy triggered: {build_name}")
