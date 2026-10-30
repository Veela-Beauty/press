# Deployment Operations Guide

## New Bench Checklist (after creating via dashboard)
When a user creates a new bench from the dashboard, verify:

```bash
# 1. Bench is enabled (should be auto-set now, but verify)
mysql -u DB_USER -pDB_PASS DB_NAME -e "SELECT name, enabled, public FROM \`tabRelease Group\` ORDER BY creation DESC LIMIT 5;"

# 2. After deploy, check bench status
mysql -u DB_USER -pDB_PASS DB_NAME -e "SELECT name, status, group FROM \`tabBench\` ORDER BY creation DESC LIMIT 5;"

# 3. Check Nginx upstream points to container port (not self)
ssh press-f1 "grep '^upstream' /home/frappe/agent/nginx/proxy.conf"
```

## New Root Domain Checklist
When adding a new root domain (e.g., `newdomain.com`):

```bash
# The domain now auto-links to Proxy Servers via after_insert
# But verify it worked:
mysql ... -e "SELECT name, domain, parent FROM \`tabProxy Server Domain\`;"

# If missing, run manually:
bench --site demo.mvpstorm.com execute press.press.doctype.root_domain.root_domain.RootDomain.add_to_proxies --args '["DOMAIN_NAME"]'
```

## New Server Checklist (Hetzner VM via dashboard)
See Lessons 64-79 in frappe-press-lessons.md. Quick reference:

```bash
# Bootstrap new server (after VM created but bare Ubuntu)
bench --site demo.mvpstorm.com execute press.do_retry.bootstrap_new_server --args '["SERVER_NAME"]'
# Wait for Ansible (~5 min), then:
bench --site demo.mvpstorm.com execute press.do_retry.post_ansible_setup --args '["SERVER_NAME", "https://autodeploypanel.mvpstorm.com", "press-f1.sandbox.mvpstorm.com"]'
# Verify agent reachable:
bench --site demo.mvpstorm.com execute press.do_retry.ping_server_agent_authed --args '["SERVER_NAME"]'
```

## New Site Creation Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Internal Server Error` on Create | Proxy Server Domain missing for domain | Run `add_to_proxies()` on Root Domain |
| `IN ()` SQL error | `proxy_servers` list empty | Same as above |
| `Invalid release found` | App requires newer Python | `check_python_syntax` now skips if Python too old — clear `invalid_release` flag |
| `Internal Server Error` on Daily Usage | `get_usage()` returns dict not list | Fixed in analytics.py |

## Deploy / Build Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| Build stuck at Running | Agent not reporting back to Press | Check agent `config.json` has correct `press_url` |
| `pre-build: invalid release found` | App Release flagged as invalid | `UPDATE tabApp Release SET invalid_release=0 WHERE invalid_release=1` |
| `requires-python >= 3.14` | Frappe v16 needs Python 3.14 | Fixed: syntax check skipped when Python too old |
| No bench in New Site selector | Release Group `public=0` or `enabled=0` | Set `public=1` OR use bench detail page New Site button |
| Bench not in My Benches | Release Group `public=1` | Set `public=0` for managed benches |

## Deploying the press app to press-ctrl

How 0.7.2 to 0.7.5 were deployed (2026-10-30). Scripts with every guard are in the
press-ops repo: `scripts/confidential-ui-deploy-2026-10-30/`, `scripts/infra-ui-deploy-2026-10-30/`,
`scripts/font-size-deploy-2026-10-30/` (copy the newest and change FROM / TARGET / OUT / TAG).

1. **Guards**: `apps/press` HEAD is the expected commit; no tracked changes except the
   generated `dashboard/auto-imports.d.ts` (see below); GitHub `cloudflare-dns` head is exactly
   the merge commit you reviewed.
2. **Snapshot first** (`/home/frappe/deploy-safety-<date>/`): a `safety/pre-...` tag (push it
   from the dev box: press-ctrl's GitHub key is read-only), a bundle of every ref plus the stash
   SHAs, the untracked files, the built `press/public/dashboard`, `www/dashboard.html`, and the
   uncommitted diff + untracked files of every OTHER app. Copy it to the dev box and check the
   sha256 list. Add a DB dump when the release changes a schema.
3. `git merge --ff-only` in `apps/press` only, as `frappe`. **Never `bench update`**: other apps
   (`daman_backup`, `frappe_theme_switcher`, `sanad_*`) carry uncommitted server-side work.
4. Import check in a fresh process; `bench --site demo.mvpstorm.com reload-doctype <DocType>`
   for a changed schema (no full `migrate`, same reason as 3).
5. `yarn build` in `apps/press/dashboard` when Vue changed; `clear-cache`;
   `supervisorctl restart frappe-bench-web:` (never `restart all`).
6. **Post-state**: same stash count, same untracked files, every other app's diff hash equal to
   the snapshot. Then live checks (dashboard 200 on the new build, the new strings in the bundle).

**When `hooks.py` changed**, check `frappe.get_hooks("<hook>")` in a fresh process after the
deploy. On 0.7.4 the Redis `app_hooks` cache kept the old hooks through `clear-cache` and a
worker restart; deleting the key `<db_name>|app_hooks` fixed it. See
[the lesson](../08-lessons/2026-10-30-hooks-change-not-seen.md).

**`dashboard/auto-imports.d.ts`** is rewritten by unplugin-auto-import on every `yarn build`
(new Lucide icons), so it shows as modified after each build until the change is committed.
The deploy guard accepts it only when every changed line is a generated
`const Lucide...: typeof import('~icons/lucide/...')['default']` declaration, keeps the diff in
the snapshot, and resets it before the merge.

## SSL Certificates
```bash
# Renew wildcard cert
certbot certonly --dns-cloudflare --dns-cloudflare-credentials /root/.cloudflare/credentials.ini -d '*.sandbox.mvpstorm.com'

# Permissions fix after renew
chmod -R 755 /etc/letsencrypt/live/ /etc/letsencrypt/archive/
```
