import frappe

def fix():
    frappe.set_user("Administrator")

    # Create a dummy email account to prevent OutgoingEmailError crashes
    if not frappe.get_all("Email Account", filters={"default_outgoing": 1}):
        if not frappe.db.exists("Email Account", "Notifications"):
            ea = frappe.get_doc({
                "doctype": "Email Account",
                "email_account_name": "Notifications",
                "email_id": "noreply@demo.mvpstorm.com",
                "domain": "demo.mvpstorm.com",
                "default_outgoing": 1,
                "enable_outgoing": 0,  # disabled but exists as default
                "smtp_server": "localhost",
                "smtp_port": 25,
            })
            ea.flags.ignore_permissions = True
            ea.flags.ignore_mandatory = True
            ea.insert(ignore_permissions=True)
            print("Created dummy Email Account: Notifications")
        else:
            frappe.db.set_value("Email Account", "Notifications", "default_outgoing", 1)
            print("Set Notifications as default outgoing")
    else:
        print("Default outgoing email account already exists")

    frappe.db.commit()

    # Mark all stuck builds as Failure
    stuck = frappe.get_all("Deploy Candidate Build",
        filters={"status": ["in", ["Preparing", "Running"]]},
        pluck="name")
    for b in stuck:
        frappe.db.set_value("Deploy Candidate Build", b, "status", "Failure")
        print(f"Marked {b} as Failure")
    frappe.db.commit()

    # Retry build
    rg = frappe.get_doc("Release Group", "bench-0004")
    dc = rg.create_deploy_candidate()
    frappe.db.commit()
    print(f"\nNew DC: {dc.name}")
    dc.build()
    frappe.db.commit()
    print("Build triggered!")
