import frappe

def build_deploy_candidate():
    frappe.set_user("Administrator")
    dc = frappe.get_doc("Deploy Candidate", "deploy-0002-000001")
    print(f"DC: {dc.name}")
    print(f"Apps: {len(dc.apps)}")
    
    # Trigger the build
    dc.build()
    frappe.db.commit()
    print(f"Build triggered!")
    
