import frappe

def create_deploy_candidate():
    frappe.set_user("Administrator")
    
    rg = frappe.get_doc("Release Group", "bench-0002")
    print(f"Release Group: {rg.name} ({rg.title})")
    print(f"Apps: {len(rg.apps)}")
    
    # Use the Release Group method to create deploy candidate
    dc = rg.create_deploy_candidate()
    frappe.db.commit()
    print(f"Deploy Candidate created: {dc.name}")
    
