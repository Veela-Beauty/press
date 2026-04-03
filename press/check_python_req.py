import frappe, os, json

def check():
    frappe.set_user("Administrator")
    build = frappe.get_doc("Deploy Candidate Build", "fcjjam3soi")
    dc = frappe.get_doc("Deploy Candidate", build.deploy_candidate)
    
    clone_dir = frappe.db.get_single_value("Press Settings", "clone_directory")
    print(f"Clone dir: {clone_dir}")
    
    for app in dc.apps:
        app_name = app.app
        # Check pyproject.toml in clone
        app_path = os.path.join(clone_dir or "/home/frappe/frappe-bench/clones", app_name)
        pyproject = os.path.join(app_path, "pyproject.toml")
        if os.path.exists(pyproject):
            with open(pyproject) as f:
                content = f.read()
            if "requires-python" in content:
                for line in content.split("\n"):
                    if "requires-python" in line:
                        print(f"  {app_name}: {line.strip()}")
                        break
            else:
                print(f"  {app_name}: no requires-python")
        else:
            print(f"  {app_name}: no pyproject.toml at {pyproject}")

