import frappe

def check():
    frappe.set_user("Administrator")
    builds = frappe.get_all("Deploy Candidate Build",
        filters={"deploy_candidate": ["like", "deploy-0005%"]},
        fields=["name", "deploy_candidate", "status", "creation"],
        order_by="creation desc", limit=3)

    for b in builds:
        build = frappe.get_doc("Deploy Candidate Build", b.name)
        print(f"\nBuild: {b.name} | DC: {b.deploy_candidate} | Status: {b.status}")
        for step in build.build_steps:
            s = step.as_dict()
            status = s.get("status", "?")
            output = s.get("output", "")
            line = f"  {s.get('step', '?')}: {s.get('stage_slug', '?')} -> {status}"
            if output and status == "Failure":
                line += f"\n    {str(output)[:300]}"
            print(line)
