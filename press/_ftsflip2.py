import frappe, json
def gwis():
    s = "gwis-stg.sandbox.mvpstorm.com"
    try:
        for n in frappe.db.sql_list("SELECT name FROM `tabSite Update` WHERE site=%s AND status IN ('Pending','Running','Scheduled')", (s,)):
            frappe.db.set_value("Site Update", n, "status", "Failure")
        frappe.db.commit()
        site = frappe.get_doc("Site", s)
        su = site.schedule_update(skip_failing_patches=False, skip_backups=True)
        frappe.db.commit()
        d = frappe.get_doc("Site Update", su); d.start(); frappe.db.commit(); d.reload()
        print("FTSRESULT " + json.dumps({"job": d.get("update_job"), "dest": d.destination_bench, "status": d.status}, default=str))
    except Exception as e:
        print("FTSRESULT " + json.dumps({"err": str(e)[:160]}))
