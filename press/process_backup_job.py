"""
Force-process the completed backup agent job to advance the migration.
Run: bench --site demo.mvpstorm.com execute press.process_backup_job.run
"""
import frappe
from frappe.utils.password import get_decrypted_password
from press.agent import Agent
from press.press.doctype.agent_job.agent_job import handle_polled_job

def run():
    server_name = 'u4-default.sandbox.mvpstorm.com'
    agent = Agent(server_name, server_type='Server')

    # The current active backup job for the migration
    migration_job_name = 'q2vvngal3r'
    backup_job = frappe.get_doc('Agent Job', migration_job_name)
    print(f"Agent Job: {migration_job_name}, job_id: {backup_job.job_id}, status: {backup_job.status}")

    # Poll status from agent
    polled = agent.get_jobs_status([backup_job.job_id])
    if not polled:
        print("Could not get job status from agent!")
        return

    polled_job = polled[0]
    print(f"Agent says job status: {polled_job.get('status')}")
    print(f"Agent job ID match: {polled_job.get('id')} == {backup_job.job_id}")

    # Process the polled result (this updates Press DB and triggers migration callback)
    print("\nProcessing polled job...")
    handle_polled_job(polled_job=polled_job, job=backup_job)
    frappe.db.commit()
    print("Done!")

    # Check migration status
    migration = frappe.get_doc('Site Migration', 'jtolj4gnoj')
    print(f"\nMigration status: {migration.status}")
    for step in migration.steps:
        print(f"  [{step.status}] {step.step_title} (job: {step.step_job})")
