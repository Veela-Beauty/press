import frappe
import subprocess

def fix():
    frappe.set_user("Administrator")
    team = frappe.get_all("Team", filters={"user": "Administrator"}, pluck="name")[0]
    dashboard_team = "sqkn1globp"

    # Update v16 app sources to use version-16 branch
    updates = {
        "SRC-frappe-004": "version-16",
        "SRC-erpnext-004": "version-16",
        "SRC-hrms-003": "version-16",
        # payments stays on develop (no version-16 branch)
    }

    for src_name, new_branch in updates.items():
        if frappe.db.exists("App Source", src_name):
            old_branch = frappe.db.get_value("App Source", src_name, "branch")
            frappe.db.set_value("App Source", src_name, "branch", new_branch)
            print(f"Updated {src_name}: {old_branch} -> {new_branch}")

            # Create release for new branch
            app = frappe.db.get_value("App Source", src_name, "app")
            result = subprocess.run(
                ["git", "ls-remote", f"https://github.com/frappe/{app}.git", new_branch],
                capture_output=True, text=True, timeout=15
            )
            if result.stdout:
                commit = result.stdout.split()[0]
                existing = frappe.get_all("App Release",
                    filters={"source": src_name, "hash": commit}, pluck="name")
                if not existing:
                    rel = frappe.get_doc({
                        "doctype": "App Release", "app": app,
                        "source": src_name, "hash": commit, "team": team
                    })
                    rel.insert(ignore_permissions=True)
                    frappe.db.set_value("App Release", rel.name, "status", "Approved")
                    print(f"  New release: {commit[:10]}")
                else:
                    print(f"  Release exists")

    frappe.db.commit()

    # Now update the Release Group bench-0004 apps to use correct sources
    rg_name = "bench-0004"
    if frappe.db.exists("Release Group", rg_name):
        rg = frappe.get_doc("Release Group", rg_name)
        print(f"\nRelease Group {rg_name}: {len(rg.apps)} apps")
        for app in rg.apps:
            print(f"  {app.app}: {app.source}")

        # Create new deploy candidate
        dc = rg.create_deploy_candidate()
        frappe.db.commit()
        print(f"\nNew Deploy Candidate: {dc.name}")

        dc.build()
        frappe.db.commit()
        print("Build triggered!")
    else:
        print(f"\nRelease Group {rg_name} not found")
