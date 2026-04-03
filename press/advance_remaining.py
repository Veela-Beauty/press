"""
Advance all remaining pending migration steps.
Run: bench --site demo.mvpstorm.com execute press.advance_remaining.run
"""
import frappe
import time
from press.agent import Agent
from press.press.doctype.agent_job.agent_job import handle_polled_job

MIGRATION_NAME = 'jtolj4gnoj'

def get_agent(server_name, job_type=None):
    # Determine server type from context
    if frappe.db.exists('Proxy Server', server_name):
        return Agent(server_name, server_type='Proxy Server')
    return Agent(server_name, server_type='Server')

def poll_job(job_name):
    job = frappe.get_doc('Agent Job', job_name)
    if not job.job_id:
        return None, None

    agent = get_agent(job.server, job.job_type)
    try:
        polled = agent.get_jobs_status([job.job_id])
        if polled:
            return polled[0], job
    except Exception as e:
        print(f"  Error polling {job_name}: {e}")
    return None, job

def send_job_if_needed(step):
    """Force send a pending job that has no job_id"""
    job = frappe.get_doc('Agent Job', step.step_job)
    if not job.job_id:
        print(f"  Force-sending job {step.step_job}...")
        job.create_http_request()
        frappe.db.commit()
        job.reload()
        print(f"  Sent: job_id = {job.job_id}")
    return job

def run():
    for attempt in range(30):
        migration = frappe.get_doc('Site Migration', MIGRATION_NAME)
        print(f"\n=== Attempt {attempt+1} | Migration: {migration.status} ===")

        if migration.status in ('Success', 'Failure'):
            break

        # Show all steps
        for step in migration.steps:
            print(f"  [{step.status}] {step.step_title} (job: {step.step_job})")

        # Find the active pending step with a job
        active_step = next((s for s in migration.steps if s.status == 'Pending' and s.step_job), None)

        if not active_step:
            # Find pending step without job — trigger it
            next_step = next((s for s in migration.steps if s.status == 'Pending' and not s.step_job), None)
            if next_step:
                print(f"\nCalling run_next_step() to trigger: {next_step.step_title}")
                migration.run_next_step()
                frappe.db.commit()
                migration.reload()
                active_step = next((s for s in migration.steps if s.status == 'Pending' and s.step_job), None)
            else:
                print("No pending steps. Done or stuck.")
                break

        if active_step:
            # Force send if no job_id
            job = send_job_if_needed(active_step)
            if not job.job_id:
                print(f"  Job still has no id, waiting...")
                time.sleep(10)
                continue

            # Poll status
            polled_job, job = poll_job(active_step.step_job)
            if polled_job:
                status = polled_job.get('status')
                print(f"\nStep: {active_step.step_title}")
                print(f"  Status: {status}")
                if status in ('Success', 'Failure', 'Undelivered'):
                    handle_polled_job(polled_job=polled_job, job=job)
                    frappe.db.commit()
                    print(f"  Processed! Advancing...")
                    continue
                else:
                    print(f"  Still {status}, waiting 15s...")
                    time.sleep(15)
            else:
                print(f"  No status from agent, waiting 10s...")
                time.sleep(10)

    migration.reload()
    print(f"\n=== FINAL ===")
    print(f"Migration: {migration.status}")
    for step in migration.steps:
        print(f"  [{step.status}] {step.step_title}")

    site = frappe.get_doc('Site', migration.site)
    print(f"\nSite: bench={site.bench}, server={site.server}, status={site.status}")
    print(f"URL: https://{site.name}")
