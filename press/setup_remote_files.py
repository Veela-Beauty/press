"""
Create Remote File records for the migration backup files and resume migration.
Run: bench --site demo.mvpstorm.com execute press.setup_remote_files.run
"""
import frappe

BASE_URL = "https://autodeploypanel.mvpstorm.com/files/migration_backups"
MIGRATION_NAME = 'jtolj4gnoj'

def run():
    migration = frappe.get_doc('Site Migration', MIGRATION_NAME)
    print(f"Migration status: {migration.status}")
    print(f"Backup ref: {migration.backup}")

    # Create Remote File records with the backup file URLs
    db_remote = frappe.get_doc({
        'doctype': 'Remote File',
        'file_name': 'roseline-sfa-database.sql.gz',
        'file_type': 'application/gzip',
        'file_size': 256513,
        'url': f"{BASE_URL}/roseline-sfa-database.sql.gz",
        'status': 'Available',
    }).insert()
    print(f"Created DB Remote File: {db_remote.name}")

    public_remote = frappe.get_doc({
        'doctype': 'Remote File',
        'file_name': 'roseline-sfa-files.tar',
        'file_type': 'application/x-tar',
        'file_size': 10240,
        'url': f"{BASE_URL}/roseline-sfa-files.tar",
        'status': 'Available',
    }).insert()
    print(f"Created Public Remote File: {public_remote.name}")

    private_remote = frappe.get_doc({
        'doctype': 'Remote File',
        'file_name': 'roseline-sfa-private-files.tar',
        'file_type': 'application/x-tar',
        'file_size': 10240,
        'url': f"{BASE_URL}/roseline-sfa-private-files.tar",
        'status': 'Available',
    }).insert()
    print(f"Created Private Remote File: {private_remote.name}")

    # Create or update SiteBackup record
    if migration.backup:
        backup = frappe.get_doc('Site Backup', migration.backup)
        print(f"Updating existing backup: {backup.name}")
    else:
        backup = frappe.new_doc('Site Backup')
        backup.site = migration.site
        backup.status = 'Success'
        print("Creating new backup record")

    backup.remote_database_file = db_remote.name
    backup.remote_public_file = public_remote.name
    backup.remote_private_file = private_remote.name
    backup.with_files = 1
    backup.offsite = 1
    backup.save()
    frappe.db.commit()
    print(f"Backup record updated: {backup.name}")

    # Update migration backup field
    if not migration.backup:
        migration.backup = backup.name
        migration.save()
        frappe.db.commit()
        print(f"Migration backup set to: {backup.name}")

    # Reset migration to Running and retry from next pending step
    print(f"\nResetting migration status to Running...")
    migration.reload()
    migration.status = 'Running'
    # Reset skipped steps back to pending
    for step in migration.steps:
        if step.step_title == 'Restore site on destination' and step.status == 'Skipped':
            step.status = 'Pending'
            step.step_job = None
            print(f"  Reset step: {step.step_title}")
        elif step.status == 'Skipped':
            step.status = 'Pending'
            print(f"  Reset step: {step.step_title}")
    migration.save()
    frappe.db.commit()

    print(f"\nNow calling run_next_step()...")
    migration.run_next_step()
    frappe.db.commit()
    print(f"Done! Migration status: {migration.status}")
    for step in migration.steps:
        print(f"  [{step.status}] {step.step_title} (job: {step.step_job})")
