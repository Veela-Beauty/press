import frappe
import requests

def add_all_frappe_apps():
    frappe.set_user("Administrator")
    
    apps_to_add = [
        {"app": "hrms", "title": "Frappe HR", "repo": "https://github.com/frappe/hrms", "branch": "version-15"},
        {"app": "payments", "title": "Payments", "repo": "https://github.com/frappe/payments", "branch": "version-15"},
        {"app": "webshop", "title": "Webshop", "repo": "https://github.com/frappe/webshop", "branch": "main"},
        {"app": "print_designer", "title": "Print Designer", "repo": "https://github.com/frappe/print_designer", "branch": "main"},
        {"app": "wiki", "title": "Wiki", "repo": "https://github.com/frappe/wiki", "branch": "main"},
        {"app": "lms", "title": "LMS", "repo": "https://github.com/frappe/lms", "branch": "main"},
        {"app": "builder", "title": "Frappe Builder", "repo": "https://github.com/frappe/builder", "branch": "main"},
        {"app": "helpdesk", "title": "Helpdesk", "repo": "https://github.com/frappe/helpdesk", "branch": "main"},
        {"app": "crm", "title": "Frappe CRM", "repo": "https://github.com/frappe/crm", "branch": "main"},
        {"app": "insights", "title": "Frappe Insights", "repo": "https://github.com/frappe/insights", "branch": "main"},
        {"app": "lending", "title": "Lending", "repo": "https://github.com/frappe/lending", "branch": "develop"},
        {"app": "drive", "title": "Frappe Drive", "repo": "https://github.com/frappe/drive", "branch": "main"},
        {"app": "gameplan", "title": "Gameplan", "repo": "https://github.com/frappe/gameplan", "branch": "main"},
    ]
    
    team = frappe.get_all("Team", filters={"user": "Administrator"}, pluck="name")[0]
    print(f"Team: {team}")
    
    for info in apps_to_add:
        app_name = info["app"]
        print(f"\n--- {app_name} ---")
        
        if not frappe.db.exists("App", app_name):
            frappe.get_doc({"doctype": "App", "name": app_name, "title": info["title"], "frappe": 1}).insert(ignore_permissions=True)
            print(f"  App created")
        else:
            print(f"  App exists")
        
        existing = frappe.get_all("App Source", filters={"app": app_name, "repository_url": info["repo"], "branch": info["branch"]}, pluck="name")
        if not existing:
            src = frappe.get_doc({
                "doctype": "App Source", "app": app_name, "app_title": info["title"],
                "repository_url": info["repo"], "branch": info["branch"],
                "team": team, "versions": [{"version": "Version 15"}],
            })
            src.insert(ignore_permissions=True)
            source_name = src.name
            print(f"  Source: {source_name}")
        else:
            source_name = existing[0]
            print(f"  Source exists: {source_name}")
        
        parts = info["repo"].rstrip("/").split("/")
        owner, repo = parts[-2], parts[-1]
        try:
            r = requests.get(f"https://api.github.com/repos/{owner}/{repo}/commits/{info[chr(98)+chr(114)+chr(97)+chr(110)+chr(99)+chr(104)]}", timeout=10)
            if r.status_code != 200:
                print(f"  SKIP: GitHub {r.status_code}")
                continue
            commit = r.json()["sha"]
        except Exception as e:
            print(f"  SKIP: {e}")
            continue
        
        existing_rel = frappe.get_all("App Release", filters={"app": app_name, "source": source_name, "hash": commit}, pluck="name")
        if not existing_rel:
            rel = frappe.get_doc({"doctype": "App Release", "app": app_name, "source": source_name, "hash": commit, "team": team})
            rel.insert(ignore_permissions=True)
            frappe.db.set_value("App Release", rel.name, "status", "Approved")
            print(f"  Release: {commit[:10]}")
        else:
            print(f"  Release exists")
    
    frappe.db.commit()
    print("\nAll apps registered!")
