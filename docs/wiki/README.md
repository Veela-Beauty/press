# Frappe Press — Accurate Systems Fork Wiki

White-labeled fork of Frappe Press for Accurate Systems Cloud Hosting Solutions.

## Table of Contents

### 00 — Getting Started
- [Overview](00-getting-started/overview.md) — What this fork does, brand identity
- [Architecture](00-getting-started/architecture.md) — System design, servers, deploy flow

### 02 — Frontend Development
- [Rebrand Guide](02-frontend-development/rebrand-guide.md) — All files changed, design tokens, how to modify
- [UI Style Guide](02-frontend-development/ui-style-guide.md) — Colors, typography, component patterns

### 06 — Deployment & Ops
- [Server Provisioning Guide](06-deployment-ops/server-provisioning.md) — bootstrapping new servers on Hetzner without private network
- [Ops Toolkit (do_retry.py)](06-deployment-ops/ops-toolkit.md) — bench execute scripts for server management
- [Scaling Guide](06-deployment-ops/scaling-guide.md) — how to grow from 1 server to multi-server clusters, sizing, cost estimation

## Key Branch Patches

The `cloudflare-dns` branch patches 6 files from upstream Press:

| File | What changed |
|---|---|
| `press/utils/dns.py` | Cloudflare REST API instead of AWS Route53 |
| `press/press/doctype/root_domain/root_domain.py` | Cloudflare headers and API calls |
| `press/press/doctype/root_domain/root_domain.json` | Added `cloudflare_api_token`, `cloudflare_zone_id` fields |
| `press/press/doctype/tls_certificate/tls_certificate.py` | `certbot dns-cloudflare` instead of `dns-route53` |
| `press/press/doctype/virtual_machine/virtual_machine.py` | Null guards for `vpc_id` and `security_group_id` |
| `press/press/doctype/server/server.py` | Pass `ca_public_key` in `_setup_unified_server()` |
| `press/playbooks/roles/user_ssh_certificate/tasks/main.yml` | Accept `ca_public_key` var instead of downloading from frappecloud.com |

## Quick Reference

| Token | Value | Usage |
|-------|-------|-------|
| Primary Blue | `#046BD2` | Buttons, links, active sidebar |
| Primary Hover | `#045CB4` | Button hover states |
| Dark Sidebar | `#1E293B` | Sidebar background |
| Login Gradient | `#046BD2 → #197972` | Login page background |
| Teal Accent | `#197972` | Gradient endpoint |

## Build & Deploy

```bash
ssh press-ctrl
su - frappe
cd /home/frappe/frappe-bench
git -C apps/press pull upstream cloudflare-dns
bench build --force --app press
bench --site demo.mvpstorm.com clear-cache
sudo supervisorctl restart frappe-bench-web:frappe-bench-frappe-web
```

## Ops Scripts

- `press/do_retry.py` — server bootstrap and verification toolkit (not a patch, new file)
