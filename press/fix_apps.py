import frappe, requests

def fix_missing_releases():
    frappe.set_user("Administrator")
    team = frappe.get_all("Team", filters={"user": "Administrator"}, pluck="name")[0]
    
    # These repos have different default branches
    fixes = [
        {"app": "webshop", "source": "SRC-webshop-001", "repo": "frappe/webshop", "branch": "main"},
        {"app": "wiki", "source": "SRC-wiki-001", "repo": "frappe/wiki", "branch": "main"},
        {"app": "builder", "source": "SRC-builder-001", "repo": "frappe/builder", "branch": "main"},
    ]
    
    for f in fixes:
        # Try different branches
        for branch in ["main", "develop", "version-15", "master"]:
            r = requests.get(f"https://api.github.com/repos/{f[chr(114)+chr(101)+chr(112)+chr(111)]}/commits/{branch}", timeout=10)
            if r.status_code == 200:
                commit = r.json()["sha"]
                print(f"{f[chr(97)+chr(112)+chr(112)]}: found on branch {branch} -> {commit[:10]}")
                
                # Update source branch if different
                frappe.db.set_value("App Source", f["source"], "branch", branch)
                
                existing = frappe.get_all("App Release", filters={"app": f["app"], "source": f["source"]}, pluck="name")
                if not existing:
                    rel = frappe.get_doc({"doctype": "App Release", "app": f["app"], "source": f["source"], "hash": commit, "team": team})
                    rel.insert(ignore_permissions=True)
                    frappe.db.set_value("App Release", rel.name, "status", "Approved")
                    print(f"  Release created")
                else:
                    print(f"  Release exists: {existing[0]}")
                break
            else:
                print(f"  {f[chr(97)+chr(112)+chr(112)]}: branch {branch} -> {r.status_code}")
    
    frappe.db.commit()
    print("Done!")
