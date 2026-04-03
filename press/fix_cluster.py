import frappe

def fix():
    frappe.set_user("Administrator")
    
    # Make cluster public
    frappe.db.set_value("Cluster", "Default", {"public": 1})
    print("Cluster Default: public=1")
    
    # Check server cluster assignment
    server = frappe.get_doc("Server", "press-f1.demo.mvpstorm.com")
    print(f"Server cluster: {server.cluster}")
    print(f"Server use_for_new_benches: {getattr(server, use_for_new_benches, N/A)}")
    print(f"Server use_for_new_sites: {getattr(server, use_for_new_sites, N/A)}")
    
    # Enable server for new benches and sites
    if hasattr(server, "use_for_new_benches"):
        server.use_for_new_benches = 1
    if hasattr(server, "use_for_new_sites"):
        server.use_for_new_sites = 1
    server.save(ignore_permissions=True)
    print("Server updated for new benches/sites")
    
    frappe.db.commit()
    print("Done!")
