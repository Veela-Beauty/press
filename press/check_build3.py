import frappe

def check():
    frappe.set_user("Administrator")
    build = frappe.get_doc("Deploy Candidate Build", "fcjjam3soi")
    
    for step in build.build_steps:
        s = step.as_dict()
        if s.get("status") == "Failure":
            print(f"Failed step: {s.get(chr(115)+chr(116)+chr(97)+chr(103)+chr(101)+chr(95)+chr(115)+chr(108)+chr(117)+chr(103))}")
            print(f"Output: {s.get(chr(111)+chr(117)+chr(116)+chr(112)+chr(117)+chr(116), chr(78)+chr(111)+chr(110)+chr(101))}")
            print(f"Command: {s.get(chr(99)+chr(111)+chr(109)+chr(109)+chr(97)+chr(110)+chr(100), chr(78)+chr(111)+chr(110)+chr(101))}")
            # Print all fields to see what we have
            for k, v in s.items():
                if v and k not in ["name", "parent", "parenttype", "parentfield", "doctype", "idx", "owner", "creation", "modified", "modified_by", "docstatus"]:
                    val = str(v)[:500]
                    print(f"  {k}: {val}")
