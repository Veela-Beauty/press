import frappe
from frappe.utils import nowdate, add_days

def run():
    # 1. Check Demo Site Request
    if frappe.db.exists("DocType", "Demo Site Request"):
        if frappe.db.table_exists("tabDemo Site Request"):
            print("Demo Site Request: DocType + table OK")
        else:
            print("Demo Site Request: DocType exists but table missing — syncing...")
            frappe.db.sql("""CREATE TABLE IF NOT EXISTS `tabDemo Site Request` (
                `name` varchar(140) NOT NULL,
                `creation` datetime(6) DEFAULT NULL,
                `modified` datetime(6) DEFAULT NULL,
                `modified_by` varchar(140) DEFAULT NULL,
                `owner` varchar(140) DEFAULT NULL,
                `docstatus` int(1) NOT NULL DEFAULT 0,
                `idx` int(8) NOT NULL DEFAULT 0,
                `company` varchar(140) DEFAULT NULL,
                `email` varchar(140) DEFAULT NULL,
                `phone` varchar(140) DEFAULT NULL,
                `site` varchar(140) DEFAULT NULL,
                `invite_code` varchar(140) DEFAULT NULL,
                PRIMARY KEY (`name`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
            print("Demo Site Request: table created")
    else:
        print("Demo Site Request: creating DocType...")
        dt = frappe.get_doc({
            "doctype": "DocType",
            "name": "Demo Site Request",
            "module": "Press",
            "autoname": "hash",
            "fields": [
                {"fieldname": "company", "fieldtype": "Data", "label": "Company", "in_list_view": 1},
                {"fieldname": "email", "fieldtype": "Data", "label": "Email", "options": "Email", "in_list_view": 1},
                {"fieldname": "phone", "fieldtype": "Data", "label": "Phone"},
                {"fieldname": "site", "fieldtype": "Data", "label": "Site", "in_list_view": 1},
                {"fieldname": "invite_code", "fieldtype": "Data", "label": "Invite Code"},
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}],
        })
        dt.insert(ignore_permissions=True)
        print("Demo Site Request: created")

    # 2. Create Demo Invite Code DocType
    if frappe.db.exists("DocType", "Demo Invite Code"):
        print("Demo Invite Code: already exists")
    else:
        print("Demo Invite Code: creating DocType...")
        dt = frappe.get_doc({
            "doctype": "DocType",
            "name": "Demo Invite Code",
            "module": "Press",
            "autoname": "field:code",
            "sort_field": "creation",
            "sort_order": "DESC",
            "fields": [
                {"fieldname": "code", "fieldtype": "Data", "label": "Invite Code", "reqd": 1, "unique": 1, "in_list_view": 1, "set_only_once": 1},
                {"fieldname": "enabled", "fieldtype": "Check", "label": "Enabled", "default": 1, "in_list_view": 1},
                {"fieldname": "cb1", "fieldtype": "Column Break"},
                {"fieldname": "expires_on", "fieldtype": "Date", "label": "Expires On", "in_list_view": 1},
                {"fieldname": "sb1", "fieldtype": "Section Break", "label": "Restrictions"},
                {"fieldname": "email", "fieldtype": "Data", "label": "Locked to Email", "options": "Email", "description": "If set, only this email can use this code"},
                {"fieldname": "cb2", "fieldtype": "Column Break"},
                {"fieldname": "max_uses", "fieldtype": "Int", "label": "Max Uses", "default": 0, "description": "0 = unlimited"},
                {"fieldname": "used_count", "fieldtype": "Int", "label": "Used Count", "default": 0, "read_only": 1, "in_list_view": 1},
                {"fieldname": "sb2", "fieldtype": "Section Break", "label": "Notes"},
                {"fieldname": "notes", "fieldtype": "Small Text", "label": "Notes"},
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}],
        })
        dt.insert(ignore_permissions=True)
        print("Demo Invite Code: created")

    # 3. Create a default invite code
    if not frappe.db.exists("Demo Invite Code", "ACCU-DEMO-2026"):
        frappe.get_doc({
            "doctype": "Demo Invite Code",
            "code": "ACCU-DEMO-2026",
            "enabled": 1,
            "expires_on": add_days(nowdate(), 90),
            "max_uses": 0,
            "notes": "Default invite code — unlimited uses, 90 day expiry",
        }).insert(ignore_permissions=True)
        print("Default invite code ACCU-DEMO-2026 created (expires in 90 days)")

    frappe.db.commit()
    print("Done")
