import frappe

def execute():
    users = frappe.db.sql("""SELECT name, email, user_type FROM tabUser WHERE enabled=1 AND user_type='System User' AND name!='Guest'""", as_dict=True)
    for u in users:
        print(" ", u.name, "|", u.email)
