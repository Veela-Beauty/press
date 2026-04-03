import frappe
import subprocess

def fix():
    frappe.set_user("Administrator")
    team = frappe.get_all("Team", filters={"user": "Administrator"}, pluck="name")[0]

    # 1. Check what App Releases exist for the v16 sources and if hashes match
    print("=== Checking v16 App Releases ===")
    dc = frappe.get_doc("Deploy Candidate", "deploy-0004-000002")
    for app in dc.apps:
        source = frappe.get_doc("App Source", app.source)
        release = frappe.get_doc("App Release", app.release) if app.release else None

        # Get actual latest commit from version-16 branch
        result = subprocess.run(
            ["git", "ls-remote", source.repository_url, source.branch],
            capture_output=True, text=True, timeout=15
        )
        latest_commit = result.stdout.split()[0] if result.stdout else "N/A"

        release_hash = release.hash if release else "NO RELEASE"
        match = "MATCH" if release and release.hash == latest_commit else "MISMATCH"

        print(f"  {app.app}:")
        print(f"    Source: {app.source} branch={source.branch}")
        print(f"    Release hash: {release_hash[:12] if release else 'NONE'}")
        print(f"    Latest commit: {latest_commit[:12]}")
        print(f"    Status: {match}")

        # If mismatch, create correct release
        if match == "MISMATCH" and latest_commit != "N/A":
            existing = frappe.get_all("App Release",
                filters={"source": app.source, "hash": latest_commit}, pluck="name")
            if not existing:
                rel = frappe.get_doc({
                    "doctype": "App Release", "app": app.app,
                    "source": app.source, "hash": latest_commit, "team": team
                })
                rel.insert(ignore_permissions=True)
                frappe.db.set_value("App Release", rel.name, "status", "Approved")
                print(f"    Created release: {latest_commit[:12]}")
            else:
                print(f"    Release already exists: {existing[0]}")

    frappe.db.commit()

    # 2. Mark stuck/failed builds as Failure
    stuck = frappe.get_all("Deploy Candidate Build",
        filters={"deploy_candidate": ["like", "deploy-0004%"], "status": ["in", ["Preparing", "Running"]]},
        pluck="name")
    for b in stuck:
        frappe.db.set_value("Deploy Candidate Build", b, "status", "Failure")
        print(f"\nMarked {b} as Failure")

    frappe.db.commit()

    # 3. Create fresh deploy candidate and build
    rg = frappe.get_doc("Release Group", "bench-0004")
    dc_new = rg.create_deploy_candidate()
    frappe.db.commit()
    print(f"\nNew DC: {dc_new.name}")

    # Print what's in it
    for app in dc_new.apps:
        print(f"  {app.app}: source={app.source} release={app.release}")
        if app.release:
            h = frappe.db.get_value("App Release", app.release, "hash")
            print(f"    hash: {h[:12] if h else 'NONE'}")

    dc_new.build()
    frappe.db.commit()
    print("\nBuild triggered!")
