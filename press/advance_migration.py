"""
Advance a stuck migration manually.
Run: bench --site demo.mvpstorm.com execute press.advance_migration.run
"""
import frappe

def run():
    migration_name = 'jtolj4gnoj'
    migration = frappe.get_doc('Site Migration', migration_name)

    print(f"Migration status: {migration.status}")
    print("Steps:")
    for step in migration.steps:
        print(f"  [{step.status}] {step.step_title} (job: {step.step_job})")

    # Find next pending step
    next_step = None
    for step in migration.steps:
        if step.status in ['Pending', 'Running']:
            next_step = step
            break

    if not next_step:
        print("No pending steps found!")
        return

    print(f"\nNext step: {next_step.step_title}")
    print("Calling run_next_step()...")

    try:
        migration.run_next_step()
        frappe.db.commit()
        print(f"Done! Migration status: {migration.status}")
        for step in migration.steps:
            print(f"  [{step.status}] {step.step_title} (job: {step.step_job})")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
