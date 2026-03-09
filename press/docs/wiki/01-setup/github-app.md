# GitHub App Integration

Configure the GitHub App so dashboard users can connect their GitHub accounts and deploy private repositories.

---

## 1. Create the GitHub App

Go to: `https://github.com/settings/apps/new` (or your org's settings)

### Required Settings

| Setting | Value |
|---------|-------|
| GitHub App name | `mvpstorm-press` (becomes the public slug) |
| Homepage URL | `https://demo.mvpstorm.com` |
| Callback URL | `https://demo.mvpstorm.com/github/authorize` |
| Setup URL (optional) | `https://demo.mvpstorm.com/github/authorize` |
| Request user authorization during install | **Enabled** (critical) |
| Webhook URL | `https://demo.mvpstorm.com/api/method/press.api.github.hook` |
| Webhook Secret | (any random secret) |

### Permissions

| Permission | Level |
|------------|-------|
| Contents | Read-only |
| Metadata | Read-only |

### Post-Creation

After creating the app:
1. Note the **App ID** (numeric, shown on the General page)
2. Note the **Client ID** (starts with `Iv1.`)
3. Generate a **Client Secret** and copy it immediately
4. Generate a **Private Key** — downloads as a `.pem` file

---

## 2. Configure Press Settings

```python
ps = frappe.get_doc("Press Settings")
ps.github_app_id = "12345678"
ps.github_app_client_id = "Iv1.xxxxxxxxxxxxxxxxx"
ps.github_app_client_secret = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
ps.github_app_private_key = open("/path/to/mvpstorm-press.private-key.pem").read()
ps.github_app_public_link = "https://github.com/apps/mvpstorm-press"
ps.save(ignore_permissions=True)
frappe.db.commit()
```

**`github_app_public_link`** is the URL shown to users for the "Connect to GitHub" button. It must exactly match the app's slug in the GitHub URL — use the slug from `github.com/apps/<slug>`, not the display name.

---

## 3. Enable OAuth During Installation

In GitHub App settings under "Identifying and authorizing users":
- Enable **"Request user authorization (OAuth) during installation"**

Without this, users who install the app are NOT automatically authorized. Press won't have their OAuth token and will show "Connect to GitHub" even after installation.

---

## 4. OAuth Flow (How It Works)

```
User clicks "Add App" in dashboard
    → GitHub App installation page
    → User installs app on their repos
    → GitHub redirects to callback URL
    → Press receives code, exchanges for token
    → Token saved on Team record
    → User can now deploy private repos
```

If "Request user authorization during installation" is enabled, steps 2-4 happen automatically. If not enabled, the user must separately go through OAuth.

---

## 5. Manual OAuth Fix

If a user installed the app but authorization didn't complete (token missing):

```python
# Find the state token
team = frappe.get_doc("Team", "<team_hash>")
import base64, json

state = base64.b64encode(json.dumps({
    "team": team.name,
    "next": "/dashboard/settings/github"
}).encode()).decode()

print(f"https://github.com/login/oauth/authorize?client_id={ps.github_app_client_id}&state={state}")
```

User navigates to the printed URL and completes OAuth.

---

## 6. Verification

After setup:

1. Dashboard → Settings → GitHub → Should show "Connected" with repos listed
2. Dashboard → New Bench → Can add apps from GitHub

```python
# Check if OAuth token saved for team
team = frappe.get_doc("Team", "<team_hash>")
print(team.github_access_token)  # Should be non-empty
```

---

## Troubleshooting

**"Connect to GitHub" shown after installation**
→ OAuth authorization was not captured. Run manual OAuth fix above.

**Webhook not receiving events**
→ Check GitHub App webhook delivery log. Ensure `frappe-web` process is running.

**Private repo not appearing in app list**
→ GitHub App must be installed on the repo/org. Check Installation page: `github.com/apps/mvpstorm-press/installations/new`.
