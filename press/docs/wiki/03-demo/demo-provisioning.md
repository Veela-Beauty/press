# Demo Site Provisioning

Self-service demo site creation for prospects, protected by invite codes.

## Architecture

```
Customer browser                    Server 1 (press-ctrl)           Server 2 (press-f1)
    |                                   |                               |
    |  https://demo.sandbox.mvpstorm.com|                               |
    |  (static HTML page)              |                               |
    |                                   |                               |
    |-- POST /api/method/             --|                               |
    |   press.api.demo.create           |                               |
    |   (CORS to autodeploypanel)       |                               |
    |                                   |-- Creates Site doc            |
    |                                   |-- Press agent deploys ------->|
    |                                   |                               |-- Docker container
    |  <-- poll check_status ---------- |                               |-- Site active
    |                                   |                               |
    |  https://COMPANY.sandbox...  -----|------------------------------>|
```

## Components

### Landing Page
- **URL**: `https://demo.sandbox.mvpstorm.com`
- **Location**: `/var/www/demo-landing/index.html` on Server 1
- **Nginx**: `/etc/nginx/conf.d/demo-sandbox.conf`
- **SSL**: Let's Encrypt cert at `/etc/letsencrypt/live/demo.sandbox.mvpstorm.com/`
- **DNS**: `demo.sandbox.mvpstorm.com` → A → 89.167.116.92 (overrides wildcard)
- Standalone HTML — no Frappe dependency, calls Press API via CORS

### API (`press/api/demo.py`)
- `create(company, email, phone, invite_code)` — validates invite code, creates Site
- `check_status(site)` — polls Site status, returns `ready: true` when Active
- Runs site creation as Administrator to bypass Press role guards
- CORS enabled via `allow_cors` in `site_config.json`

### DocTypes

#### Demo Invite Code
Managed at `/app/demo-invite-code`. Fields:
| Field | Type | Purpose |
|-------|------|---------|
| code | Data (unique, PK) | The invite code string |
| enabled | Check | Toggle on/off |
| expires_on | Date | Code expires after this |
| email | Data | If set, only this email can use it |
| max_uses | Int | Max uses (0 = unlimited) |
| used_count | Int (read-only) | Auto-incremented on use |
| notes | Small Text | Internal notes |
| sites_html | HTML | Shows linked Demo Site Requests |

#### Demo Site Request
Audit log at `/app/demo-site-request`. Fields:
| Field | Type | Purpose |
|-------|------|---------|
| company | Data | Company name from form |
| email | Data | Email from form |
| phone | Data | Phone from form |
| site | Link → Site | The created site (clickable) |
| invite_code | Link → Demo Invite Code | Which code was used (clickable) |

### Validation Flow (in order)
1. Invite code exists in `Demo Invite Code`
2. Code is enabled
3. Code hasn't expired (`expires_on`)
4. Code hasn't exceeded `max_uses`
5. Email matches (if code has `email` set)
6. Standard input validation (company, email format)
7. Rate limiting (2 per email per day, 50 total sites max)

## Managing Invite Codes

### Create a new code
Go to `/app/demo-invite-code/new` or:
```python
frappe.get_doc({
    "doctype": "Demo Invite Code",
    "code": "PARTNER-XYZ",
    "enabled": 1,
    "expires_on": "2026-06-01",
    "max_uses": 5,
    "email": "partner@example.com",
    "notes": "For XYZ partner demo",
}).insert()
```

### Disable a code
Set `enabled = 0` on the form, or:
```python
frappe.db.set_value("Demo Invite Code", "CODE-NAME", "enabled", 0)
```

### View usage
Open any invite code → scroll to "Sites Created" section to see all sites created with that code.

## Configuration

In `site_config.json` on the Press site:
```json
{
    "allow_cors": "https://demo.sandbox.mvpstorm.com"
}
```

In `press/api/demo.py`:
```python
DEMO_RELEASE_GROUP = "bench-0005"   # Which bench to deploy on
DEMO_PLAN = "Free"                   # Site plan
DEMO_ADMIN_PASSWORD = "demo1234"     # Default admin password
MAX_DEMOS_PER_EMAIL_PER_DAY = 2     # Rate limit
MAX_TOTAL_DEMO_SITES = 50           # Capacity limit
```
