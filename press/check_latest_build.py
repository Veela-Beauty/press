import frappe

def check():
    frappe.set_user("Administrator")

    # Get ALL builds for bench-0004
    builds = frappe.get_all("Deploy Candidate Build",
        filters={"deploy_candidate": ["like", "deploy-0004%"]},
        fields=["name", "deploy_candidate", "status", "creation"],
        order_by="creation desc", limit=5)

    for b in builds:
        print(f"\n{'='*50}")
        print(f"Build: {b.name} | DC: {b.deploy_candidate} | Status: {b.status}")
        build = frappe.get_doc("Deploy Candidate Build", b.name)
        for step in build.build_steps:
            s = step.as_dict()
            status = s.get("status", "?")
            output = s.get("output", "")
            line = f"  {s.get('step', '?')}: {s.get('stage_slug', '?')} -> {status}"
            if output and status == "Failure":
                line += f"\n    {str(output)[:300]}"
            print(line)

    # Check latest error
    err = frappe.get_all("Error Log",
        filters={"creation": [">=", "2026-03-08 07:00:00"]},
        fields=["name", "method"],
        order_by="creation desc", limit=3)
    print(f"\nRecent errors:")
    for e in err:
        print(f"  {e.name}: {e.method}")

    if err:
        error_text = frappe.db.get_value("Error Log", err[0].name, "error")
        # Print last 500 chars of the error
        print(f"\nLatest error detail:\n{error_text[-800:]}")
