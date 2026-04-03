import frappe
import subprocess

def setup():
    frappe.set_user("Administrator")
    team = frappe.get_all("Team", filters={"user": "Administrator"}, pluck="name")[0]
    dashboard_team = "sqkn1globp"

    # Apps to add for each version
    versions_config = {
        "Version 14": {
            "frappe": {"repo": "https://github.com/frappe/frappe", "branch": "version-14"},
            "erpnext": {"repo": "https://github.com/frappe/erpnext", "branch": "version-14"},
            "hrms": {"repo": "https://github.com/frappe/hrms", "branch": "version-14"},
            "payments": {"repo": "https://github.com/frappe/payments", "branch": "version-14"},
        },
        "Version 16": {
            "frappe": {"repo": "https://github.com/frappe/frappe", "branch": "develop"},
            "erpnext": {"repo": "https://github.com/frappe/erpnext", "branch": "develop"},
            "hrms": {"repo": "https://github.com/frappe/hrms", "branch": "develop"},
            "payments": {"repo": "https://github.com/frappe/payments", "branch": "develop"},
            "webshop": {"repo": "https://github.com/frappe/webshop", "branch": "develop"},
            "lending": {"repo": "https://github.com/frappe/lending", "branch": "develop"},
            "crm": {"repo": "https://github.com/frappe/crm", "branch": "main"},
            "helpdesk": {"repo": "https://github.com/frappe/helpdesk", "branch": "main"},
            "builder": {"repo": "https://github.com/frappe/builder", "branch": "develop"},
            "insights": {"repo": "https://github.com/frappe/insights", "branch": "develop"},
            "print_designer": {"repo": "https://github.com/frappe/print_designer", "branch": "main"},
            "wiki": {"repo": "https://github.com/frappe/wiki", "branch": "develop"},
            "lms": {"repo": "https://github.com/frappe/lms", "branch": "main"},
            "drive": {"repo": "https://github.com/frappe/drive", "branch": "main"},
            "gameplan": {"repo": "https://github.com/frappe/gameplan", "branch": "main"},
        },
    }

    def get_commit(repo_url, branch):
        parts = repo_url.rstrip("/").split("/")
        owner, repo = parts[-2], parts[-1]
        result = subprocess.run(
            ["git", "ls-remote", f"https://github.com/{owner}/{repo}.git", branch],
            capture_output=True, text=True, timeout=15
        )
        if result.stdout:
            return result.stdout.split()[0]
        return None

    for version_name, apps in versions_config.items():
        print(f"\n{'='*50}")
        print(f"Setting up {version_name}")
        print(f"{'='*50}")

        # Make version public
        frappe.db.set_value("Frappe Version", version_name, "public", 1)

        for app_name, info in apps.items():
            repo = info["repo"]
            branch = info["branch"]
            print(f"\n--- {app_name} ({branch}) ---")

            # Check if branch exists
            commit = get_commit(repo, branch)
            if not commit:
                print(f"  SKIP: branch {branch} not found")
                continue

            # Create App if not exists
            if not frappe.db.exists("App", app_name):
                frappe.get_doc({"doctype": "App", "name": app_name, "title": app_name.title(), "frappe": 1}).insert(ignore_permissions=True)
                print(f"  App created")

            # Check if App Source exists for this version/branch combo
            existing = frappe.get_all("App Source", filters={
                "app": app_name, "repository_url": repo, "branch": branch
            }, pluck="name")

            if not existing:
                src = frappe.get_doc({
                    "doctype": "App Source",
                    "app": app_name,
                    "app_title": app_name.replace("_", " ").title(),
                    "repository_url": repo,
                    "branch": branch,
                    "team": dashboard_team,
                    "public": 1,
                    "enabled": 1,
                    "frappe": 1,
                    "versions": [{"version": version_name}],
                })
                src.insert(ignore_permissions=True)
                source_name = src.name
                print(f"  Source created: {source_name}")
            else:
                source_name = existing[0]
                # Make sure it has the version
                src_doc = frappe.get_doc("App Source", source_name)
                version_exists = any(v.version == version_name for v in src_doc.versions)
                if not version_exists:
                    src_doc.append("versions", {"version": version_name})
                    src_doc.save(ignore_permissions=True)
                    print(f"  Added {version_name} to existing source {source_name}")
                else:
                    print(f"  Source exists: {source_name}")
                # Ensure public and frappe flags
                frappe.db.set_value("App Source", source_name, {"public": 1, "frappe": 1, "enabled": 1})

            # Create App Release
            existing_rel = frappe.get_all("App Release", filters={
                "app": app_name, "source": source_name, "hash": commit
            }, pluck="name")
            if not existing_rel:
                rel = frappe.get_doc({
                    "doctype": "App Release",
                    "app": app_name,
                    "source": source_name,
                    "hash": commit,
                    "team": team,
                })
                rel.insert(ignore_permissions=True)
                frappe.db.set_value("App Release", rel.name, "status", "Approved")
                print(f"  Release: {commit[:10]}")
            else:
                print(f"  Release exists")

    frappe.db.commit()

    # Summary
    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    for v in ["Version 14", "Version 15", "Version 16"]:
        fv = frappe.get_doc("Frappe Version", v)
        sources = frappe.db.sql("""
            SELECT aps.app, aps.branch, aps.name
            FROM `tabApp Source Version` asv
            JOIN `tabApp Source` aps ON asv.parent = aps.name
            WHERE asv.version = %s AND aps.enabled = 1 AND aps.public = 1
        """, v, as_dict=True)
        print(f"\n{v} (public={fv.public}): {len(sources)} apps")
        for s in sources:
            print(f"  {s.app} ({s.branch}) -> {s.name}")
