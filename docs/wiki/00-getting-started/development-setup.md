# Development Setup

## SSH Access
```bash
ssh press-ctrl   # 89.167.116.92 — Press controller
ssh press-f1     # 89.167.57.21  — App server
```

## Bench Console
```bash
su - frappe -c 'cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com console'
```

## Key Directories
| Path | Purpose |
|------|---------|
| `/home/frappe/frappe-bench/apps/press/` | Press source code |
| `/home/frappe/frappe-bench/sites/demo.mvpstorm.com/` | Press site |
| `/home/frappe/frappe-bench/builds/` | Docker build contexts |
| `/home/frappe/frappe-bench/clones/` | App release clones |
| `/home/frappe/agent/` | Agent on press-f1 |
| `/home/frappe/agent/config.json` | Agent config (press_url, access_token) |

## After Code Changes
```bash
# Python/API changes:
supervisorctl restart frappe-bench-web:frappe-bench-frappe-web

# Frontend (Vue) changes:
su - frappe -c 'cd /home/frappe/frappe-bench && bench build --force --app press && bench clear-cache'
supervisorctl restart frappe-bench-web:frappe-bench-frappe-web

# Clear redis cache:
su - frappe -c 'cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com clear-cache'
```

## Patched Files (cloudflare-dns branch + self-hosted fixes)
1. `press/utils/dns.py` — Cloudflare REST instead of boto3/Route53
2. `press/press/doctype/root_domain/root_domain.py` — Cloudflare + auto proxy domain
3. `press/press/doctype/tls_certificate/tls_certificate.py` — dns-cloudflare certbot plugin
4. `press/press/doctype/root_domain/root_domain.json` — Cloudflare fields
5. `press/press/doctype/app_release/app_release.py` — Python 3.14 fallback + version-aware syntax check
6. `press/press/doctype/deploy_candidate/validations.py` — Python version warn not raise
7. `press/press/doctype/release_group/release_group.py` — after_insert enabled=1
8. `press/press/api/analytics.py` — daily_usage handles missing log server
