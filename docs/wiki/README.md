# Frappe Press — Accurate Systems Fork Wiki

White-labeled fork of Frappe Press for Accurate Systems Cloud Hosting Solutions.

## Table of Contents

### 00 — Getting Started
- [Overview](00-getting-started/overview.md) — What this fork does, brand identity
- [Architecture](00-getting-started/architecture.md) — System design, servers, deploy flow

### 02 — Frontend Development
- [Rebrand Guide](02-frontend-development/rebrand-guide.md) — All files changed, design tokens, how to modify
- [UI Style Guide](02-frontend-development/ui-style-guide.md) — Colors, typography, component patterns

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
