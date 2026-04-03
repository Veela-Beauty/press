import frappe

def run():
    rd = frappe.get_doc("Root Domain", "sandbox.mvpstorm.com")
    token = rd.get_password("cloudflare_api_token")
    zone_id = rd.cloudflare_zone_id
    print(f"Zone ID: {zone_id}")
    print(f"Token (first 10): {token[:10]}...")

    # Test token validity first
    import requests
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Verify token
    r = requests.get("https://api.cloudflare.com/client/v4/user/tokens/verify", headers=headers)
    print(f"Token verify: {r.status_code} - {r.json()}")

    if r.status_code == 200 and r.json().get("success"):
        # Create the DNS record
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
        print(f"DNS create: {resp.status_code}")
        print(f"Response: {resp.json()}")
