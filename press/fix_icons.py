import frappe

def fix():
    frappe.set_user("Administrator")

    # Set cluster image - use a flag emoji or hosted icon
    # Press dashboard expects image URLs. Let's use country flag SVGs from a public CDN.
    cluster = frappe.get_doc("Cluster", "Default")
    # Use a generic server/globe icon from frappe's built-in assets
    cluster.image = "/assets/press/flags/de.svg"
    cluster.title = "Europe (Germany)"
    try:
        cluster.save(ignore_permissions=True)
        print(f"Cluster updated: title={cluster.title} image={cluster.image}")
    except Exception as e:
        print(f"Cluster save error: {e}")
        # Try direct DB update
        frappe.db.set_value("Cluster", "Default", {
            "image": "/assets/press/flags/de.svg",
            "title": "Europe (Germany)",
        })
        print("Cluster updated via DB")

    # Check if flag files exist
    import os
    flags_dir = "/home/frappe/frappe-bench/apps/press/press/public/flags"
    if os.path.exists(flags_dir):
        flags = os.listdir(flags_dir)
        print(f"\nFlag files available: {len(flags)}")
        print(f"  Examples: {flags[:10]}")
    else:
        print(f"\nFlags directory not found: {flags_dir}")
        # Check what's in press public
        public_dir = "/home/frappe/frappe-bench/apps/press/press/public"
        if os.path.exists(public_dir):
            items = os.listdir(public_dir)
            print(f"Press public dir contents: {items}")

    # Set Marketplace App images to their GitHub avatar URLs
    apps_images = {
        "frappe": "https://avatars.githubusercontent.com/u/10060846",
        "erpnext": "https://avatars.githubusercontent.com/u/10060846",
        "hrms": "https://avatars.githubusercontent.com/u/10060846",
        "payments": "https://avatars.githubusercontent.com/u/10060846",
        "webshop": "https://avatars.githubusercontent.com/u/10060846",
        "lending": "https://avatars.githubusercontent.com/u/10060846",
        "crm": "https://avatars.githubusercontent.com/u/10060846",
        "helpdesk": "https://avatars.githubusercontent.com/u/10060846",
        "builder": "https://avatars.githubusercontent.com/u/10060846",
        "insights": "https://avatars.githubusercontent.com/u/10060846",
        "print_designer": "https://avatars.githubusercontent.com/u/10060846",
        "wiki": "https://avatars.githubusercontent.com/u/10060846",
        "lms": "https://avatars.githubusercontent.com/u/10060846",
        "drive": "https://avatars.githubusercontent.com/u/10060846",
        "gameplan": "https://avatars.githubusercontent.com/u/10060846",
    }
    for app_name, image_url in apps_images.items():
        if frappe.db.exists("Marketplace App", app_name):
            frappe.db.set_value("Marketplace App", app_name, "image", image_url)
    print(f"\nMarketplace App images set (Frappe logo)")

    frappe.db.commit()

    # Make cluster public again (it resets!)
    frappe.db.set_value("Cluster", "Default", "public", 1)
    frappe.db.commit()
    print("Cluster public: 1 (re-set)")
