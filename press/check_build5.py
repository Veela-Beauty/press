import frappe

def check():
    frappe.set_user("Administrator")
    builds = frappe.get_all("Deploy Candidate Build", filters={"deploy_candidate": "deploy-0002-000002"}, fields=["name"], order_by="creation desc", limit=1)
    if not builds:
        print("No build found")
        return
    build = frappe.get_doc("Deploy Candidate Build", builds[0].name)
    print(f"Build: {build.name} | Status: {build.status}")
    for step in build.build_steps:
        s = step.as_dict()
        step_name = s.get("step", "?")
        stage = s.get("stage_slug", "?")
        status = s.get("status", "?")
        output = s.get("output", "")
        line = f"  {step_name}: {stage} -> {status}"
        if output and status == "Failure":
            line += f" | {str(output)[:300]}"
        print(line)
