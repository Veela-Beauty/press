import frappe, requests

def fix():
    frappe.set_user("Administrator")
    team = frappe.get_all("Team", filters={"user": "Administrator"}, pluck="name")[0]
    
    # Fix webshop and lending to use version-15 branch
    fixes = {
        "SRC-webshop-001": "version-15",
        "SRC-lending-001": "version-15",
    }
    
    for src_name, branch in fixes.items():
        frappe.db.set_value("App Source", src_name, "branch", branch)
        print(f"Fixed {src_name} -> {branch}")
        
        # Create release for new branch
        src = frappe.get_doc("App Source", src_name)
        parts = src.repository_url.rstrip("/").split("/")
        owner, repo = parts[-2], parts[-1]
        
        import subprocess
        result = subprocess.run(["git", "ls-remote", f"https://github.com/{owner}/{repo}.git", branch], capture_output=True, text=True)
        commit = result.stdout.split()[0] if result.stdout else None
        
        if commit:
            existing = frappe.get_all("App Release", filters={"app": src.app, "source": src_name, "hash": commit}, pluck="name")
            if not existing:
                rel = frappe.get_doc({"doctype": "App Release", "app": src.app, "source": src_name, "hash": commit, "team": team})
                rel.insert(ignore_permissions=True)
                frappe.db.set_value("App Release", rel.name, "status", "Approved")
                print(f"  Release: {commit[:10]}")
            else:
                print(f"  Release exists")
    
    # Delete old bench-0002 Release Group
    rg = frappe.get_doc("Release Group", "bench-0002")
    
    # Remove incompatible apps (keep only frappe, erpnext, hrms, payments, webshop, lending)
    compatible = ["frappe", "erpnext", "hrms", "payments", "webshop", "lending"]
    rg.apps = [a for a in rg.apps if a.app in compatible]
    rg.save(ignore_permissions=True)
    
    print(f"\nRelease Group {rg.name} updated with {len(rg.apps)} apps:")
    for a in rg.apps:
        print(f"  {a.app}: {a.source}")
    
    frappe.db.commit()
    print("\nDone! Now create a new Deploy Candidate.")
