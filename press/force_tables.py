import frappe
from frappe.utils import add_days, nowdate

def run():
    for dt_name in ["Demo Invite Code", "Demo Site Request"]:
        dt = frappe.get_doc("DocType", dt_name)
        from frappe.database.schema import DBTable
        dbt = DBTable(dt_name)
        dbt.sync()
        exists = frappe.db.table_exists(f"tab{dt_name}")
        print(f"{dt_name}: table {'EXISTS' if exists else 'MISSING'}")

    if frappe.db.count("Demo Invite Code") == 0:
        frappe.get_doc({
            "doctype": "Demo Invite Code",
            "code": "ACCU-DEMO-2026",
            "enabled": 1,
            "expires_on": add_days(nowdate(), 90),
            "max_uses": 0,
            "used_count": 1,
            "notes": "Default invite code",
        }).insert(ignore_permissions=True)
        print("Inserted ACCU-DEMO-2026")

    if frappe.db.count("Demo Site Request") == 0:
        frappe.get_doc({
            "doctype": "Demo Site Request",
            "company": "Elixeum Test",
            "email": "eng.elgogary@gmail.com",
            "site": "elixeum-test.sandbox.mvpstorm.com",
            "invite_code": "ACCU-DEMO-2026",
        }).insert(ignore_permissions=True)
        print("Inserted Elixeum Test request")

    frappe.db.commit()
    print("Done")
