import frappe

def fix():
    frappe.set_user("Administrator")

    # 1. Disable email notifications to prevent crashes
    ps = frappe.get_doc("Press Settings")
    ps.send_email_notifications = 0
    ps.save(ignore_permissions=True)
    print("Email notifications disabled")

    # 2. The v16 issue: ERPNext develop now requires frappe >= 17.0.0-dev
    # This means develop branch is actually v17 now, not v16
    # For v16, we need version-16 tagged branches (if they exist)
    # Let's check what branches are available

    import subprocess
    apps_to_check = ["frappe", "erpnext", "hrms", "payments"]
    print("\n=== Checking version-16 branches ===")
    for app in apps_to_check:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", f"https://github.com/frappe/{app}.git", "version-16"],
            capture_output=True, text=True, timeout=15
        )
        has_v16 = bool(result.stdout.strip())
        print(f"  {app}: version-16 -> {'YES' if has_v16 else 'NO'}")

        # Also check version-16-beta
        result2 = subprocess.run(
            ["git", "ls-remote", "--heads", f"https://github.com/frappe/{app}.git", "version-16-beta"],
            capture_output=True, text=True, timeout=15
        )
        has_v16_beta = bool(result2.stdout.strip())
        if has_v16_beta:
            print(f"  {app}: version-16-beta -> YES")

    frappe.db.commit()
    print("\nNote: If no version-16 branches exist, v16 is still in 'develop' which is now v17.")
    print("Consider renaming 'Version 16' to 'Nightly/Develop' or removing it.")
