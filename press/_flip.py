import frappe, json
def flip(sites=None):
    out = []
    for s in (sites or []):
        try:
            for n in frappe.db.sql_list("SELECT name FROM `tabSite Update` WHERE site=%s AND status IN ('Pending','Running','Scheduled')", (s,)):
                frappe.db.set_value("Site Update", n, "status", "Failure")
            frappe.db.commit()
            site = frappe.get_doc("Site", s)
            su = site.schedule_update(skip_failing_patches=False, skip_backups=True)
            frappe.db.commit()
            d = frappe.get_doc("Site Update", su); d.start(); frappe.db.commit(); d.reload()
            out.append({"site": s, "update": su, "job": d.get("update_job"), "dest": d.destination_bench, "status": d.status})
        except Exception as e:
            out.append({"site": s, "err": str(e)[:140]})
    print("RESULT " + json.dumps(out, default=str)[:2500])
