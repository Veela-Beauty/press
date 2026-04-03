import frappe
import json

def run():
    # 1. Check current state
    for dt_name in ["Demo Invite Code", "Demo Site Request"]:
        exists = frappe.db.exists("DocType", dt_name)
        table = frappe.db.table_exists(f"tab{dt_name}")
        print(f"{dt_name}: DocType={'YES' if exists else 'NO'}, Table={'YES' if table else 'NO'}")

    # 2. Update Demo Site Request — add Link to invite code + Link to Site
    dt = frappe.get_doc("DocType", "Demo Site Request")
    field_names = [f.fieldname for f in dt.fields]
    print(f"\nDemo Site Request fields: {field_names}")

    changed = False

    # Make invite_code a Link field to Demo Invite Code
    if "invite_code" in field_names:
        for f in dt.fields:
            if f.fieldname == "invite_code" and f.fieldtype != "Link":
                f.fieldtype = "Link"
                f.options = "Demo Invite Code"
                f.in_list_view = 1
                changed = True
                print("  Updated invite_code to Link → Demo Invite Code")
    else:
        dt.append("fields", {
            "fieldname": "invite_code",
            "fieldtype": "Link",
            "label": "Invite Code",
            "options": "Demo Invite Code",
            "in_list_view": 1,
        })
        changed = True
        print("  Added invite_code Link field")

    # Make site a Link field to Site
    if "site" in field_names:
        for f in dt.fields:
            if f.fieldname == "site" and f.fieldtype != "Link":
                f.fieldtype = "Link"
                f.options = "Site"
                f.in_list_view = 1
                changed = True
                print("  Updated site to Link → Site")
    else:
        dt.append("fields", {
            "fieldname": "site",
            "fieldtype": "Link",
            "label": "Site",
            "options": "Site",
            "in_list_view": 1,
        })
        changed = True
        print("  Added site Link field")

    if changed:
        dt.save(ignore_permissions=True)
        print("  Demo Site Request saved")

    # 3. Update Demo Invite Code — add link to see connected Demo Site Requests
    dt2 = frappe.get_doc("DocType", "Demo Invite Code")
    field_names2 = [f.fieldname for f in dt2.fields]
    print(f"\nDemo Invite Code fields: {field_names2}")

    changed2 = False

    # Add a Section Break + HTML field to show linked sites
    if "sb_sites" not in field_names2:
        dt2.append("fields", {
            "fieldname": "sb_sites",
            "fieldtype": "Section Break",
            "label": "Sites Created",
        })
        dt2.append("fields", {
            "fieldname": "sites_html",
            "fieldtype": "HTML",
            "label": "Sites",
        })
        changed2 = True
        print("  Added Sites Created section")

    if changed2:
        dt2.save(ignore_permissions=True)
        print("  Demo Invite Code saved")

    frappe.db.commit()
    print("\nDone — links established")
