import frappe
import subprocess

def create():
    frappe.set_user("Administrator")
    team = frappe.get_all("Team", filters={"user": "Administrator"}, pluck="name")[0]
    dashboard_team = "sqkn1globp"

    print("=" * 60)
    print("Creating AccuBuild Demo Bench")
    print("=" * 60)

    # Apps needed: frappe, erpnext, hrms, payments, accubuild_core
    # payments is useful for construction (payment certificates)
    bench_apps = [
        {"app": "frappe", "source": "SRC-frappe-002"},      # version-15
        {"app": "erpnext", "source": "SRC-erpnext-002"},    # version-15
        {"app": "hrms", "source": "SRC-hrms-001"},          # version-15
        {"app": "payments", "source": "SRC-payments-001"},   # version-15
        {"app": "accubuild_core", "source": "SRC-accubuild_core-001"},  # new_rfq_module
    ]

    # Verify all sources exist and have releases
    print("\nVerifying app sources...")
    for app_info in bench_apps:
        src = frappe.get_doc("App Source", app_info["source"])
        releases = frappe.get_all("App Release",
            filters={"source": app_info["source"], "status": "Approved"},
            fields=["name", "hash"],
            order_by="creation desc", limit=1)

        if releases:
            print(f"  {app_info['app']}: {src.branch} -> {releases[0].hash[:10]} OK")
        else:
            # Need to create a release
            commit = _get_commit(src.repository_url, src.branch)
            if commit:
                rel = frappe.get_doc({
                    "doctype": "App Release",
                    "app": app_info["app"],
                    "source": app_info["source"],
                    "hash": commit,
                    "team": team,
                })
                rel.insert(ignore_permissions=True)
                frappe.db.set_value("App Release", rel.name, "status", "Approved")
                print(f"  {app_info['app']}: {src.branch} -> {commit[:10]} CREATED")
            else:
                print(f"  {app_info['app']}: FAILED to get commit!")
                return

    # Create Release Group
    print("\nCreating Release Group...")
    rg = frappe.get_doc({
        "doctype": "Release Group",
        "title": "AccuBuild Demo",
        "version": "Version 15",
        "team": dashboard_team,
        "enabled": 1,
        "apps": bench_apps,
        "servers": [{"server": "press-f1.demo.mvpstorm.com"}],
    })
    rg.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"  Release Group: {rg.name} ({rg.title})")

    # Create Deploy Candidate
    print("\nCreating Deploy Candidate...")
    dc = rg.create_deploy_candidate()
    frappe.db.commit()
    print(f"  Deploy Candidate: {dc.name}")

    # Print apps in DC
    for app in dc.apps:
        print(f"    {app.app}: {app.source} -> {app.release}")

    # Trigger build
    print("\nTriggering build...")
    dc.build()
    frappe.db.commit()
    print("  Build triggered!")
    print(f"\nMonitor at: https://demo.mvpstorm.com/dashboard/groups/{rg.name}/deploys")


def _get_commit(repo_url, branch):
    try:
        result = subprocess.run(
            ["git", "ls-remote", repo_url, branch],
            capture_output=True, text=True, timeout=15
        )
        if result.stdout:
            return result.stdout.split()[0]
    except Exception:
        pass
    return None
