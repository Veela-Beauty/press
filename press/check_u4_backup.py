"""
Poll the u4 agent for backup job status.
Run: bench --site demo.mvpstorm.com execute press.check_u4_backup.run
"""
import frappe
import requests
from frappe.utils.password import get_decrypted_password

def run():
    server_name = 'u4-default.sandbox.mvpstorm.com'

    # Get decrypted agent password
    agent_password = get_decrypted_password('Server', server_name, 'agent_password')
    print(f"Agent password (last 4): ...{agent_password[-4:]}")

    # Try to get job status directly
    for job_id in [1400, 1401]:
        url = f"https://{server_name}/agent/jobs/{job_id}"
        try:
            resp = requests.get(url, auth=('frappe', agent_password), verify=False, timeout=10)
            print(f"\nJob {job_id} status code: {resp.status_code}")
            print(f"Response: {resp.text[:500]}")
        except Exception as e:
            print(f"Error fetching job {job_id}: {e}")

    # Also poll via Press's mechanism
    print("\n--- Polling via Press ---")
    from press.press.doctype.agent_job.agent_job import poll_pending_jobs_server
    import frappe.utils

    # Force poll (create a simple server object)
    server_obj = frappe.new_doc('Agent Job')
    server_obj.server = server_name
    server_obj.server_type = 'Server'

    # Import Agent
    from press.agent import Agent
    agent = Agent(server_name, server_type='Server')

    try:
        status = agent.get_jobs_status([1400, 1401])
        print(f"Jobs status from agent: {status}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
