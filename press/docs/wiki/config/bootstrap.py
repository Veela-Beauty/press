"""
Press Self-Hosted Bootstrap Script
===================================
Applies all settings from press_config.json to a fresh Press installation.

Usage:
  1. Install Press app and create site
  2. Run: bench --site YOUR_SITE migrate
  3. Edit press_config.json with your values (domain, IPs, secrets)
  4. Copy this file + press_config.json to apps/press/press/
  5. Run: bench --site YOUR_SITE execute press.bootstrap_selfhosted.run

Prerequisites:
  - Press app installed and migrated
  - Server 2 provisioned with agent running
  - SSL certs obtained
  - Docker registry running
"""

import frappe
import json
import subprocess
import os


def run():
    """Main bootstrap function — call via bench execute"""
    frappe.set_user("Administrator")

    config_path = os.path.join(os.path.dirname(__file__), "press_config.json")
    if not os.path.exists(config_path):
        # Try relative to bench
        config_path = os.path.join(frappe.get_app_path("press"), "press_config.json")

    if not os.path.exists(config_path):
        print("ERROR: press_config.json not found!")
        print("Place it next to this script or in apps/press/press/")
        return

    with open(config_path) as f:
        config = json.load(f)

    print("=" * 60)
    print("Press Self-Hosted Bootstrap")
    print("=" * 60)

    # Get or create team
    teams = frappe.get_all("Team", filters={"user": "Administrator"}, pluck="name")
    if not teams:
        print("\nERROR: No team found for Administrator. Create one first via dashboard signup.")
        return
    admin_team = teams[0]
    print(f"\nAdmin team: {admin_team}")

    # Check for dashboard team
    dashboard_teams = frappe.get_all("Team", filters={"user": ["!=", "Administrator"]}, pluck="name")
    dashboard_team = dashboard_teams[0] if dashboard_teams else admin_team
    print(f"Dashboard team: {dashboard_team}")

    # 1. Press Settings
    print("\n--- Press Settings ---")
    ps = frappe.get_doc("Press Settings")
    ps_config = config["press_settings"]
    for key, value in ps_config.items():
        if value and value not in ("REPLACE_ME", "REPLACE_WITH_SECRET", "REPLACE_WITH_PEM"):
            setattr(ps, key, value)
    ps.save(ignore_permissions=True)
    print("  Updated")

    # 2. Cluster
    print("\n--- Cluster ---")
    cl = config["cluster"]
    if not frappe.db.exists("Cluster", cl["name"]):
        frappe.get_doc({"doctype": "Cluster", **cl}).insert(ignore_permissions=True)
        print(f"  Created: {cl['name']}")
    else:
        frappe.db.set_value("Cluster", cl["name"], cl)
        print(f"  Updated: {cl['name']}")

    # 3. Frappe Versions
    print("\n--- Frappe Versions ---")
    for name, vals in config["frappe_versions"].items():
        if frappe.db.exists("Frappe Version", name):
            frappe.db.set_value("Frappe Version", name, vals)
            print(f"  Updated: {name} (public={vals['public']})")

    # 4. Apps + App Sources + App Releases
    for version_key in ["v14_apps", "v15_apps"]:
        version_name = "Version 14" if "v14" in version_key else "Version 15"
        apps_config = config.get(version_key, {})
        if not apps_config:
            continue

        print(f"\n--- {version_name} Apps ---")
        for app_name, info in apps_config.items():
            repo = info["repo"]
            branch = info["branch"]

            # Create App
            if not frappe.db.exists("App", app_name):
                frappe.get_doc({
                    "doctype": "App", "name": app_name,
                    "title": app_name.replace("_", " ").title(), "frappe": 1
                }).insert(ignore_permissions=True)

            # Create App Source
            existing = frappe.get_all("App Source", filters={
                "app": app_name, "repository_url": repo, "branch": branch
            }, pluck="name")

            if not existing:
                src = frappe.get_doc({
                    "doctype": "App Source", "app": app_name,
                    "app_title": app_name.replace("_", " ").title(),
                    "repository_url": repo, "branch": branch,
                    "team": dashboard_team, "public": 1, "enabled": 1, "frappe": 1,
                    "versions": [{"version": version_name}],
                })
                src.insert(ignore_permissions=True)
                source_name = src.name
                print(f"  {app_name}: Source created ({source_name})")
            else:
                source_name = existing[0]
                frappe.db.set_value("App Source", source_name, {"public": 1, "frappe": 1, "enabled": 1})
                print(f"  {app_name}: Source exists ({source_name})")

            # Create App Release
            commit = _get_latest_commit(repo, branch)
            if commit:
                existing_rel = frappe.get_all("App Release", filters={
                    "source": source_name, "hash": commit
                }, pluck="name")
                if not existing_rel:
                    rel = frappe.get_doc({
                        "doctype": "App Release", "app": app_name,
                        "source": source_name, "hash": commit, "team": admin_team
                    })
                    rel.insert(ignore_permissions=True)
                    frappe.db.set_value("App Release", rel.name, "status", "Approved")
                    print(f"    Release: {commit[:10]}")

            # Create Marketplace App
            if not frappe.db.exists("Marketplace App", app_name):
                try:
                    ma = frappe.get_doc({
                        "doctype": "Marketplace App", "app": app_name,
                        "title": app_name.replace("_", " ").title(),
                        "team": admin_team, "description": app_name,
                        "category": "Other",
                        "sources": [{"source": source_name, "version": version_name}],
                    })
                    ma.insert(ignore_permissions=True)
                    frappe.db.set_value("Marketplace App", ma.name, {
                        "frappe_approved": 1, "status": "Published",
                        "image": "https://avatars.githubusercontent.com/u/10060846"
                    })
                except Exception:
                    pass  # May fail on duplicate, that's OK

    # 5. Site Plans
    print("\n--- Site Plans ---")
    for plan in config.get("site_plans", []):
        if not frappe.db.exists("Site Plan", plan["name"]):
            frappe.get_doc({
                "doctype": "Site Plan",
                "__newname": plan["name"],
                "plan_title": plan["name"],
                "price_usd": plan["price_usd"],
                "price_inr": plan.get("price_inr", plan["price_usd"] * 80),
                "cpu_time_per_day": plan["cpu_time_per_day"],
                "max_storage_usage": plan["max_storage_usage"],
                "max_database_usage": plan["max_database_usage"],
                "enabled": 1,
            }).insert(ignore_permissions=True)
            print(f"  Created: {plan['name']}")
        else:
            print(f"  Exists: {plan['name']}")

    # 6. Server records (only update team/flags if exists)
    print("\n--- Server Records ---")
    sv = config.get("server", {})
    server_name = sv.get("name", "")
    if server_name and frappe.db.exists("Server", server_name):
        frappe.db.set_value("Server", server_name, {
            "team": dashboard_team,
            "use_for_new_benches": sv.get("use_for_new_benches", 1),
            "use_for_new_sites": sv.get("use_for_new_sites", 1),
            "use_for_build": sv.get("use_for_build", 1),
        })
        print(f"  Server updated: {server_name}")

    for dt in ["Database Server", "Proxy Server"]:
        if frappe.db.exists(dt, server_name):
            frappe.db.set_value(dt, server_name, "team", dashboard_team)
            print(f"  {dt} team updated")

    # 7. Update default_apps and erpnext_apps in Press Settings
    print("\n--- Default Apps ---")
    ps.reload()
    ps.default_apps = []
    for app_name in config.get("default_apps", []):
        sources = frappe.get_all("App Source", filters={"app": app_name, "public": 1}, pluck="name")
        if sources:
            ps.append("default_apps", {"app": app_name, "app_title": app_name.replace("_", " ").title()})
            print(f"  Default: {app_name}")

    ps.erpnext_apps = []
    for app_name in config.get("erpnext_apps", []):
        ps.append("erpnext_apps", {"app": app_name})
        print(f"  ERPNext: {app_name}")

    ps.save(ignore_permissions=True)

    # 8. Create dummy Email Account
    print("\n--- Email Account ---")
    if not frappe.get_all("Email Account", filters={"default_outgoing": 1}):
        domain = config["press_settings"]["domain"]
        ea = frappe.get_doc({
            "doctype": "Email Account",
            "email_account_name": "Notifications",
            "email_id": f"noreply@{domain}",
            "domain": domain,
            "default_outgoing": 1,
            "enable_outgoing": 0,
            "smtp_server": "localhost",
            "smtp_port": 25,
        })
        ea.flags.ignore_permissions = True
        ea.flags.ignore_mandatory = True
        ea.insert(ignore_permissions=True)
        print("  Created dummy Email Account")
    else:
        print("  Email Account exists")

    frappe.db.commit()

    print("\n" + "=" * 60)
    print("Bootstrap complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Set github_app_client_secret and github_app_private_key in Press Settings")
    print("  2. Set agent_password for Server, Database Server, and Proxy Server")
    print("  3. Update agent config.json on Server 2 (press_url, access_token)")
    print("  4. Create a Release Group and trigger first build")
    print("  5. Test site creation from dashboard")


def _get_latest_commit(repo_url, branch):
    """Get latest commit hash from git ls-remote"""
    try:
        parts = repo_url.rstrip("/").split("/")
        owner, repo = parts[-2], parts[-1]
        result = subprocess.run(
            ["git", "ls-remote", f"https://github.com/{owner}/{repo}.git", branch],
            capture_output=True, text=True, timeout=15
        )
        if result.stdout:
            return result.stdout.split()[0]
    except Exception:
        pass
    return None
