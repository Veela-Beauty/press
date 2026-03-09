# Press Settings

All fields in the Press Settings DocType and their correct values for self-hosted deployment.

Navigate to: Admin desk → Press → Press Settings (or `/app/press-settings`)

---

## Core Settings

| Field | Value | Notes |
|-------|-------|-------|
| `domain` | `demo.mvpstorm.com` | Root domain for the Press controller site |
| `cluster` | `Default` | Default cluster used when creating sites |
| `docker_registry_url` | `89.167.116.92:5000` | Self-hosted Docker registry (HTTP, port 5000) |
| `build_server` | `press-f1.demo.mvpstorm.com` | Server that runs Docker builds |
| `clone_directory` | `/home/frappe/frappe-bench/clones` | Where app repos are cloned on the build server |
| `build_directory` | `/home/frappe/frappe-bench/builds` | Where Docker build contexts are assembled |

**Note:** Both `clone_directory` and `build_directory` must be set AND the directories must exist on disk. If either is NULL, builds fail with a cryptic `TypeError: stat: path should be string`.

```bash
# Create on Server 2
mkdir -p /home/frappe/frappe-bench/clones /home/frappe/frappe-bench/builds
chown frappe:frappe /home/frappe/frappe-bench/clones /home/frappe/frappe-bench/builds
```

---

## App Settings

| Field | Value | Notes |
|-------|-------|-------|
| `default_apps` | `frappe`, `erpnext` | Auto-added to every new bench |
| `erpnext_apps` | `erpnext`, `hrms`, `payments`, `webshop`, `lending` | Apps listed in the dashboard marketplace |

---

## GitHub App Settings

| Field | Value | Notes |
|-------|-------|-------|
| `github_app_id` | `(numeric ID)` | From GitHub App "General" page |
| `github_app_client_id` | `Iv1.xxxxx` | OAuth client ID |
| `github_app_client_secret` | `(secret)` | OAuth client secret |
| `github_app_private_key` | `-----BEGIN RSA PRIVATE KEY-----...` | Downloaded .pem file contents |
| `github_app_public_link` | `https://github.com/apps/mvpstorm-press` | Used for "Install App" button — must match exact slug |

The `github_app_public_link` is the public installation URL shown to dashboard users. Must use the correct slug (e.g., `mvpstorm-press`, not the display name).

---

## Email Settings

| Field | Value | Notes |
|-------|-------|-------|
| `disable_mail_notifications` | (set in site_config.json) | Prevents OutgoingEmailError on builds if no email account configured |

Set in `site_config.json` if no email is configured:
```json
{"disable_mail_notifications": 1}
```

Or create a dummy Email Account with `default_outgoing = 1` in Frappe.

---

## Setting via Script

When settings cannot be saved via UI (some fields are read-only or auto-overwritten):

```python
ps = frappe.get_doc("Press Settings")
ps.domain = "demo.mvpstorm.com"
ps.cluster = "Default"
ps.docker_registry_url = "89.167.116.92:5000"
ps.build_server = "press-f1.demo.mvpstorm.com"
ps.clone_directory = "/home/frappe/frappe-bench/clones"
ps.build_directory = "/home/frappe/frappe-bench/builds"
ps.default_apps = "frappe\nerpnext"
ps.erpnext_apps = "erpnext\nhrms\npayments\nwebshop\nlending"
ps.github_app_id = "12345678"
ps.github_app_client_id = "Iv1.xxxx"
ps.github_app_client_secret = "xxxx"
ps.github_app_private_key = "-----BEGIN RSA PRIVATE KEY-----\n..."
ps.github_app_public_link = "https://github.com/apps/mvpstorm-press"
ps.save(ignore_permissions=True)
frappe.db.commit()
```

---

## Verification

After setting all values:

```bash
# Verify build server is recognized
bench --site demo.mvpstorm.com execute frappe.client.get \
  --kwargs '{"doctype": "Press Settings"}'
```

Check that `build_server` matches a Server record with `use_for_build = 1`.
