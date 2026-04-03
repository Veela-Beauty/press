"""
Script to check and trigger site migration for roseline-sfa.sandbox.mvpstorm.com
Run on press-ctrl:
  bench --site demo.mvpstorm.com execute trigger_migration.check_and_trigger
"""
import frappe

def check_and_trigger():
    site_name = 'roseline-sfa.sandbox.mvpstorm.com'
    target_bench = 'bench-0011-000006-press-f1'

    # Check existing migrations
    migrations = frappe.db.get_all(
        'Site Migration',
        filters={'site': site_name},
        fields=['name', 'status', 'source_bench', 'destination_bench', 'scheduled_time', 'creation'],
        order_by='creation desc',
        limit=5
    )
    print(f"Found {len(migrations)} migration records:")
    for m in migrations:
        print(f"  {m}")

    # Check site current state
    site = frappe.get_doc('Site', site_name)
    print(f"\nSite status: {site.status}, Bench: {site.bench}, Server: {site.server}")

    # Check target bench
    bench = frappe.get_doc('Bench', target_bench)
    print(f"Target bench status: {bench.status}, Server: {bench.server}")

    # Check scheduler
    print(f"\nScheduler enabled: {not frappe.utils.cint(frappe.db.get_value('System Settings', 'System Settings', 'enable_scheduler') == 0)}")

    return {
        'migrations': [dict(m) for m in migrations],
        'site': {'status': site.status, 'bench': site.bench},
        'bench': {'status': bench.status, 'server': bench.server}
    }
