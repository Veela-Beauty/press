import frappe

def check_build():
    frappe.set_user("Administrator")
    build = frappe.get_doc("Deploy Candidate Build", "fcjjam3soi")
    print(f"Build: {build.name}")
    print(f"Status: {build.status}")
    print(f"Deploy Candidate: {build.deploy_candidate}")
    
    dc = frappe.get_doc("Deploy Candidate", build.deploy_candidate)
    print(f"\nDC Status: {dc.status if hasattr(dc, chr(115)+chr(116)+chr(97)+chr(116)+chr(117)+chr(115)) else chr(78)+chr(47)+chr(65)}")
    
    if hasattr(build, "build_steps"):
        for step in build.build_steps:
            print(f"  Step {step.step}: {step.step_title} -> {step.status}")
    
    # Check error log
    errors = frappe.get_all("Error Log", filters={"creation": [">=", "2026-03-08 00:50:00"]}, fields=["name", "method"], order_by="creation desc", limit=5)
    print(f"\nRecent errors:")
    for e in errors:
        print(f"  {e.name}: {e.method}")
