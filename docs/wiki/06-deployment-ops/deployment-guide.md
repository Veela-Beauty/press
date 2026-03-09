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

## SSL Certificates
```bash
# Renew wildcard cert
certbot certonly --dns-cloudflare --dns-cloudflare-credentials /root/.cloudflare/credentials.ini -d '*.sandbox.mvpstorm.com'

# Permissions fix after renew
chmod -R 755 /etc/letsencrypt/live/ /etc/letsencrypt/archive/
```
