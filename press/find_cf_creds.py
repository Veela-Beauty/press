import frappe

def run():
    # Check Root Domain password fields
    rd = frappe.get_doc("Root Domain", "sandbox.mvpstorm.com")
    for f in rd.meta.fields:
        if f.fieldtype == "Password":
            val = frappe.utils.password.get_decrypted_password("Root Domain", "sandbox.mvpstorm.com", f.fieldname, raise_exception=False)
            print(f"RD sandbox - {f.fieldname}: {val}")

    rd2 = frappe.get_doc("Root Domain", "demo.mvpstorm.com")
    for f in rd2.meta.fields:
        if f.fieldtype == "Password":
            val = frappe.utils.password.get_decrypted_password("Root Domain", "demo.mvpstorm.com", f.fieldname, raise_exception=False)
            print(f"RD demo - {f.fieldname}: {val}")

    # Press Settings
    ps = frappe.get_doc("Press Settings")
    for f in ps.meta.fields:
        if f.fieldtype == "Password":
            val = frappe.utils.password.get_decrypted_password("Press Settings", "Press Settings", f.fieldname, raise_exception=False)
            if val:
                print(f"PS - {f.fieldname}: {val[:20]}...")
