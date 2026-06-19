import frappe

def execute():
    rgs = frappe.db.get_all("Release Group", filters={"enabled": 1}, fields=["name", "team"])
    print("Release Groups:")
    for r in rgs:
        print(f"  {r.name:25} team={r.team}")

    benches = frappe.db.get_all("Bench", filters={"status": "Active"}, fields=["name", "group", "status"])
    print("\nBenches:")
    for b in benches:
        print(f"  {b.name:25} group={b.group} status={b.status}")
