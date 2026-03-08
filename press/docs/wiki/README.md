# Frappe Press Self-Hosted — Wiki

Self-hosted Frappe Press deployment on `demo.mvpstorm.com` with Cloudflare DNS.

## Table of Contents

### 00 — Getting Started
- [Overview](00-getting-started/overview.md) — Architecture, servers, what's deployed
- [Setup Checklist](00-getting-started/setup-checklist.md) — Every step to go from zero to working Press

### 01 — Setup & Configuration
- [Server Setup](01-setup/server-setup.md) — Server provisioning, Ansible, agent auth
- [Press Settings](01-setup/press-settings.md) — All Press Settings fields explained
- [Dashboard Setup](01-setup/dashboard-setup.md) — App Sources, Marketplace, Clusters, Teams
- [GitHub App](01-setup/github-app.md) — GitHub OAuth integration for the dashboard
- [Cloudflare DNS](01-setup/cloudflare-dns.md) — Patches applied to replace AWS Route53

### 02 — Operations
- [Adding Apps](02-operations/adding-apps.md) — Register apps, create benches, build & deploy
- [Adding Servers](02-operations/adding-servers.md) — How to add more servers
- [Backups & Restore](02-operations/backups.md) — Backup configuration and restore flow
- [Troubleshooting](02-operations/troubleshooting.md) — Common errors and fixes

### 03 — Demo System
- [Demo Provisioning](03-demo/demo-provisioning.md) — Landing page, invite codes, site creation flow

## Patches (cloudflare-dns branch)

7 files patched on `accurate-systems/press` fork, `cloudflare-dns` branch:

| # | File | Change |
|---|------|--------|
| 1 | `press/utils/dns.py` | AWS Route53 → Cloudflare REST API |
| 2 | `press/press/doctype/root_domain/root_domain.py` | boto3 → Cloudflare headers/API |
| 3 | `press/press/doctype/tls_certificate/tls_certificate.py` | certbot dns-route53 → dns-cloudflare |
| 4 | `press/press/doctype/root_domain/root_domain.json` | New fields: cloudflare_api_token, cloudflare_zone_id |
| 5 | `press/press/doctype/app_release/app_release.py` | Python 3.14 fallback → bench python |
| 6 | `press/press/doctype/deploy_candidate/validations.py` | Python version check: raise → warn |
| 7 | `press/press/doctype/support_access/support_access.py` | Operator precedence bug fix |
