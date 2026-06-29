import frappe, json
SITES = ["gwis-stg","sppf-stg","alshamal-feeds-demo","selfstorage-stg","stlube-stg","demov15recoding","bkalf-dev"]
def status():
    out = []
    for s in SITES:
        fq = s + ".sandbox.mvpstorm.com"
        st = frappe.db.get_value("Site", fq, ["status","bench"], as_dict=True)
        out.append({"site": s, "status": st.status if st else None, "on_204": (st.bench or "").endswith("000204-press-f1") if st else None})
    print("RESULT " + json.dumps(out, default=str))
