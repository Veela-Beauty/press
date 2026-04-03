import frappe

def check():
    frappe.set_user("Administrator")
    build = frappe.get_doc("Deploy Candidate Build", "fcjjam3soi")
    print(f"Status: {build.status}")
    if hasattr(build, "error_msg"):
        print(f"Error: {build.error_msg}")
    if hasattr(build, "traceback"):
        print(f"Traceback: {build.traceback}")
    
    for step in build.build_steps:
        s = step.as_dict()
        print(f"  {s.get(chr(115)+chr(116)+chr(101)+chr(112), chr(63))}: {s.get(chr(115)+chr(116)+chr(97)+chr(103)+chr(101)+chr(95)+chr(115)+chr(108)+chr(117)+chr(103), chr(63))} -> {s.get(chr(115)+chr(116)+chr(97)+chr(116)+chr(117)+chr(115), chr(63))}")
    
    errors = frappe.get_all("Error Log", filters={"creation": [">=", "2026-03-08 00:50:00"]}, fields=["name", "method"], order_by="creation desc", limit=5)
    print(f"\nRecent errors:")
    for e in errors:
        print(f"  {e.name}: {e.method}")
