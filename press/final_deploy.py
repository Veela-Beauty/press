import frappe

def deploy():
    frappe.set_user("Administrator")

    # Archive all broken benches
    benches = frappe.get_all("Bench",
        filters={"group": "bench-0005", "status": ["in", ["Broken", "Pending"]]},
        pluck="name")
    for b in benches:
        frappe.db.set_value("Bench", b, "status", "Archived")
        print(f"Archived: {b}")

    # Verify the build image is correct
    build = frappe.get_doc("Deploy Candidate Build", "ganrrf1op3")
    print(f"\nBuild image: {build.docker_image}")
    print(f"Build repo: {build.docker_image_repository}")

    # Create deploy
    build.create_deploy()
    frappe.db.commit()

    benches = frappe.get_all("Bench",
        filters={"group": "bench-0005", "status": "Pending"},
        fields=["name", "status"])
    print(f"\nNew bench: {benches}")

    # Check agent jobs
    jobs = frappe.get_all("Agent Job",
        filters={"status": ["in", ["Pending", "Undelivered"]]},
        fields=["name", "job_type", "status"],
        order_by="creation desc", limit=5)
    print(f"\nPending jobs:")
    for j in jobs:
        print(f"  {j.name}: {j.job_type} -> {j.status}")
