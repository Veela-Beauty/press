import frappe

def run():
    ps = frappe.get_doc("Press Settings")
    for f in ps.meta.fields:
        val = ps.get(f.fieldname)
        if val and ("token" in f.fieldname.lower() or "key" in f.fieldname.lower() or "secret" in f.fieldname.lower() or "cloudflare" in f.fieldname.lower()):
            print(f"{f.fieldname}: {val}")
