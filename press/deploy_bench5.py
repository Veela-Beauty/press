import frappe

def deploy():
    frappe.set_user("Administrator")

    # Find the successful deploy candidate
    dc = frappe.get_doc("Deploy Candidate", "deploy-0005-000001")
    print(f"DC: {dc.name}")
    print(f"Apps: {[a.app for a in dc.apps]}")

    # Check build status
    builds = frappe.get_all("Deploy Candidate Build",
        filters={"deploy_candidate": dc.name, "status": "Success"},
        pluck="name")
    print(f"Successful builds: {builds}")

    if not builds:
        print("No successful build found!")
        return

    # Deploy the candidate
    try:
        dc.deploy_to_production()
        frappe.db.commit()
        print("Deploy triggered!")
    except Exception as e:
        print(f"Deploy error: {e}")
        # Try alternative method
        try:
            dc.create_deploy([{"server": "press-f1.demo.mvpstorm.com"}])
            frappe.db.commit()
            print("Deploy created via create_deploy!")
        except Exception as e2:
            print(f"Create deploy error: {e2}")

            # Check what methods are available
            methods = [m for m in dir(dc) if "deploy" in m.lower() and not m.startswith("_")]
            print(f"Available deploy methods: {methods}")
