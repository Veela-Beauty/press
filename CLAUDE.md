# Frappe Press Self-Hosted (accurate-systems fork)

Self-hosted Frappe Press — a white-label cloud hosting platform for deploying ERPNext/Frappe sites.
Running at `demo.mvpstorm.com`. Fork of `frappe/press`, branch `cloudflare-dns`.

## Stack

- Frappe framework (Python) — Press controller app
- Vue.js SPA — dashboard at `/dashboard`
- MariaDB — site DB on press-ctrl
- Agent (Python Flask) — runs on each app server, receives jobs from Press
- Docker — builds bench images, deploys sites in containers
- Cloudflare — DNS management (replaces upstream AWS Route53)
- certbot + dns-cloudflare — TLS certificate issuance

## Servers

| Server | IP | Role |
|--------|----|------|
| press-ctrl | 89.167.116.92 | Press controller, scheduler, Docker registry |
| press-f1 | 89.167.57.21 | App server (standalone: Server + DB + Proxy) |
| u4 | 157.90.244.216 | App server (standalone: sandbox cluster) |

SSH aliases: `ssh press-ctrl`, `ssh press-f1`
SSH key: `E:/.ssh/new_id_ed25519` (configured for press-ctrl and press-f1)
u4 accessible via press-ctrl: `ssh root@89.167.116.92 "ssh root@157.90.244.216 'cmd'"` (no direct SSH config)

**Push method:** press-ctrl has SSH key to GitHub (`upstream` remote via `git@github.com:accurate-systems/press.git`).
To push local commits: bundle → SCP to press-ctrl → apply → push from there.

## Commands

```bash
# On press-ctrl
sudo -u frappe bash -c 'cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com console'
bench --site demo.mvpstorm.com migrate
bench --site demo.mvpstorm.com clear-cache
supervisorctl status
supervisorctl restart all

# Build dashboard assets
sudo -u frappe bash -c 'cd /home/frappe/frappe-bench && bench build --app press && bench clear-cache'
supervisorctl restart frappe-bench-web:frappe-bench-frappe-web

# Poll pending jobs manually
bench --site demo.mvpstorm.com execute press.press.doctype.agent_job.agent_job.poll_pending_jobs
```

## Structure

```
press/
  press/doctype/         # All Press DocTypes (200+)
  press/page/            # Dashboard Vue pages
  utils/dns.py           # PATCHED: Cloudflare DNS instead of Route53
  hooks.py               # Scheduler events, doc_events, fixtures
scripts/
  provision-server.sh    # Automate new server setup (13 steps)
  setup-build-worker.sh  # Add dedicated build queue worker
  hooks/
    fix-letsencrypt-permissions.sh  # Post-renewal chmod hook
    docker-cleanup.sh               # Daily container prune
    sync-press-tls-records.sh       # Sync cert expiry to Press DB
    sync-sandbox-cert-to-press-f1.sh  # Deploy sandbox cert on renewal
docs/wiki/                # User-facing wiki (deployed docs)
press/docs/wiki/          # Ops wiki (self-hosted operations)
```

## Architecture

Press runs on press-ctrl and polls agents on app servers every 5 seconds (`poll_pending_jobs`).
Each app server runs one agent that receives job commands and reports status back to Press.
In standalone mode, one physical server serves as Server + Database Server + Proxy Server —
three separate DocType records, each with its own `agent_password` in `__Auth` table.

## Conventions

- Fork branch: `cloudflare-dns` — all self-hosted patches live here
- Remote: `fork` = `https://github.com/accurate-systems/press.git`
- Never merge upstream without checking for conflicts with Cloudflare patches
- Agent auth: Press stores plaintext in `__Auth` (encrypted); agent stores PBKDF2-SHA256 hash
- SSL certs: wildcard per subdomain level — `*.demo.mvpstorm.com` ≠ `*.sandbox.mvpstorm.com`
- Cluster.public: always set via `frappe.db.set_value()`, never via UI (patched but be cautious)

## Key Context

- `developer_mode=1` has been REMOVED — replaced by dedicated build worker (setup-build-worker.sh deployed)
- `disable_mail_notifications=1` in site_config.json (no email account configured)
- Docker registry at `89.167.116.92:5000` (HTTP) — all app servers need it in `insecure-registries`
- Certbot renewal hooks in `/etc/letsencrypt/renewal-hooks/` — see `scripts/hooks/`
- v16 disabled — build server has Python 3.11, v16 needs Python 3.12+

## Patched Files (vs upstream frappe/press)

1. `press/utils/dns.py` — Cloudflare REST API
2. `press/press/doctype/root_domain/root_domain.py` — Cloudflare
3. `press/press/doctype/root_domain/root_domain.json` — new cloudflare fields
4. `press/press/doctype/tls_certificate/tls_certificate.py` — certbot dns-cloudflare
5. `press/press/doctype/app_release/app_release.py` — Python 3.14 fallback
6. `press/press/doctype/deploy_candidate/validations.py` — warn instead of raise
7. `press/press/doctype/support_access/support_access.py` — operator precedence fix
8. `press/press/doctype/cluster/cluster.py` — preserve Cluster.public flag on save

## Ops Wiki

`press/docs/wiki/` — full self-hosted operations wiki
- `lessons-learned.md` — 53 lessons with status audit
- `02-operations/platform-risk-checklist.md` — MANDATORY before/after every change

## Environment

Secrets are on the servers, not in this repo:
- `/root/.cloudflare/credentials.ini` — Cloudflare API token
- `/home/frappe/agent/config.json` — agent access_token (PBKDF2 hash)
- Press `__Auth` table — all agent_passwords (encrypted)
