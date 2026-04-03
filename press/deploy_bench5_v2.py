import frappe

def deploy():
    frappe.set_user("Administrator")

    # The successful build
    build = frappe.get_doc("Deploy Candidate Build", "ganrrf1op3")
    print(f"Build: {build.name} | Status: {build.status}")

    # Create deploy from the build
    build.create_deploy()
    frappe.db.commit()
    print("Deploy created!")

    # Check for new bench
    benches = frappe.get_all("Bench",
        filters={"group": "bench-0005"},
        fields=["name", "status"],
        order_by="creation desc", limit=3)
    print(f"\nBenches:")
    for b in benches:
        print(f"  {b.name}: {b.status}")

    # Check agent jobs
    jobs = frappe.get_all("Agent Job",
        filters={"status": ["in", ["Pending", "Running", "Undelivered"]]},
        fields=["name", "job_type", "status"],
        order_by="creation desc", limit=5)
    print(f"\nPending jobs:")
    for j in jobs:
        print(f"  {j.name}: {j.job_type} -> {j.status}")
