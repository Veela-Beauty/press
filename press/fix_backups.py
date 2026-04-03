import frappe

def fix():
    frappe.set_user("Administrator")

    # Enable local backups (no S3 needed)
    ps = frappe.get_doc("Press Settings")
    ps.disable_physical_backup = 0
    ps.backup_interval = 6  # backup every 6 hours
    ps.backup_limit = 3     # keep 3 backups per site
    ps.offsite_backups_count = 0  # no offsite (no S3)
    ps.save(ignore_permissions=True)
    frappe.db.commit()

    print("Backup settings updated:")
    print(f"  Physical backup: enabled")
    print(f"  Interval: every 6 hours")
    print(f"  Limit: 3 per site")
    print(f"  Offsite: disabled (no S3)")

    # Check pending backup status
    pending = frappe.get_all("Site Backup",
        filters={"status": "Pending"},
        fields=["name", "site", "creation"])
    print(f"\nPending backups: {len(pending)}")
    for b in pending:
        print(f"  {b.name}: {b.site}")

    # Poll pending jobs to sync status
    from press.press.doctype.agent_job.agent_job import poll_pending_jobs
    poll_pending_jobs()
    frappe.db.commit()

    # Re-check
    backups = frappe.get_all("Site Backup",
        fields=["name", "site", "status", "creation"],
        order_by="creation desc", limit=5)
    print(f"\nAll backups after poll:")
    for b in backups:
        print(f"  {b.name}: {b.site} -> {b.status}")

    backup_jobs = frappe.get_all("Agent Job",
        filters={"job_type": ["like", "%Backup%"]},
        fields=["name", "job_type", "status"],
        order_by="creation desc", limit=5)
    print(f"\nBackup agent jobs:")
    for j in backup_jobs:
        print(f"  {j.name}: {j.job_type} -> {j.status}")
