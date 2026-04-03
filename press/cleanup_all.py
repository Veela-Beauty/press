import frappe

def cleanup():
    frappe.set_user("Administrator")

    # 1. Archive all sites
    sites = frappe.get_all("Site", filters={"status": ["!=", "Archived"]}, fields=["name", "status"])
    print(f"=== Sites to archive: {len(sites)} ===")
    for s in sites:
        frappe.db.set_value("Site", s.name, "status", "Archived")
        print(f"  Archived: {s.name} (was {s.status})")

    # 2. Deactivate all benches
    benches = frappe.get_all("Bench", filters={"status": ["!=", "Archived"]}, fields=["name", "status"])
    print(f"\n=== Benches to archive: {len(benches)} ===")
    for b in benches:
        frappe.db.set_value("Bench", b.name, "status", "Archived")
        print(f"  Archived: {b.name} (was {b.status})")

    # 3. Disable all Release Groups (except AccuBuild Demo which we'll rebuild)
    rgs = frappe.get_all("Release Group", fields=["name", "title", "enabled"])
    print(f"\n=== Release Groups: {len(rgs)} ===")
    for rg in rgs:
        frappe.db.set_value("Release Group", rg.name, "enabled", 0)
        print(f"  Disabled: {rg.name} ({rg.title})")

    # 4. Clear all agent jobs
    jobs = frappe.db.count("Agent Job", filters={"status": ["in", ["Pending", "Running", "Undelivered"]]})
    if jobs:
        frappe.db.sql("UPDATE `tabAgent Job` SET status = 'Failure' WHERE status IN ('Pending', 'Running', 'Undelivered')")
        print(f"\n  Cleared {jobs} stuck agent jobs")

    # 5. Clear stuck deploy candidate builds
    stuck_builds = frappe.db.count("Deploy Candidate Build", filters={"status": ["in", ["Preparing", "Running"]]})
    if stuck_builds:
        frappe.db.sql("UPDATE `tabDeploy Candidate Build` SET status = 'Failure' WHERE status IN ('Preparing', 'Running')")
        print(f"  Cleared {stuck_builds} stuck builds")

    frappe.db.commit()
    print("\nCleanup done!")
