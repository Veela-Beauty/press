import frappe

def verify():
    frappe.set_user("Administrator")

    # Check backup record
    backups = frappe.get_all("Site Backup",
        fields=["name", "site", "status", "with_files", "database_file",
                "public_file", "private_file", "config_file", "database_size",
                "public_size", "private_size", "creation"],
        order_by="creation desc", limit=5)

    print("=== Backups ===")
    for b in backups:
        print(f"\n  {b.name}: {b.site}")
        print(f"    Status: {b.status}")
        print(f"    With files: {b.with_files}")
        print(f"    DB file: {b.database_file}")
        print(f"    DB size: {b.database_size}")
        print(f"    Public file: {b.public_file}")
        print(f"    Private file: {b.private_file}")
        print(f"    Config file: {b.config_file}")

    # Check if restore is available
    print("\n=== Restore Capability ===")
    print("Restore works by creating an Agent Job 'Restore Site' which:")
    print("  1. Downloads the backup files from the server")
    print("  2. Restores the database")
    print("  3. Restores the files")
    print("  4. Runs bench migrate")
    print("\nTo test: use dashboard Site > Actions > Restore")
