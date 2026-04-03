import frappe

def go():
    frappe.set_user("Administrator")
    rg = frappe.get_doc("Release Group", "bench-0002")
    dc = rg.create_deploy_candidate()
    frappe.db.commit()
    print(f"Deploy Candidate: {dc.name}")
    
    dc.build()
    frappe.db.commit()
    print(f"Build triggered!")
