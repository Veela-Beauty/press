"""
Self-Hosted Press Utilities
============================
Safe wrappers for common Press operations that prevent
duplicate builds, stuck jobs, and other self-hosted gotchas.

Usage:
    bench --site SITE execute press.press.selfhosted_utils.build_bench --kwargs '{"release_group": "bench-0005"}'
    bench --site SITE execute press.press.selfhosted_utils.create_demo_site --kwargs '{"subdomain": "acme", "group": "bench-0005"}'
"""

import frappe


def build_bench(release_group: str, force: bool = False):
    """
    Safe build + deploy for a Release Group.
    - Checks for existing active/running builds first
    - Cancels stuck builds
    - Uses build_and_deploy (auto-deploys after build)
    """
    frappe.set_user("Administrator")

    rg = frappe.get_doc("Release Group", release_group)
    print(f"Release Group: {rg.name} ({rg.title})")

    # 1. Check for stuck builds and cancel them
    stuck = frappe.get_all(
        "Deploy Candidate Build",
        filters={
            "deploy_candidate": ["like", f"deploy-{release_group.split('-')[1]}%"],
            "status": ["in", ["Preparing", "Running"]],
        },
        fields=["name", "status", "creation"],
    )
    if stuck:
        for b in stuck:
            age_seconds = (frappe.utils.now_datetime() - b.creation).total_seconds()
            if age_seconds > 600 or force:  # Stuck for >10 min
                frappe.db.set_value("Deploy Candidate Build", b.name, "status", "Failure")
                print(f"  Cancelled stuck build: {b.name} (age: {int(age_seconds)}s)")
            else:
                print(f"  Build {b.name} still running ({int(age_seconds)}s old)")
                if not force:
                    print("  Use force=True to cancel. Aborting.")
                    return

    frappe.db.commit()

    # 2. Check if bench already active (no build needed)
    active_benches = frappe.get_all(
        "Bench",
        filters={"group": release_group, "status": "Active"},
        pluck="name",
    )

    # 3. Create deploy candidate
    dc = rg.create_deploy_candidate()
    frappe.db.commit()
    print(f"Deploy Candidate: {dc.name}")

    # 4. Use build_and_deploy (builds Docker image, then auto-creates bench)
    build_name = dc.build_and_deploy()
    frappe.db.commit()
    print(f"Build + Deploy triggered: {build_name}")
    print(f"\nMonitor: bench --site {frappe.local.site} execute press.press.selfhosted_utils.check_build --kwargs '{{\"build\": \"{build_name}\"}}'")

    return build_name


def check_build(build: str):
    """Check the status of a build and its bench."""
    frappe.set_user("Administrator")

    b = frappe.get_doc("Deploy Candidate Build", build)
    print(f"Build: {b.name} | Status: {b.status}")

    for step in b.build_steps:
        s = step.as_dict()
        status = s.get("status", "?")
        output = s.get("output", "")
        line = f"  {s.get('step', '?')}: {s.get('stage_slug', '?')} -> {status}"
        if output and status == "Failure":
            line += f"\n    {str(output)[:300]}"
        print(line)

    # Check bench
    dc = frappe.get_doc("Deploy Candidate", b.deploy_candidate)
    benches = frappe.get_all(
        "Bench",
        filters={"group": dc.group, "status": "Active"},
        fields=["name", "status"],
    )
    if benches:
        print(f"\nActive bench: {benches[0].name}")
    else:
        print("\nNo active bench yet")


def create_demo_site(subdomain: str, group: str = "bench-0005", plan: str = "Free"):
    """
    Create a demo site on the AccuBuild bench.
    Returns site name when creation starts.
    """
    frappe.set_user("Administrator")

    domain = frappe.db.get_single_value("Press Settings", "domain")
    site_name = f"{subdomain}.{domain}"

    # Check if site already exists
    if frappe.db.exists("Site", site_name):
        existing_status = frappe.db.get_value("Site", site_name, "status")
        print(f"Site {site_name} already exists (status: {existing_status})")
        return site_name

    # Find active bench for this group
    bench = frappe.get_all(
        "Bench",
        filters={"group": group, "status": "Active"},
        fields=["name", "server"],
        order_by="creation desc",
        limit=1,
    )
    if not bench:
        print(f"No active bench for {group}. Run build_bench first.")
        return None

    bench = bench[0]

    # Get team
    teams = frappe.get_all("Team", filters={"user": ["!=", "Administrator"]}, pluck="name")
    team = teams[0] if teams else frappe.get_all("Team", pluck="name")[0]

    # Get apps from the release group
    rg = frappe.get_doc("Release Group", group)
    apps = [{"app": a.app} for a in rg.apps]

    # Create site
    site = frappe.get_doc({
        "doctype": "Site",
        "subdomain": subdomain,
        "domain": domain,
        "group": group,
        "server": bench.server,
        "bench": bench.name,
        "team": team,
        "free": 1,
        "subscription_plan": plan,
        "apps": apps,
    })
    site.insert(ignore_permissions=True)
    frappe.db.commit()

    print(f"Site created: {site.name}")
    print(f"  Bench: {bench.name}")
    print(f"  Apps: {[a.app for a in rg.apps]}")
    print(f"  URL: https://{site.name}")

    return site.name


def poll_and_check():
    """Run poll_pending_jobs and show status of all pending work."""
    frappe.set_user("Administrator")

    from press.press.doctype.agent_job.agent_job import poll_pending_jobs
    poll_pending_jobs()
    frappe.db.commit()

    # Show pending jobs
    jobs = frappe.get_all(
        "Agent Job",
        filters={"status": ["in", ["Pending", "Running", "Undelivered"]]},
        fields=["name", "job_type", "status", "server"],
        order_by="creation desc",
        limit=10,
    )
    if jobs:
        print("Pending jobs:")
        for j in jobs:
            print(f"  {j.name}: {j.job_type} -> {j.status}")
    else:
        print("No pending jobs")

    # Show recent completed
    recent = frappe.get_all(
        "Agent Job",
        filters={"status": ["in", ["Success", "Failure"]]},
        fields=["name", "job_type", "status"],
        order_by="creation desc",
        limit=5,
    )
    print("\nRecent jobs:")
    for j in recent:
        print(f"  {j.name}: {j.job_type} -> {j.status}")
