import frappe

def fix():
    frappe.set_user("Administrator")

    # Update ALL references from demo.mvpstorm.com to sandbox.mvpstorm.com in build records
    frappe.db.sql("""
        UPDATE `tabDeploy Candidate Build`
        SET docker_image = REPLACE(docker_image, 'demo.mvpstorm.com', 'sandbox.mvpstorm.com')
        WHERE docker_image LIKE '%demo.mvpstorm.com%'
    """)
    print("Updated docker_image fields")

    frappe.db.sql("""
        UPDATE `tabDeploy Candidate Build`
        SET docker_image_repository = REPLACE(docker_image_repository, 'demo.mvpstorm.com', 'sandbox.mvpstorm.com')
        WHERE docker_image_repository LIKE '%demo.mvpstorm.com%'
    """)
    print("Updated docker_image_repository fields")

    frappe.db.commit()

    # Verify
    build = frappe.get_doc("Deploy Candidate Build", "ganrrf1op3")
    print(f"\nBuild ganrrf1op3:")
    print(f"  docker_image: {build.docker_image}")
    print(f"  docker_image_repository: {build.docker_image_repository}")

    # Now poll to check the pending bench
    from press.press.doctype.agent_job.agent_job import poll_pending_jobs
    poll_pending_jobs()
    frappe.db.commit()

    benches = frappe.get_all("Bench",
        filters={"group": "bench-0005"},
        fields=["name", "status"],
        order_by="creation desc", limit=5)
    print(f"\nBenches:")
    for b in benches:
        print(f"  {b.name}: {b.status}")

    jobs = frappe.get_all("Agent Job",
        filters={"job_type": "New Bench"},
        fields=["name", "status", "creation"],
        order_by="creation desc", limit=3)
    print(f"\nNew Bench jobs:")
    for j in jobs:
        print(f"  {j.name}: {j.status}")
