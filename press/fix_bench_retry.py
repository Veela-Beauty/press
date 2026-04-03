import frappe

def fix():
    frappe.set_user("Administrator")

    # Update the deploy candidate build's docker image reference
    build = frappe.get_doc("Deploy Candidate Build", "ganrrf1op3")

    # Also need to update the docker image name in the DC
    dc = frappe.get_doc("Deploy Candidate", build.deploy_candidate)

    # Check what docker image field exists
    if hasattr(dc, "docker_image"):
        old = dc.docker_image
        dc.docker_image = old.replace("demo.mvpstorm.com", "sandbox.mvpstorm.com") if old else old
        dc.save(ignore_permissions=True)
        print(f"DC docker_image: {old} -> {dc.docker_image}")

    # Archive the broken bench
    frappe.db.set_value("Bench", "bench-0005-000001-press-f1-1", "status", "Archived")
    print("Archived broken bench")

    # Try deploy again
    build.create_deploy()
    frappe.db.commit()
    print("New deploy created!")

    benches = frappe.get_all("Bench",
        filters={"group": "bench-0005", "status": ["!=", "Archived"]},
        fields=["name", "status"],
        order_by="creation desc", limit=3)
    print(f"\nBenches:")
    for b in benches:
        print(f"  {b.name}: {b.status}")
