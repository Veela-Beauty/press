import frappe, json

SITES_0006 = [
    "sppf-stg.sandbox.mvpstorm.com", "alshamal-feeds-demo.sandbox.mvpstorm.com",
    "gwis-stg.sandbox.mvpstorm.com", "selfstorage-stg.sandbox.mvpstorm.com",
    "stlube-stg.sandbox.mvpstorm.com", "demov15recoding.sandbox.mvpstorm.com",
    "bkalf-dev.sandbox.mvpstorm.com",
]

def run():
    out = []
    for s in SITES_0006:
        try:
            for n in frappe.db.sql_list("SELECT name FROM `tabSite Update` WHERE site=%s AND status IN ('Pending','Running','Scheduled')", (s,)):
                frappe.db.set_value("Site Update", n, "status", "Failure")
            frappe.db.commit()
            site = frappe.get_doc("Site", s)
            su = site.schedule_update(skip_failing_patches=False, skip_backups=True)
            frappe.db.commit()
            d = frappe.get_doc("Site Update", su); d.start(); frappe.db.commit(); d.reload()
            out.append({"site": s.split(".")[0], "job": d.get("update_job"), "dest": d.destination_bench, "status": d.status})
        except Exception as e:
            out.append({"site": s.split(".")[0], "err": str(e)[:120]})
    print("FTSRESULT " + json.dumps(out, default=str))
