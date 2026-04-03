import frappe

def check():
    frappe.set_user("Administrator")

    builds = frappe.get_all("Deploy Candidate Build",
        filters={"deploy_candidate": "deploy-0004-000001"},
        fields=["name", "status", "creation"],
        order_by="creation desc", limit=1)

    if not builds:
        print("No build found for deploy-0004-000001")
        return

    build = frappe.get_doc("Deploy Candidate Build", builds[0].name)
    print(f"Build: {build.name} | Status: {build.status}")

    for step in build.build_steps:
        s = step.as_dict()
        step_name = s.get("step", "?")
        stage = s.get("stage_slug", "?")
        status = s.get("status", "?")
        output = s.get("output", "")
        duration = s.get("duration", "")
        line = f"  {step_name}: {stage} -> {status}"
        if duration:
            line += f" ({duration}s)"
        if output and status in ("Failure", "Running"):
            line += f"\n    Output: {str(output)[:500]}"
        print(line)

    # Check recent errors
    errors = frappe.get_all("Error Log",
        filters={"creation": [">=", "2026-03-08 03:50:00"]},
        fields=["name", "method", "creation"],
        order_by="creation desc", limit=5)
    print(f"\nRecent errors:")
    for e in errors:
        print(f"  {e.name}: {e.method} ({e.creation})")
