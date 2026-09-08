# Frappe Press — Accurate Systems Fork Wiki

Enhanced fork of Frappe Press by Accurate Systems — enterprise capabilities, Cloudflare DNS, backup management.

## Table of Contents

### 00 — Getting Started
- [Overview](00-getting-started/overview.md) — What this fork does, brand identity
- [Architecture](00-getting-started/architecture.md) — System design, servers, deploy flow
- [Development Setup](00-getting-started/development-setup.md) — Prerequisites, IDE, local build

### 01 — Backend Development
- [File Reference Matrix](01-backend-development/file-reference-matrix.md) — Complete map of all ~67 files (dashboard, patches, backup, ops)
- [Team SSH Access Management](01-backend-development/team-ssh-management.md) — Full feature: doctype fields, admin APIs, cert generation, agent forwarding patch, UI flow

### 02 — Frontend Development
- [Dashboard Customization Guide](02-frontend-development/rebrand-guide.md) — All customized files, design tokens, how to modify
- [UI Style Guide](02-frontend-development/ui-style-guide.md) — Colors, typography, component patterns
- [Site Restore & Upload System](02-frontend-development/site-restore-upload.md) — Direct/chunked upload, S3 fallback, progress tracking

### 03 — Integrations
- [GitHub App User Tokens](03-integrations/github-app-user-tokens.md) — Per-user GitHub OAuth for in-bench git operations (Option C); architecture, ops, troubleshooting
- [MCP Server — Token Issuance](03-integrations/mcp-server.md) — Token TTL (1–90 days), password OR email-OTP re-auth, Press MCP Email OTP doctype

### 03 — Backup Integration
- [Backup Integration Guide](03-backup-integration/overview.md) — How daman_backup works: architecture, DocTypes, API, dashboard pages, scheduler, tests

### 06 — Deployment & Ops
- [Deployment Guide](06-deployment-ops/deployment-guide.md) — New bench/server/domain checklists
- [Server Provisioning](06-deployment-ops/server-provisioning.md) — Bootstrapping Hetzner VMs without private network
- [Ops Toolkit](06-deployment-ops/ops-toolkit.md) — do_retry.py bench execute scripts
- [Press-Ctrl Stability Runbook](06-deployment-ops/press-ctrl-stability-runbook.md) — `bench-update-safe` wrapper, iron rules, snapshots, rollback. **Required reading** before any `bench update` / `pip install` on press-ctrl.
- [Site Usage Pipeline](06-deployment-ops/site-usage-pipeline.md) — Daily site-usage audit + dashboard backfill
- [Known Issues & Fixes](06-deployment-ops/known-issues-and-fixes.md) — Troubleshooting guide
- [Root Cause Patches](06-deployment-ops/root-cause-patches.md) — Patches applied to fix upstream issues
- [Scaling Guide](06-deployment-ops/scaling-guide.md) — Scaling considerations for self-hosted

### 07 — Implementation Status
- [Features Matrix](07-implementation-status/features-matrix.md) — Complete list of all fork features, patches, and enhancements
- [Critical Issues](07-implementation-status/critical-issues.md) — Known blockers and workarounds

### 08 — Lessons Learned
- [2026-09-08 — A stranded Server freezes every job on it](08-lessons/2026-09-08-stranded-server-freezes-every-job.md) — `Server.status != "Active"` silently drops a whole box from job polling *and* site updates. Also: writing `Agent Job.status` without its callback orphans the record, `bench clear-cache` does not clear `app_hooks`, and a purged registry tag makes a stuck bench unretryable.
- [2026-04-29 — bench-watch, Site Overview usage, Log Server](08-lessons/2026-04-29-bench-watch-and-log-server.md) — `dashboard_fields` is a silent whitelist; 5 repeating-pattern bugs.

## Key Branch Patches

The `cloudflare-dns` branch patches **15 files** from upstream Press. See [Features Matrix](07-implementation-status/features-matrix.md) for the complete list.

**Recent additions (2026-03-31):**
- GitHub webhook integration — instant push notifications (no more 5-min poll wait)
- Public repo auto-detect — `public=1` set automatically for `frappe/*` repos
- GitHub re-auth elimination — reuses existing installations when OAuth token expires
- Failed source retry — every 30 min, retries `last_github_poll_failed=True` sources
- Demo data engine — app-safe dependency handling, construction trading seed set

## Quick Reference

| Token | Value | Usage |
|-------|-------|-------|
| Primary Blue | `#046BD2` | Buttons, links, active sidebar |
| Primary Hover | `#045CB4` | Button hover states |
| Dark Sidebar | `#1E293B` | Sidebar background |
| Login Gradient | `#046BD2 -> #197972` | Login page background |
| Teal Accent | `#197972` | Gradient endpoint |

## Build & Deploy

For **dashboard-only changes** (HTML/JS/CSS — no Python deps touched):

```bash
ssh press-ctrl
su - frappe
cd /home/frappe/frappe-bench
git -C apps/press pull upstream cloudflare-dns
bench build --force --app press
bench --site demo.mvpstorm.com clear-cache
sudo supervisorctl restart frappe-bench-web:frappe-bench-frappe-web
```

For **any change that touches Python code, requirements, or migrations** — use the safe wrapper instead (auto-rollback on failure, no more 10-hour outages):

```bash
ssh press-ctrl
sudo -u frappe bench-update-safe              # full pipeline with safety nets
sudo -u frappe bench-update-safe --dry-run    # preview only
```

See [Press-Ctrl Stability Runbook](06-deployment-ops/press-ctrl-stability-runbook.md) for the full pipeline and iron rules.
