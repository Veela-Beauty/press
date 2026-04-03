import frappe
import requests

def setup():
    frappe.set_user("Administrator")

    # Get Cloudflare credentials from existing Root Domain
    rd = frappe.get_doc("Root Domain", "demo.mvpstorm.com")
    zone_id = rd.cloudflare_zone_id
    token = rd.get_password("cloudflare_api_token")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    base_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"

    records = [
        # Control panel -> Server 1
        {"type": "A", "name": "autodeploypanel.mvpstorm.com", "content": "89.167.116.92", "ttl": 600, "proxied": False},
        # Sandbox root -> Server 2
        {"type": "A", "name": "sandbox.mvpstorm.com", "content": "89.167.57.21", "ttl": 600, "proxied": False},
        # Wildcard for customer sites -> Server 2
        {"type": "CNAME", "name": "*.sandbox.mvpstorm.com", "content": "sandbox.mvpstorm.com", "ttl": 600, "proxied": False},
    ]

    for record in records:
        # Check if exists
        params = {"type": record["type"], "name": record["name"]}
        resp = requests.get(base_url, headers=headers, params=params)
        existing = resp.json().get("result", [])

        if existing:
            rec_id = existing[0]["id"]
            resp = requests.put(f"{base_url}/{rec_id}", headers=headers, json=record)
            if resp.ok:
                print(f"Updated: {record['name']} -> {record['content']}")
            else:
                print(f"FAILED to update {record['name']}: {resp.status_code} {resp.json().get('errors', resp.text[:200])}")
        else:
            resp = requests.post(base_url, headers=headers, json=record)
            if resp.ok:
                print(f"Created: {record['name']} -> {record['content']}")
            else:
                print(f"FAILED to create {record['name']}: {resp.status_code} {resp.json().get('errors', resp.text[:200])}")

    print("\nDNS records done!")
