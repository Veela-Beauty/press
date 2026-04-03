import frappe

def check():
    frappe.set_user("Administrator")

    # Check Cluster image
    clusters = frappe.get_all("Cluster", fields=["name", "title", "image"])
    print("=== Clusters ===")
    for c in clusters:
        print(f"  {c.name}: image={c.image}")

    # Check Cloud Region images
    regions = frappe.get_all("Cloud Region", fields=["name", "title", "image"])
    print(f"\n=== Cloud Regions: {len(regions)} ===")
    for r in regions:
        print(f"  {r.name}: {r.title} image={r.image}")

    # Check Marketplace App images
    apps = frappe.get_all("Marketplace App", fields=["name", "image"])
    print(f"\n=== Marketplace App images ===")
    for a in apps:
        print(f"  {a.name}: image={a.image}")

    # Check if there's a Frappe Version image field
    versions = frappe.get_all("Frappe Version", fields=["name", "status"])
    print(f"\n=== Frappe Versions ===")
    for v in versions:
        print(f"  {v.name}: {v.status}")

    # Check site_config for assets/webserver URL
    print(f"\n=== Site URL ===")
    print(f"  frappe.utils.get_url(): {frappe.utils.get_url()}")
