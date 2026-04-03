"""
Auto-advance the migration by polling and processing each pending step.
Run: bench --site demo.mvpstorm.com execute press.auto_advance_migration.run
"""
import frappe
import time
from press.agent import Agent
from press.press.doctype.agent_job.agent_job import handle_polled_job

MIGRATION_NAME = 'jtolj4gnoj'

def get_agent_for_server(server_name):
    server_type = 'Server'
    # Check if it's a proxy server
    if frappe.db.exists('Proxy Server', server_name):
        server_type = 'Proxy Server'
    return Agent(server_name, server_type=server_type)

def poll_and_process_job(agent_job_name):
    job = frappe.get_doc('Agent Job', agent_job_name)
    if not job.job_id:
        print(f"  Job {agent_job_name}: no job_id yet (not sent to agent)")
        return False

    agent = get_agent_for_server(job.server)
    try:
        polled = agent.get_jobs_status([job.job_id])
        if not polled:
            print(f"  Job {agent_job_name}: no status from agent")
            return False
        polled_job = polled[0]
        status = polled_job.get('status')
        print(f"  Job {agent_job_name} ({job.job_type}): agent status = {status}")

        if status in ('Success', 'Failure'):
            handle_polled_job(polled_job=polled_job, job=job)
            frappe.db.commit()
            return True
        return False
    except Exception as e:
        print(f"  Error polling {agent_job_name}: {e}")
        return False

def run():
    migration = frappe.get_doc('Site Migration', MIGRATION_NAME)
    print(f"Migration: {MIGRATION_NAME}, status: {migration.status}")

    if migration.status not in ('Running', 'Pending'):
        print("Migration not in running state, checking if we need to reset...")

    max_rounds = 20
    for round_num in range(max_rounds):
        migration.reload()
        print(f"\n=== Round {round_num+1} ===")
        print(f"Migration status: {migration.status}")

        for step in migration.steps:
            print(f"  [{step.status}] {step.step_title} (job: {step.step_job})")

        if migration.status in ('Success', 'Failure'):
            print(f"\nMigration completed with status: {migration.status}")
            break

        # Find current active step
        active_step = None
        for step in migration.steps:
            if step.status == 'Pending' and step.step_job:
                active_step = step
                break

        if not active_step:
            # Check if next step needs to be triggered
            next_pending = next((s for s in migration.steps if s.status == 'Pending' and not s.step_job), None)
            if next_pending:
                print(f"  Next step {next_pending.step_title} not triggered yet, calling run_next_step()...")
                migration.run_next_step()
                frappe.db.commit()
                migration.reload()
            else:
                print("  No pending steps found")
                break

            active_step = next((s for s in migration.steps if s.status == 'Pending' and s.step_job), None)

        if active_step:
            print(f"\nPolling step: {active_step.step_title} (job: {active_step.step_job})")
            processed = poll_and_process_job(active_step.step_job)
            if not processed:
                print("  Waiting for job to complete...")
                time.sleep(10)
                # Try again
                poll_and_process_job(active_step.step_job)
        else:
            time.sleep(5)

    migration.reload()
    print(f"\n=== FINAL STATUS ===")
    print(f"Migration: {migration.status}")
    for step in migration.steps:
        print(f"  [{step.status}] {step.step_title}")

    # Check site's new location
    site = frappe.get_doc('Site', migration.site)
    print(f"\nSite bench: {site.bench}, server: {site.server}, status: {site.status}")
