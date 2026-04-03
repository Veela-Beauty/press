import frappe

def run():
    token = "ajC8qXYh-U1FivxBj2kHYKwVJvdfiMgsiIdGvFtC"
    zone_id = "41e5c9954e80ce5a0bcfa5cf502b77af"

    for domain in ["sandbox.mvpstorm.com", "demo.mvpstorm.com"]:
        rd = frappe.get_doc("Root Domain", domain)
        rd.cloudflare_zone_id = zone_id
        rd.cloudflare_api_token = token
        rd.save(ignore_permissions=True)
        print(f"Updated {domain}: zone_id={zone_id}")

    frappe.db.commit()
    print("Done - both Root Domains updated")
