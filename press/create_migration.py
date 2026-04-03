"""
Manually create and start site migration for roseline-sfa.sandbox.mvpstorm.com
Place in /home/frappe/frappe-bench/apps/press/ and run:
  bench --site demo.mvpstorm.com execute create_migration.run
"""
import frappe

def run():
    site_name = 'roseline-sfa.sandbox.mvpstorm.com'
    target_bench = 'bench-0011-000006-press-f1'

    # Check current site state
    site = frappe.get_doc('Site', site_name)
    print(f"Current: bench={site.bench}, server={site.server}, status={site.status}")

    # Check target bench
    bench = frappe.get_doc('Bench', target_bench)
    print(f"Target bench: status={bench.status}, server={bench.server}")

    if bench.status != 'Active':
        print(f"ERROR: Target bench is not active! Status: {bench.status}")
        return

    if site.bench == target_bench:
        print("Site is already on the target bench!")
        return

    # Check for existing ongoing migration
    from press.press.doctype.site_migration.site_migration import get_ongoing_migration
    existing = get_ongoing_migration(site_name, scheduled=True)
    if existing:
        print(f"Found existing migration: {existing}")
        # Try to run it
        migration = frappe.get_doc('Site Migration', existing)
        print(f"Migration status: {migration.status}")
        if migration.status == 'Scheduled':
            print("Starting existing scheduled migration...")
            migration.start()
            print("Done!")
        return

    # Create new migration
    print(f"\nCreating migration from {site.bench} to {target_bench}...")
    migration = frappe.get_doc({
        'doctype': 'Site Migration',
        'site': site_name,
        'destination_bench': target_bench,
        'destination_server': bench.server,
        'source_bench': site.bench,
        'source_server': site.server,
        'status': 'Scheduled',
    })
    migration.insert()
    frappe.db.commit()
    print(f"Created migration: {migration.name}")

    print("Starting migration...")
    migration.start()
    frappe.db.commit()
    print(f"Migration started! Status: {migration.status}")
    return migration.name
