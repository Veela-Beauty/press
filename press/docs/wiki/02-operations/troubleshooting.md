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

### A new override in hooks.py does nothing after a deploy
**Cause:** `bench clear-cache` ran before the web and worker restart. The old processes, still on the old code,
rebuilt `app_hooks` in Redis from the old `hooks.py`, so Frappe kept dispatching to the original method (0.7.59:
`frappe.client.get_password` still went to Frappe, not `press.overrides.get_password`).
**Check:** press-ops `scripts/mcp-deploy-update-2026-11-23/41_check_override_hook.py` prints where a method dispatches.
**Fix:** run `bench --site demo.mvpstorm.com clear-cache` again once every process runs the new code; deploy scripts
clear the cache after the restarts (`40_deploy_0759.sh`).

### Alert email accepted but not received
**Cause:** after Brevo accepts a message, the receiving side can still drop or file it: Gmail Spam, Promotions or
Updates, or a Brevo block. mvpstorm.com has Brevo DKIM (`brevo1`, `brevo2`) and DMARC `p=reject`, but no SPF record.
**Check:** a recorded Watch Tower event means the relay took the email; send a neutral test and the alert again with
`45_mail_test_agent_watch.py`, then search the inbox and its tabs for both subjects.
**Fix:** if only the neutral test arrives, reword the alert; if neither arrives, read Brevo's transactional log.
Add SPF for mvpstorm.com (`v=spf1 include:spf.brevo.com ~all`) either way.

### "Site creation failed" on a site that works
**Cause:** `Site.creation_failed` is still set from a failed New Site or Restore job that was finished by hand. Status
can be Active; the 14-day drop only takes Broken sites.
**Check:** `frappe.get_all("Site", filters={"status": "Active", "creation_failed": ("is", "set")}, pluck="name")`.
**Fix:** since 0.7.64 the hourly `clear_stale_creation_failed` clears it after a green migrate; to clear it now, see
[Backups: after a restore finished by hand](backups.md#after-a-restore-finished-by-hand).

### MCP `mint_dashboard_login_url` refused over a confidential site
**Cause:** a dashboard session reaches every site of the team, so the tool needs every confidential site of the team
unlocked, whichever page `redirect_to` names (`scope/call_guard.py` `_rule_whole_team`). Not a bug.
**Fix:** read the field the page shows instead, or the owner issues a token that names all those sites and enters the
Admin PIN. Since 0.7.65 the refusal lists every locked site.

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
