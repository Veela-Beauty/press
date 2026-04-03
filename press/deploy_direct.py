import frappe

def deploy():
    frappe.set_user("Administrator")

    # Cancel the stuck build
    frappe.db.set_value("Deploy Candidate Build", "04n095cg4j", "status", "Failure")

    # The first build succeeded - use it to deploy on new server name
    # We need to create the bench directly since the docker image already exists
    build = frappe.get_doc("Deploy Candidate Build", "ganrrf1op3")
    print(f"Using successful build: {build.name}")

    # Create deploy
    build.create_deploy()
    frappe.db.commit()
    print("Deploy created!")

    # Check
    benches = frappe.get_all("Bench",
        filters={"group": "bench-0005"},
        fields=["name", "status"],
        order_by="creation desc", limit=3)
    print(f"\nBenches:")
    for b in benches:
        print(f"  {b.name}: {b.status}")
