import frappe

def fix():
    frappe.set_user("Administrator")
    server = frappe.get_doc("Server", "press-f1.demo.mvpstorm.com")
    fields = [f.fieldname for f in server.meta.fields]
    
    for f in ["use_for_new_benches", "use_for_new_sites", "use_for_build"]:
        if f in fields:
            val = getattr(server, f, 0)
            print(f"  {f}: {val}")
            if not val:
                setattr(server, f, 1)
    
    server.save(ignore_permissions=True)
    frappe.db.commit()
    print("Server flags updated")
