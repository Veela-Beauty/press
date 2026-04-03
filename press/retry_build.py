import frappe

def retry():
    frappe.set_user("Administrator")
    dc = frappe.get_doc("Deploy Candidate", "deploy-0002-000001")
    dc.build()
    frappe.db.commit()
    print("Build re-triggered!")
