import frappe

def run():
    # Get the Cloudflare API token from Root Domain
    rd = frappe.get_doc("Root Domain", "sandbox.mvpstorm.com")
    zone_id = rd.cloudflare_zone_id

    # Get the token from Press's Cloudflare integration
    from press.press.doctype.root_domain.root_domain import RootDomain
    # Try to use the domain's own method
    import requests

    # Get password field (tokens are stored as password type)
    token = frappe.utils.password.get_decrypted_password("Root Domain", "sandbox.mvpstorm.com", "cloudflare_api_token", raise_exception=False)
    if not token:
        token = frappe.utils.password.get_decrypted_password("Root Domain", "sandbox.mvpstorm.com", "cloudflare_api_key", raise_exception=False)

    if not token:
        # Check Press Settings
        token = frappe.utils.password.get_decrypted_password("Press Settings", "Press Settings", "cloudflare_api_token", raise_exception=False)

    if not token:
        print("No Cloudflare API token found!")
        # List all password fields
        for f in rd.meta.fields:
            if f.fieldtype == "Password":
                print(f"  Password field: {f.fieldname}")
        for f in frappe.get_doc("Press Settings").meta.fields:
            if f.fieldtype == "Password":
                print(f"  PS Password field: {f.fieldname}")
        return

    print(f"Token found, zone_id: {zone_id}")

    # Create DNS record
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    resp = requests.post(
        f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
        headers=headers,
        json={
            "type": "A",
            "name": "demo.sandbox.mvpstorm.com",
            "content": "89.167.116.92",
            "ttl": 1,
            "proxied": False
        }
    )
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.json()}")
