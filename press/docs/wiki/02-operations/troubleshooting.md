# Troubleshooting

## Common Errors & Fixes

### "You are not allowed to use this plan"
**Cause:** Server.team is NULL
**Fix:** Set team on Server, Database Server, and Proxy Server records to match the dashboard user's team hash.

### Agent 401 Unauthenticated
**Cause:** agent_password mismatch between Press and agent config
**Fix:**
1. Check which server_type failed (Server vs Proxy Server)
2. Each has a SEPARATE agent_password in `__Auth` table
3. All must match the single `access_token` in agent's config.json
4. Agent stores pbkdf2-sha256 hash, Press stores the plaintext

### Site stuck at "Pending"
**Cause:** `poll_pending_jobs` not running
**Fix:**
1. Check: `bench --site demo.mvpstorm.com execute frappe.client.get_list --kwargs '{"doctype": "Scheduled Job Type", "filters": {"name": "agent_job.poll_pending_jobs"}, "fields": ["name", "last_execution", "stopped"]}'`
2. If missing: `bench --site demo.mvpstorm.com migrate`
3. Manual poll: `bench --site demo.mvpstorm.com execute press.press.doctype.agent_job.agent_job.poll_pending_jobs`

### Build fails: "Incompatible Python version"
**Cause:** App requires Python 3.14+ but server has 3.11
**Fix:** Patched in `validations.py` — warn instead of raise. Committed on cloudflare-dns branch.

### Build fails: "Incompatible app version"
**Cause:** App's `develop` branch targets a newer Frappe version than expected
**Fix:** Use `version-15` or `version-16` tagged branches instead of `develop`

### Build fails: SyntaxError `type X = Y`
**Cause:** Frappe v16+ uses Python 3.12+ type alias syntax
**Fix:** Cannot build v16 on Python 3.11. Need Python 3.12+ on the build server.

### Dashboard "Select Frappe Framework Version" empty
**Cause:** Multiple flags must all be set (see setup checklist)
**Fix:** Set App Source `public=1, frappe=1`, Frappe Version `public=1`, Cluster `public=1`

### Dashboard shows "Connect to GitHub" even after installing app
**Cause:** OAuth token not saved — installation ≠ authorization
**Fix:** Navigate to OAuth URL directly: `https://github.com/login/oauth/authorize?client_id=YOUR_CLIENT_ID&state=BASE64_STATE`

### "Internal Server Error" on Access Requests page
**Cause:** Operator precedence bug in `support_access.py`
**Fix:** Patched — `(A == B) | (C == D)` instead of `A == B | C == D`

### "OutgoingEmailError" crashes build notifications
**Cause:** No Email Account configured
**Fix:** Create dummy Email Account with `default_outgoing=1` or set `disable_mail_notifications=1` in site_config.json

### Cluster `public` flag resets on save
**Cause:** Unknown — Cluster.save() resets public to 0
**Fix:** Set via direct DB: `frappe.db.set_value("Cluster", "Default", "public", 1)`

## Useful Commands

```bash
# SSH to servers
ssh press-ctrl    # Server 1 (89.167.116.92)
ssh press-f1      # Server 2 (89.167.57.21)

# Bench console
sudo -u frappe bash -c 'cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com console'

# Supervisor
supervisorctl status
supervisorctl restart all

# Poll pending jobs manually
sudo -u frappe bash -c 'cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com execute press.press.doctype.agent_job.agent_job.poll_pending_jobs'

# Check build status
bench --site demo.mvpstorm.com execute frappe.client.get_list --kwargs '{"doctype": "Deploy Candidate Build", "fields": ["name", "status", "creation"], "order_by": "creation desc", "limit_page_length": 5}'

# Clear all stuck jobs
bench --site demo.mvpstorm.com execute frappe.db.sql --args '["UPDATE \`tabAgent Job\` SET status = \"Failure\" WHERE status IN (\"Pending\", \"Undelivered\")"]'

# Rebuild dashboard assets
sudo -u frappe bash -c 'cd /home/frappe/frappe-bench && bench build --app press && bench clear-cache'
supervisorctl restart frappe-bench-web:frappe-bench-frappe-web
```
