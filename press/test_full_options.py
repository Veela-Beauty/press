import frappe

def test():
    frappe.set_user("test@mvpstorm.com")
    from press.api.bench import options
    result = options()

    versions = result.get("versions", [])
    clusters = result.get("clusters", [])

    print(f"Versions: {len(versions)}")
    for v in versions:
        apps = v.get("apps", [])
        print(f"  {v['name']}: {v.get('status')} default={v.get('default')} - {len(apps)} apps")
        for a in apps:
            print(f"    {a['name']}: {a.get('title')}")

    print(f"\nClusters: {len(clusters)}")
    for c in clusters:
        print(f"  {c}")

    # Check if frappe_approved marketplace apps exist
    approved = frappe.get_all("Marketplace App", filters={"frappe_approved": 1}, pluck="app")
    print(f"\nFrappe Approved Marketplace Apps: {approved}")

    all_mp = frappe.get_all("Marketplace App", fields=["name", "app", "frappe_approved", "status"])
    print(f"\nAll Marketplace Apps:")
    for m in all_mp:
        print(f"  {m.name}: app={m.app} approved={m.frappe_approved} status={m.status}")
