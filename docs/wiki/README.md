# Frappe Press — Accurate Systems Fork Wiki

Enhanced fork of Frappe Press by Accurate Systems — enterprise capabilities, Cloudflare DNS, backup management.

## Table of Contents

### 00 — Getting Started
- [Overview](00-getting-started/overview.md) — What this fork does, brand identity
- [Architecture](00-getting-started/architecture.md) — System design, servers, deploy flow
- [Development Setup](00-getting-started/development-setup.md) — Prerequisites, IDE, local build

### 01 — Backend Development
- [File Reference Matrix](01-backend-development/file-reference-matrix.md) — Complete map of all ~67 files (dashboard, patches, backup, ops)

### 02 — Frontend Development
- [Dashboard Customization Guide](02-frontend-development/rebrand-guide.md) — All customized files, design tokens, how to modify
- [UI Style Guide](02-frontend-development/ui-style-guide.md) — Colors, typography, component patterns
- [Site Restore & Upload System](02-frontend-development/site-restore-upload.md) — Direct/chunked upload, S3 fallback, progress tracking

### 03 — Backup Integration
- [Backup Integration Guide](03-backup-integration/overview.md) — How daman_backup works: architecture, DocTypes, API, dashboard pages, scheduler, tests

### 06 — Deployment & Ops
- [Deployment Guide](06-deployment-ops/deployment-guide.md) — New bench/server/domain checklists
- [Server Provisioning](06-deployment-ops/server-provisioning.md) — Bootstrapping Hetzner VMs without private network
- [Ops Toolkit](06-deployment-ops/ops-toolkit.md) — do_retry.py bench execute scripts
- [Known Issues & Fixes](06-deployment-ops/known-issues-and-fixes.md) — Troubleshooting guide
- [Root Cause Patches](06-deployment-ops/root-cause-patches.md) — Patches applied to fix upstream issues
- [Scaling Guide](06-deployment-ops/scaling-guide.md) — Scaling considerations for self-hosted

### 07 — Implementation Status
- [Critical Issues](07-implementation-status/critical-issues.md) — Known blockers and workarounds

## Key Branch Patches

The `cloudflare-dns` branch patches 7 files from upstream Press:

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
| Login Gradient | `#046BD2 -> #197972` | Login page background |
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
