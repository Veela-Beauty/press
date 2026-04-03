import frappe

def reconfig():
    frappe.set_user("Administrator")
    dashboard_team = "sqkn1globp"
    new_domain = "sandbox.mvpstorm.com"
    old_server = "press-f1.demo.mvpstorm.com"
    new_server = "press-f1.sandbox.mvpstorm.com"

    # 1. Create new Root Domain for sandbox
    print("=== Root Domain ===")
    if not frappe.db.exists("Root Domain", new_domain):
        # Get cloudflare creds from old domain
        old_rd = frappe.get_doc("Root Domain", "demo.mvpstorm.com")
        old_token = old_rd.get_password("cloudflare_api_token")

        rd = frappe.get_doc({
            "doctype": "Root Domain",
            "name": new_domain,
            "dns_provider": "Cloudflare",
            "cloudflare_zone_id": "41e5c9954e80ce5a0bcfa5cf502b77af",
            "default_cluster": "Default",
        })
        rd.insert(ignore_permissions=True)
        # Set password separately
        frappe.utils.password.set_encrypted_password("Root Domain", new_domain, old_token, "cloudflare_api_token")
        print(f"  Created: {new_domain}")
    else:
        print(f"  Exists: {new_domain}")

    # 2. Update Press Settings
    print("\n=== Press Settings ===")
    ps = frappe.get_doc("Press Settings")
    ps.domain = new_domain
    ps.save(ignore_permissions=True)
    print(f"  domain: {ps.domain}")

    # 3. Rename Server records
    print("\n=== Server Records ===")
    for dt in ["Server", "Database Server", "Proxy Server"]:
        if frappe.db.exists(dt, old_server):
            try:
                frappe.rename_doc(dt, old_server, new_server, force=True)
                print(f"  Renamed {dt}: {old_server} -> {new_server}")
            except Exception as e:
                print(f"  FAILED to rename {dt}: {e}")
                # Try direct DB update as fallback
                try:
                    frappe.db.sql(f"UPDATE `tab{dt}` SET name = %s WHERE name = %s", (new_server, old_server))
                    print(f"  Renamed via DB: {dt}")
                except Exception as e2:
                    print(f"  DB rename also failed: {e2}")
        elif frappe.db.exists(dt, new_server):
            print(f"  Already renamed: {dt} -> {new_server}")
        else:
            print(f"  NOT FOUND: {dt} {old_server}")

    # 4. Update server references in other records
    print("\n=== Updating references ===")

    # Update Server's proxy_server and database_server links
    if frappe.db.exists("Server", new_server):
        frappe.db.set_value("Server", new_server, {
            "proxy_server": new_server,
            "database_server": new_server,
        })
        print(f"  Server links updated")

    # Update Press Settings build_server
    frappe.db.set_single_value("Press Settings", "build_server", new_server)
    print(f"  build_server: {new_server}")

    # 5. Ensure cluster is public
    print("\n=== Cluster ===")
    frappe.db.set_value("Cluster", "Default", "public", 1)
    print(f"  Default cluster: public=1")

    frappe.db.commit()
    print("\nPhase 5 done!")
