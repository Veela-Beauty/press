import frappe

def fix():
    frappe.set_user("Administrator")

    # Check what image the build references
    build = frappe.get_doc("Deploy Candidate Build", "ganrrf1op3")
    dc = frappe.get_doc("Deploy Candidate", build.deploy_candidate)

    # Find all fields that might have the old domain
    print("=== Build fields with demo.mvpstorm.com ===")
    for f in build.meta.fields:
        val = str(getattr(build, f.fieldname, "") or "")
        if "demo.mvpstorm.com" in val:
            print(f"  {f.fieldname}: {val[:100]}")

    print("\n=== DC fields with demo.mvpstorm.com ===")
    for f in dc.meta.fields:
        val = str(getattr(dc, f.fieldname, "") or "")
        if "demo.mvpstorm.com" in val:
            print(f"  {f.fieldname}: {val[:100]}")

    # Check the docker_image fields
    for attr in ["docker_image", "docker_image_repository", "docker_image_tag", "intel_build", "arm_build"]:
        if hasattr(build, attr):
            print(f"\n  build.{attr}: {getattr(build, attr, None)}")
        if hasattr(dc, attr):
            print(f"  dc.{attr}: {getattr(dc, attr, None)}")

    # Update references from demo -> sandbox
    print("\n=== Updating references ===")
    frappe.db.sql("UPDATE `tabDeploy Candidate Build` SET docker_image_repository = REPLACE(docker_image_repository, 'demo.mvpstorm.com', 'sandbox.mvpstorm.com') WHERE docker_image_repository LIKE '%demo.mvpstorm.com%'")
    rows = frappe.db.sql("SELECT COUNT(*) FROM `tabDeploy Candidate Build` WHERE docker_image_repository LIKE '%sandbox%'")[0][0]
    print(f"  Updated {rows} build records")

    # Archive the broken bench
    frappe.db.set_value("Bench", "bench-0005-000001-press-f1-2", "status", "Archived")

    # Try deploy again
    build.reload()
    build.create_deploy()
    frappe.db.commit()
    print("Deploy created!")

    benches = frappe.get_all("Bench",
        filters={"group": "bench-0005"},
        fields=["name", "status"],
        order_by="creation desc", limit=5)
    for b in benches:
        print(f"  {b.name}: {b.status}")
