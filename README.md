<div align="center">

<img src="docs/assets/logo.png" alt="Accurate Systems" width="80"/>

# Accurate Systems Cloud Hosting Solutions

### Enterprise Cloud Hosting Platform

*Built on [Frappe Press](https://github.com/frappe/press) — enhanced with enterprise capabilities, Cloudflare DNS, and backup management*

[![Branch](https://img.shields.io/badge/branch-cloudflare--dns-046BD2?style=flat-square)](https://github.com/accurate-systems/press/tree/cloudflare-dns)
[![Upstream](https://img.shields.io/badge/upstream-frappe%2Fpress-gray?style=flat-square)](https://github.com/frappe/press)
[![Frappe](https://img.shields.io/badge/frappe-v15-blue?style=flat-square)](https://github.com/frappe/frappe)
[![License](https://img.shields.io/badge/license-AGPL--3.0-green?style=flat-square)](LICENSE)

[Website](https://accuratesystems.com.sa) · [Dashboard](https://autodeploypanel.mvpstorm.com/dashboard/login) · [Demo](https://demo.sandbox.mvpstorm.com) · [Wiki](docs/wiki/README.md)

</div>

---

<div align="center">
<img src="docs/assets/login-page.png" alt="Login Page" width="700"/>
<br/><sub><b>Login</b> — Custom design, Google & GitHub SSO</sub>
</div>

<br/>

<div align="center">
<img src="docs/assets/dashboard-sites.png" alt="Dashboard" width="700"/>
<br/><sub><b>Dashboard</b> — Dark sidebar, enhanced navigation, full server management</sub>
</div>

---

## What Is This?

An **enterprise-grade cloud hosting platform** built on [Frappe Press](https://github.com/frappe/press) architecture. We took the solid foundation of Press and enhanced it with new capabilities for production self-hosted deployments — Cloudflare DNS integration, server-level backup management, single-server mode, and a branded dashboard experience.

This is not a reskin. It's a **feature-enhanced fork** that adds what enterprises need to run Press on their own infrastructure.

### What We Added

| Capability | Upstream Press | This Fork |
|-----------|:---:|:---:|
| Cloudflare DNS (auto A/AAAA, wildcard SSL) | No | **Yes** |
| Server backup management (BorgBackup) | No | **Yes** |
| Backup monitoring dashboard (4 pages) | No | **Yes** |
| Alert system (email/webhook, CRUD) | No | **Yes** |
| Self-hosted on any VPS (Hetzner, DO, bare metal) | Partial | **Full** |
| Standalone single-server mode | No | **Yes** |
| Custom branded dashboard | Basic | **Full** |
| No vendor lock-in (no AWS/FrappeCloud dependency) | No | **Yes** |

---

## Features

### Custom Branded Dashboard

Fully customized dashboard with Accurate Systems branding and an enhanced dark-theme UI.

| Area | Scope |
|------|-------|
| Dashboard Vue SPA | ~20 components redesigned (dark sidebar, branded nav, login) |
| Email Templates | 30+ notification templates with custom branding |
| UI Theme | Brand color `#046BD2`, dark sidebar `#1E293B`, gradient login |
| Static Assets | Custom logo, favicon, images |

### Cloudflare DNS

Replaces AWS Route53 with Cloudflare API. 7 patched files handle DNS record management, TLS certificate provisioning, and wildcard SSL.

| Capability | How |
|-----------|-----|
| A/AAAA record management | `press/utils/dns.py` -- Cloudflare REST API |
| Wildcard SSL | `certbot dns-cloudflare` with DNS-01 challenge |
| Per-domain config | `cloudflare_api_token` + `cloudflare_zone_id` on Root Domain |
| No AWS dependency | Zero Route53/IAM/STS code paths |

### Self-Hosted Deployment

Run Press on your own infrastructure -- Hetzner, DigitalOcean, bare metal, or any Ubuntu 22.04 VPS.

- Standalone single-server mode (controller + app on one box)
- Multi-server scaling (add app servers from dashboard)
- Local Docker registry (no Docker Hub dependency)
- Automated Ansible provisioning via `do_retry.py` toolkit
- Demo landing page included

### Backup Management

Server-level backup management integrated directly into the Press dashboard. Powered by the [`daman_backup`](https://github.com/accurate-systems/daman-backup-app-server) Frappe app using BorgBackup + borgmatic.

| Component | Description |
|-----------|-------------|
| **BackupOverview** | Unified dashboard: server stats, job queue summary, client health |
| **ServerBackups** | Server list with Run Backup / Check Health actions |
| **BackupJobs** | Job queue with Cancel / Retry actions, real-time status |
| **BackupAlerts** | Full CRUD for alert rules (email/webhook, configurable thresholds) |

**Backend**: 8 whitelisted API methods in `press_api.py`, 10 DocTypes, 40 passing tests.
**Execution**: borgmatic container on the host, supports Docker Direct and Portainer API modes.
See the [Backup Integration Guide](docs/wiki/03-backup-integration/overview.md) for full details.

### Upstream Sync

Structured process to stay current with Frappe Press upstream.

- Per-commit analysis with risk assessment before merging
- Every decision (adopt/skip/adapt) recorded in `SYNC_JOURNAL.md`
- ~95% of conflicts are branding strings (trivial resolution)
- 2-week sync cadence

---

## Architecture

```
                    ┌─── Cloudflare DNS ───┐
                    │  *.mvpstorm.com      │
                    │  A / AAAA records    │
                    │  Wildcard SSL        │
                    └──────┬───────────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            ▼              │              ▼
┌───────────────────┐      │   ┌───────────────────┐
│  🔧 Controller    │      │   │  📦 App Server    │
│  (Server 1)       │◄─────┘   │  (Server 2)       │
│                   │  Agent   │                   │
│  • Press App      │────────►│  • Docker Engine   │
│  • Dashboard UI   │  API    │  • Bench Containers│
│  • Build Server   │         │  • MariaDB         │
│  • Docker Registry│         │  • Nginx Proxy     │
│  • Job Scheduler  │         │  • Redis           │
└───────────────────┘         └───────────────────┘
        │                              │
        │         ┌────────┐           │
        └────────►│ GitHub │◄──────────┘
                  │ (Apps) │
                  └────────┘
```

---

## Design Tokens

| Token | Value | Preview | Usage |
|-------|-------|---------|-------|
| Primary Blue | `#046BD2` | ![#046BD2](https://via.placeholder.com/16/046BD2/046BD2.png) | Buttons, links, active states |
| Primary Hover | `#045CB4` | ![#045CB4](https://via.placeholder.com/16/045CB4/045CB4.png) | Button hover |
| Dark Sidebar | `#1E293B` | ![#1E293B](https://via.placeholder.com/16/1E293B/1E293B.png) | Sidebar background |
| Teal Accent | `#197972` | ![#197972](https://via.placeholder.com/16/197972/197972.png) | Login gradient endpoint |
| Login Gradient | `#046BD2 → #197972` | | Background gradient |

---

## Quick Start

### Prerequisites

- Ubuntu 22.04 LTS (2 servers recommended, 4vCPU / 8GB RAM each)
- Domain on Cloudflare
- Cloudflare API token (Zone:Edit permission)

### Install

```bash
# 1. Install Frappe Bench
pip install frappe-bench
bench init frappe-bench --frappe-branch version-15
cd frappe-bench

# 2. Get this fork
bench get-app https://github.com/accurate-systems/press.git --branch cloudflare-dns

# 3. Create site
bench new-site cloud.yourdomain.com --install-app press

# 4. Configure (in Press UI)
#    - Add Cloudflare API token to Root Domain
#    - Set Zone ID in Cluster
#    - Create DNS records

# 5. Build & launch
bench build --app press
bench --site cloud.yourdomain.com migrate
sudo supervisorctl restart all
```

See the [full setup guide](docs/wiki/06-deployment-ops/server-provisioning.md) for detailed instructions.

---

## Enhanced Files (vs Upstream Press)

| File | What Changed |
|------|-------------|
| `press/utils/dns.py` | Cloudflare REST API (replaces AWS Route53) |
| `press/press/doctype/root_domain/root_domain.py` | Cloudflare API headers and calls |
| `press/press/doctype/root_domain/root_domain.json` | Added `cloudflare_api_token`, `cloudflare_zone_id` |
| `press/press/doctype/tls_certificate/tls_certificate.py` | `certbot dns-cloudflare` (replaces dns-route53) |
| `press/press/doctype/virtual_machine/virtual_machine.py` | Null guards for `vpc_id` / `security_group_id` |
| `press/press/doctype/server/server.py` | `ca_public_key` in unified server setup |
| `dashboard/src/assets/style.css` | Custom theme and UI enhancements |
| `dashboard/src/components/AppSidebar*.vue` | Dark sidebar with enhanced navigation |
| `dashboard/src/pages/LoginBox.vue` | Redesigned login page |

---

## Scaling

Start with a single server and scale horizontally as your client base grows:

| Stage | Setup | Capacity | Cost (Hetzner) |
|-------|-------|----------|----------------|
| **Starter** | 1 controller + 1 app server | 5-15 sites | ~EUR30/mo |
| **Growth** | 1 controller + 2 app servers | 15-30 sites | ~EUR45/mo |
| **Production** | 1 controller + 2 app + 1 DB | 30-60 sites | ~EUR80/mo |
| **Enterprise** | 1 controller + 4 app + 2 DB | 60-120 sites | ~EUR150/mo |
| **Scale** | 1 ctrl + LB + 3 proxy + 8 app + 2 DB | 150-200 sites | ~EUR240/mo |

Press supports adding new servers, migrating sites between servers, and multi-cluster deployments across regions — all from the dashboard.

See the [Scaling Guide](docs/wiki/06-deployment-ops/scaling-guide.md) for full details: when to scale, how to add servers, DNS patterns, monitoring thresholds, and cost estimation.

---

## Documentation

Full project documentation lives in the [Wiki](docs/wiki/README.md):

| Section | Content |
|---------|---------|
| [Overview](docs/wiki/00-getting-started/overview.md) | What this fork does, brand identity |
| [Architecture](docs/wiki/00-getting-started/architecture.md) | Servers, DNS, deploy flow |
| [File Reference Matrix](docs/wiki/01-backend-development/file-reference-matrix.md) | Complete map of all ~67 files |
| [Rebrand Guide](docs/wiki/02-frontend-development/rebrand-guide.md) | All changed files, design tokens |
| [Backup Integration](docs/wiki/03-backup-integration/overview.md) | How daman_backup works, DocTypes, API |
| [Server Provisioning](docs/wiki/06-deployment-ops/server-provisioning.md) | Bootstrapping new servers |
| [Ops Toolkit](docs/wiki/06-deployment-ops/ops-toolkit.md) | Management scripts |
| [Scaling Guide](docs/wiki/06-deployment-ops/scaling-guide.md) | When and how to scale, sizing, costs |

---

## Keeping in Sync with Upstream

This fork uses a structured sync process documented in [`SYNC_JOURNAL.md`](SYNC_JOURNAL.md):

- **Method**: Per-commit analysis with risk assessment before merging
- **Tracking**: Every decision (adopt/skip/adapt) is recorded with reasoning
- **Conflict pattern**: ~95% of changes are branding strings — conflicts are trivial
- **Frequency**: Every 2 weeks

```bash
# Sync workflow
git fetch origin develop
# Analyze upstream commits (use sync-fork skill or manual review)
# See SYNC_JOURNAL.md for the structured process
git rebase origin/develop
bench build --force --app press
bench --site your-site migrate
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | [Frappe Framework](https://github.com/frappe/frappe) v15 (Python) |
| Dashboard | [Frappe UI](https://github.com/frappe/frappe-ui) (Vue 3) |
| Containers | [Docker](https://www.docker.com) |
| Provisioning | [Ansible](https://www.ansible.com) |
| DNS | [Cloudflare API](https://developers.cloudflare.com/api/) |
| SSL | [Let's Encrypt](https://letsencrypt.org/) + DNS-01 challenge |
| Database | MariaDB 10.6+ |
| Agent | [Frappe Agent](https://github.com/frappe/agent) (Flask) |

---

## License

GNU Affero General Public License v3.0 — same as upstream. See [LICENSE](LICENSE).

---

<div align="center">

**Built by [Accurate Systems](https://accuratesystems.com.sa)**

<sub>Cloud Hosting Solutions — Enterprise-grade ERPNext hosting on your infrastructure</sub>

</div>
