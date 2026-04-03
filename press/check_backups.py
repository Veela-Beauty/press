import frappe

def check():
    frappe.set_user("Administrator")

    # Check Press Settings backup config
    ps = frappe.get_doc("Press Settings")
    print("=== Backup Settings ===")
    print(f"  offsite_backups_provider: {ps.offsite_backups_provider}")
    print(f"  offsite_backups_count: {ps.offsite_backups_count}")
    print(f"  backup_interval: {ps.backup_interval}")
    print(f"  backup_offset: {ps.backup_offset}")
    print(f"  backup_limit: {ps.backup_limit}")
    print(f"  disable_physical_backup: {ps.disable_physical_backup}")

    # Check if any backups exist
    backups = frappe.get_all("Site Backup",
        fields=["name", "site", "status", "with_files", "offsite", "creation"],
        order_by="creation desc", limit=10)
    print(f"\n=== Recent Backups: {len(backups)} ===")
    for b in backups:
        print(f"  {b.name}: site={b.site} status={b.status} files={b.with_files} offsite={b.offsite} created={b.creation}")

    # Check active sites
    sites = frappe.get_all("Site", filters={"status": "Active"}, fields=["name", "status"])
    print(f"\n=== Active Sites: {len(sites)} ===")
    for s in sites:
        print(f"  {s.name}")

    # Check scheduled backup job
    sjt = frappe.get_all("Scheduled Job Type",
        filters={"method": ["like", "%backup%"]},
        fields=["name", "method", "cron_format", "stopped", "last_execution"],
        limit=10)
    print(f"\n=== Backup Scheduled Jobs ===")
    for s in sjt:
        print(f"  {s.name}: {s.method}")
        print(f"    cron={s.cron_format} stopped={s.stopped} last={s.last_execution}")

    # Check if backup/restore agent jobs exist
    backup_jobs = frappe.get_all("Agent Job",
        filters={"job_type": ["like", "%Backup%"]},
        fields=["name", "job_type", "status", "creation"],
        order_by="creation desc", limit=5)
    print(f"\n=== Backup Agent Jobs ===")
    for j in backup_jobs:
        print(f"  {j.name}: {j.job_type} -> {j.status} ({j.creation})")
    if not backup_jobs:
        print("  None yet")

    restore_jobs = frappe.get_all("Agent Job",
        filters={"job_type": ["like", "%Restore%"]},
        fields=["name", "job_type", "status", "creation"],
        order_by="creation desc", limit=5)
    print(f"\n=== Restore Agent Jobs ===")
    for j in restore_jobs:
        print(f"  {j.name}: {j.job_type} -> {j.status} ({j.creation})")
    if not restore_jobs:
        print("  None yet")
