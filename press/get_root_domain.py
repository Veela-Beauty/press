import frappe

def run():
    doc = frappe.get_doc("Root Domain", "sandbox.mvpstorm.com")
    for f in doc.meta.fields:
        val = doc.get(f.fieldname)
        if val:
            print(f"{f.fieldname}: {val}")
