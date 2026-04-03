import frappe

def run():
    # Check what tables actually exist with "demo" in name
    tables = frappe.db.sql("SHOW TABLES LIKE '%Demo%'", as_list=True)
    print(f"Tables matching 'Demo': {tables}")

    tables2 = frappe.db.sql("SHOW TABLES LIKE '%demo%'", as_list=True)
    print(f"Tables matching 'demo': {tables2}")

    # Try direct SQL table creation
    for dt_name in ["Demo Invite Code", "Demo Site Request"]:
        tab_name = f"tab{dt_name}"
        try:
            count = frappe.db.sql(f"SELECT COUNT(*) FROM `{tab_name}`")[0][0]
            print(f"{tab_name}: EXISTS with {count} rows")
        except Exception as e:
            print(f"{tab_name}: {e}")

    # Check if frappe.db.table_exists uses different logic
    print(f"\nfrappe.db.table_exists('tabDemo Invite Code'): {frappe.db.table_exists('tabDemo Invite Code')}")
    print(f"frappe.db.table_exists('Demo Invite Code'): {frappe.db.table_exists('Demo Invite Code')}")
