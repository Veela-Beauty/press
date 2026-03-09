# Cloudflare DNS

Press was built for AWS Route53. This fork patches it to use the Cloudflare API instead.

---

## Why This Was Patched

The upstream Press uses `boto3` (AWS SDK) for DNS management. Self-hosted deployments outside AWS need a different DNS provider. Cloudflare provides a simpler REST API and is free for most use cases.

---

## Patched Files (cloudflare-dns branch)

| File | Change |
|------|--------|
| `press/utils/dns.py` | Replaced boto3 Route53 calls with Cloudflare REST API |
| `press/press/doctype/root_domain/root_domain.py` | Replaced boto3 with Cloudflare `requests` calls |
| `press/press/doctype/root_domain/root_domain.json` | Added `cloudflare_api_token` and `cloudflare_zone_id` fields |
| `press/press/doctype/tls_certificate/tls_certificate.py` | Changed certbot from `dns-route53` plugin to `dns-cloudflare` |
| `press/press/doctype/app_release/app_release.py` | Python 3.14 path fallback → uses bench Python |
| `press/press/doctype/deploy_candidate/validations.py` | Python version check: raises exception → emits warning |
| `press/press/doctype/support_access/support_access.py` | Operator precedence bug fix |

Plus 2 additional patches applied during operations (see [troubleshooting](../02-operations/troubleshooting.md)).

---

## Cloudflare Setup

### 1. Create API Token

Go to: `https://dash.cloudflare.com/profile/api-tokens`

Create a token with:
- **Permissions:** Zone → DNS → Edit
- **Zone Resources:** Include → Specific zone → `mvpstorm.com`

### 2. Find Zone ID

```bash
curl -s -H "Authorization: Bearer YOUR_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones?name=mvpstorm.com" \
  | python3 -m json.tool | grep '"id"' | head -1
```

Or from the Cloudflare dashboard: Zone overview → right sidebar → "Zone ID".

### 3. Store Credentials

```bash
# Single source of truth — update this when rotating tokens
cat > /root/.cloudflare/credentials.ini << EOF
dns_cloudflare_api_token = YOUR_TOKEN
EOF
chmod 600 /root/.cloudflare/credentials.ini
```

When the token is rotated, update in order:
1. `/root/.cloudflare/credentials.ini`
2. Press Root Domain records (via bench execute)
3. Update docs/memory files

---

## Root Domain Configuration

In the Press admin: `Press > Root Domain > demo.mvpstorm.com`

| Field | Value |
|-------|-------|
| Name | `demo.mvpstorm.com` |
| Cloudflare API Token | `(token)` |
| Cloudflare Zone ID | `(zone ID for mvpstorm.com)` |

Set via script if the UI fields aren't visible:

```python
frappe.db.set_value("Root Domain", "demo.mvpstorm.com", {
    "cloudflare_api_token": "YOUR_TOKEN",
    "cloudflare_zone_id": "YOUR_ZONE_ID"
})
frappe.db.commit()
```

---

## How DNS Records Are Created

When a new site is created, Press calls `root_domain.create_dns_record(site_name)`, which:

1. Makes a `POST /zones/{zone_id}/dns_records` to Cloudflare
2. Creates an A record: `sitename.demo.mvpstorm.com → 89.167.57.21`
3. Sets proxied=False (direct connection to server)

### Manual DNS Record Creation

```python
import requests

token = frappe.get_decrypted_password("Root Domain", "demo.mvpstorm.com", "cloudflare_api_token")
zone_id = frappe.db.get_value("Root Domain", "demo.mvpstorm.com", "cloudflare_zone_id")

response = requests.post(
    f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={
        "type": "A",
        "name": "mysite.demo.mvpstorm.com",
        "content": "89.167.57.21",
        "proxied": False,
        "ttl": 1
    }
)
print(response.json())
```

---

## TLS Certificate Issuance

Press issues TLS certs for sites via certbot on the proxy server. The Cloudflare patch changes the certbot command from:

```bash
# Original (Route53)
certbot certonly --dns-route53 -d "*.demo.mvpstorm.com"

# Patched (Cloudflare)
certbot certonly --dns-cloudflare \
  --dns-cloudflare-credentials /root/.cloudflare/credentials.ini \
  -d "*.demo.mvpstorm.com"
```

The `tls_certificate.py` patch also handles writing the credentials file to the proxy server via SSH before running certbot.

---

## Troubleshooting

**Zone ID mismatch — DNS records not created**
```bash
# Verify zone ID
curl -s -H "Authorization: Bearer TOKEN" \
  "https://api.cloudflare.com/client/v4/zones?name=mvpstorm.com" | grep '"id"'
```

**Token verify endpoint for account-scoped tokens**
```bash
# For account-scoped tokens, use account endpoint instead of user endpoint
curl -H "Authorization: Bearer TOKEN" \
  "https://api.cloudflare.com/client/v4/accounts/ACCOUNT_ID/tokens/verify"
```

**certbot dns-cloudflare and --nginx can't be used together**
→ Use `certonly` mode only. Configure nginx SSL manually.
