import frappe

def check():
    frappe.set_user("Administrator")

    # Check bench-0003 status
    rg = frappe.get_doc("Release Group", "bench-0003")
    print(f"Release Group: {rg.name} ({rg.title})")
    print(f"Version: {rg.version}")
    print(f"Apps:")
    for a in rg.apps:
        print(f"  {a.app}: {a.source}")

    # Check if there's a working bench
    benches = frappe.get_all("Bench",
        filters={"group": rg.name, "status": "Active"},
        fields=["name", "status", "creation"],
        order_by="creation desc", limit=3)
    print(f"\nActive benches: {len(benches)}")
    for b in benches:
        print(f"  {b.name}: {b.status}")

    # Check latest deploy candidate builds
    dcs = frappe.get_all("Deploy Candidate",
        filters={"group": rg.name},
        fields=["name", "creation"],
        order_by="creation desc", limit=3)
    print(f"\nDeploy Candidates:")
    for dc in dcs:
        builds = frappe.get_all("Deploy Candidate Build",
            filters={"deploy_candidate": dc.name},
            fields=["name", "status"],
            order_by="creation desc", limit=1)
        build_status = builds[0].status if builds else "No build"
        print(f"  {dc.name}: {build_status}")

    # Check the Press API for creating sites
    print(f"\n=== Site Creation API ===")
    print(f"Endpoint: POST /api/method/press.api.site.new")
    print(f"Required params: site name, bench/group, apps, plan")

    # Check available site plans
    plans = frappe.get_all("Site Plan",
        filters={"enabled": 1},
        fields=["name", "price_usd"])
    print(f"\nSite Plans:")
    for p in plans:
        print(f"  {p.name}: ${p.price_usd}")
