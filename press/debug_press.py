import frappe

def debug():
    frappe.set_user("Administrator")

    # Check App Source fields directly
    sources = frappe.db.sql(
        "SELECT name, app, public, enabled, frappe as is_frappe FROM `tabApp Source` LIMIT 20",
        as_dict=True
    )
    print("App Sources:")
    for s in sources:
        print(f"  {s.name}: app={s.app} public={s.public} enabled={s.enabled} frappe={s.is_frappe}")

    # Check Frappe Version
    versions = frappe.db.sql(
        "SELECT name, public, status, `default` FROM `tabFrappe Version`",
        as_dict=True
    )
    print(f"\nFrappe Versions:")
    for v in versions:
        print(f"  {v.name}: public={v.public} status={v.status} default={v.default}")

    # Check App Source Version child records
    asv = frappe.db.sql(
        "SELECT parent, version FROM `tabApp Source Version` LIMIT 20",
        as_dict=True
    )
    print(f"\nApp Source Version records: {len(asv)}")
    for a in asv:
        print(f"  parent={a.parent} version={a.version}")

    # Run the actual joined query
    rows = frappe.db.sql("""
        SELECT asv.version, aps.name as source, aps.app, aps.public, aps.enabled, fv.public as fv_public
        FROM `tabApp Source Version` asv
        LEFT JOIN `tabApp Source` aps ON asv.parent = aps.name
        LEFT JOIN `tabFrappe Version` fv ON asv.version = fv.name
        WHERE aps.enabled = 1 AND aps.public = 1 AND fv.public = 1
    """, as_dict=True)
    print(f"\nJoined query result: {len(rows)} rows")
    for r in rows:
        print(f"  {r}")
