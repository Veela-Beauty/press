"""
Check the restore job status on press-f1 agent and process it.
Run: bench --site demo.mvpstorm.com execute press.check_restore_on_agent.run
"""
import frappe
from press.agent import Agent
from press.press.doctype.agent_job.agent_job import handle_polled_job

def run():
    server_name = 'press-f1.sandbox.mvpstorm.com'
    agent = Agent(server_name, server_type='Server')

    restore_job = frappe.get_doc('Agent Job', 'v1ce6ivfo5')
    print(f"Restore Job: {restore_job.name}, job_id: {restore_job.job_id}, status: {restore_job.status}")

    # Poll status from press-f1 agent
    try:
        polled = agent.get_jobs_status([restore_job.job_id])
        if polled:
            polled_job = polled[0]
            print(f"Agent status: {polled_job.get('status')}")
            print(f"Steps: {[s.get('name') + '=' + s.get('status') for s in polled_job.get('steps', [])]}")

            if polled_job.get('status') == 'Success':
                print("\nRestoration completed! Processing job update...")
                handle_polled_job(polled_job=polled_job, job=restore_job)
                frappe.db.commit()
                migration = frappe.get_doc('Site Migration', 'jtolj4gnoj')
                print(f"Migration status: {migration.status}")
                for step in migration.steps:
                    print(f"  [{step.status}] {step.step_title}")
            elif polled_job.get('status') == 'Failure':
                print("\nRestoration FAILED!")
                print(f"Error details: {polled_job}")
                handle_polled_job(polled_job=polled_job, job=restore_job)
                frappe.db.commit()
            else:
                print(f"\nJob still {polled_job.get('status')} - check again later")
        else:
            print("No status returned from agent")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
