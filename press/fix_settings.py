import frappe

def fix():
    frappe.set_user("Administrator")
    ps = frappe.get_doc("Press Settings")

    # 1. Set default_apps - these auto-add when creating new bench
    ps.default_apps = []
    for app_name in ["frappe", "erpnext"]:
        source = frappe.get_all("App Source", filters={"app": app_name}, pluck="name")
        if source:
            ps.append("default_apps", {"app": app_name, "source": source[0]})
            print(f"Default app: {app_name} -> {source[0]}")

    # 2. Set erpnext_apps - apps shown in marketplace/bench creation
    ps.erpnext_apps = []
    for app_name in ["erpnext", "hrms", "payments", "webshop", "lending"]:
        source = frappe.get_all("App Source", filters={"app": app_name}, pluck="name")
        if source:
            ps.append("erpnext_apps", {"app": app_name, "source": source[0]})
            print(f"ERPNext app: {app_name} -> {source[0]}")

    # 3. Disable offsite backups (no S3 configured)
    ps.offsite_backups_count = 0
    ps.disable_physical_backup = 1
    print("Offsite backups: disabled (no S3)")

    # 4. Disable features that need external services
    ps.send_telegram_notifications = 0
    ps.send_email_notifications = 0
    print("Notifications: disabled")

    # 5. Free credits for trial
    ps.free_credits_usd = 100
    print("Free credits: $100 USD")

    ps.save(ignore_permissions=True)
    frappe.db.commit()
    print("\nPress Settings updated!")

    # Summary of what still needs manual setup for GitHub integration
    print("\n=== GITHUB APP INTEGRATION (optional) ===")
    print("To enable 'Add app from GitHub' in dashboard:")
    print("1. Go to https://github.com/settings/apps/new")
    print("2. Create a GitHub App with:")
    print("   - Name: MVPStorm Press (or any unique name)")
    print("   - Homepage: https://demo.mvpstorm.com")
    print("   - Callback URL: https://demo.mvpstorm.com/api/method/press.api.github.callback")
    print("   - Setup URL: https://demo.mvpstorm.com/github/installations/new")
    print("   - Permissions: Contents (Read), Metadata (Read)")
    print("3. After creation, note the App ID and generate a Client Secret")
    print("4. Set in Press Settings: github_app_id, github_app_secret")
    print("\nWithout this, apps must be added via backend scripts.")
