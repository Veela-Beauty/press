import frappe

def retry():
    frappe.set_user("Administrator")

    # Mark the stuck build as failed
    builds = frappe.get_all("Deploy Candidate Build",
        filters={"deploy_candidate": "deploy-0004-000001"},
        pluck="name", order_by="creation desc", limit=1)

    if builds:
        frappe.db.set_value("Deploy Candidate Build", builds[0], "status", "Failure")
        print(f"Marked build {builds[0]} as Failure")

    # Create new build
    dc = frappe.get_doc("Deploy Candidate", "deploy-0004-000001")
    dc.build()
    frappe.db.commit()
    print("New build triggered!")
