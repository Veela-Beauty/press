import frappe

def cancel():
    frappe.set_user("Administrator")

    # Mark all stuck builds for deploy-0005-000002 as Failure
    builds = frappe.get_all("Deploy Candidate Build",
        filters={"deploy_candidate": "deploy-0005-000002", "status": ["in", ["Preparing", "Running", "Pending"]]},
        pluck="name")

    for b in builds:
        frappe.db.set_value("Deploy Candidate Build", b, "status", "Failure")
        print(f"Marked {b} as Failure")

    frappe.db.commit()

    # Confirm bench is active
    benches = frappe.get_all("Bench",
        filters={"group": "bench-0005"},
        fields=["name", "status"])
    print(f"\nBench status:")
    for b in benches:
        print(f"  {b.name}: {b.status}")
