import frappe

def check():
    frappe.set_user("Administrator")
    build = frappe.get_doc("Deploy Candidate Build", "gv2fvk1ps8")
    print(f"Status: {build.status}")
    for step in build.build_steps:
        s = step.as_dict()
        stage = s.get("stage_slug", "?")
        step_name = s.get("step", "?")
        status = s.get("status", "?")
        output = s.get("output", "")
        line = f"  {step_name}: {stage} -> {status}"
        if output and status == "Failure":
            line += f" | {str(output)[:200]}"
        print(line)
