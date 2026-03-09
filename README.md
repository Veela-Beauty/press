<div align="center" markdown="1">

<img src="https://frappe.io/files/Group%202%20(1).png" alt="Press logo" width="80"/>
<h1>Accurate Systems Cloud Hosting Solutions</h1>

**White-label Self-Hosted Cloud Platform — Fork of [Frappe Press](https://github.com/frappe/press)**

</div>

<div align="center">
	<a href="https://accuratesystems.com.sa">Website</a>
	-
	<a href="https://autodeploypanel.mvpstorm.com/dashboard/login">Dashboard</a>
	-
	<a href="https://demo.sandbox.mvpstorm.com">Demo</a>
</div>

---

## What Is This Fork?

This is a **white-label fork** of [Frappe Press](https://github.com/frappe/press) maintained by [Accurate Systems](https://accuratesystems.com.sa). It transforms Frappe Cloud into a self-hosted, fully branded cloud hosting platform under the **Accurate Systems** identity.

### Fork Branch

- **Branch**: `cloudflare-dns` (based on upstream `develop`)
- **Upstream**: [frappe/press](https://github.com/frappe/press) `develop` branch
- **Fork purpose**: White-label rebrand + Cloudflare DNS integration + self-hosted deployment tooling

## What's Different from Upstream

### 1. Full White-Label Rebrand (~95% of changes)

All user-facing references to "Frappe Cloud" have been replaced with "Accurate Systems Cloud Hosting Solutions":

- **Brand strings**: ~80 Python/Vue files rebranded ("Frappe Cloud" → "Accurate Systems Cloud")
- **URLs**: ~60 files updated (frappecloud.com → accuratesystems.com.sa)
- **Email templates**: 30+ HTML templates rebranded
- **Dashboard UI**: Custom logo, brand color (`#046BD2`), dark sidebar (`#1E293B`), login gradient
- **Login pages**: Branded `LoginBox.vue`, `SaaSLoginBox.vue` with gradient background and white logo

### 2. Cloudflare DNS Integration (New Feature)

Native Cloudflare DNS provider support for automatic domain management:

- **Root Domain**: Cloudflare API token stored per root domain
- **Cluster**: Cloudflare zone ID configuration
- **Automatic DNS**: A/AAAA record creation for sites and servers via Cloudflare API
- **Wildcard SSL**: Let's Encrypt wildcard certificates with Cloudflare DNS-01 challenge

### 3. Self-Hosted Deployment Tooling (New Feature)

Scripts and utilities for deploying Press on your own infrastructure:

- **`selfhosted_utils.py`**: Helper functions for standalone server provisioning
- **`do_retry.py`**: Retry logic for deployment operations
- **Demo landing page**: Static HTML at `demo.sandbox.mvpstorm.com` for trial signups
- **Standalone mode**: Full support for single-server deployments (controller + app server on separate machines)

### 4. Schema Extensions

- **Cluster DocType**: Added `cloudflare_zone_id` field
- **Root Domain DocType**: Added `cloudflare_api_token` field

## Architecture

```
┌─────────────────────────────────────┐
│  Press Controller (Server 1)        │
│  - Frappe Bench + Press app         │
│  - Dashboard (Vue SPA)              │
│  - Docker Registry (local)          │
│  - Build server (clones + builds)   │
│  - Cloudflare DNS management        │
└──────────────┬──────────────────────┘
               │ Agent API
┌──────────────▼──────────────────────┐
│  App Server / Standalone (Server 2) │
│  - Docker containers (benches)      │
│  - MariaDB (tenant databases)       │
│  - Nginx (reverse proxy)            │
│  - Redis                            │
│  - Frappe Agent                     │
└─────────────────────────────────────┘
```

## Setup

### Prerequisites

- Ubuntu 22.04 LTS
- 2 Hetzner (or equivalent) servers: 4vCPU, 8GB RAM minimum each
- Domain with Cloudflare DNS
- Cloudflare API token with Zone:Edit permissions

### Installation

1. **Install Frappe Bench** on Server 1 (controller):
   ```bash
   # Standard frappe-bench installation
   pip install frappe-bench
   bench init frappe-bench --frappe-branch version-15
   cd frappe-bench
   ```

2. **Install Press** (this fork):
   ```bash
   bench get-app https://github.com/accurate-systems/press.git --branch cloudflare-dns
   bench new-site your-site.domain.com --install-app press
   ```

3. **Configure Cloudflare**:
   - Add your Cloudflare API token to the Root Domain record in Press
   - Set the Zone ID in the Cluster record
   - Create DNS records: `A` for controller, wildcard `A` for app server

4. **Provision App Server** (Server 2):
   - Use Press's built-in Ansible provisioning
   - Or follow manual standalone setup (see wiki)

5. **Build & Deploy**:
   ```bash
   bench build --app press
   bench --site your-site.domain.com migrate
   sudo supervisorctl restart all
   ```

### Documentation

Detailed setup guides and architecture docs are available in the [project wiki](docs/wiki/).

## Keeping in Sync with Upstream

This fork is actively maintained and synced with upstream `frappe/press` using a structured process:

- **Sync method**: Per-commit analysis with conflict risk assessment before merging
- **Sync journal**: All sync operations are recorded in `SYNC_JOURNAL.md` with per-commit decisions
- **Conflict pattern**: Most conflicts are trivial (branding strings vs upstream logic changes in different code sections)
- **Sync frequency**: Every 2 weeks recommended

To sync with upstream:
```bash
git remote add frappe https://github.com/frappe/press.git  # if not already added
git fetch frappe develop
# Analyze upstream commits before merging (recommended)
# See SYNC_JOURNAL.md for the structured process
git rebase frappe/develop
```

## Tech Stack

- [**Frappe Framework**](https://github.com/frappe/frappe) v15 — Full-stack Python/JS web framework
- [**Frappe UI**](https://github.com/frappe/frappe-ui) — Vue-based dashboard UI
- [**Docker**](https://www.docker.com) — Container-based bench deployments
- [**Ansible**](https://www.ansible.com) — Server provisioning automation
- [**Cloudflare API**](https://developers.cloudflare.com/api/) — DNS record management
- [**Let's Encrypt**](https://letsencrypt.org/) — SSL certificates (with Cloudflare DNS-01 challenge)

## Key Files (Fork-Specific)

| File | Purpose |
|------|---------|
| `press/press/doctype/root_domain/root_domain.json` | Cloudflare API token field |
| `press/press/doctype/cluster/cluster.json` | Cloudflare zone ID field |
| `press/utils/selfhosted_utils.py` | Standalone deployment helpers |
| `press/utils/do_retry.py` | Retry logic for provisioning |
| `dashboard/src/components/AppSidebar*.vue` | Dark sidebar theme |
| `dashboard/src/pages/LoginBox.vue` | Branded login page |
| `dashboard/src/pages/SaaSLoginBox.vue` | Branded SaaS login |
| `dashboard/src/assets/style.css` | Global brand overrides |
| `SYNC_JOURNAL.md` | Fork sync history and decisions |

## License

Same as upstream — [GNU Affero General Public License v3.0](LICENSE)

---

<div align="center" style="padding-top: 0.75rem;">
	<a href="https://accuratesystems.com.sa" target="_blank">
		<strong>Accurate Systems</strong>
	</a>
	<br/>
	<sub>Cloud Hosting Solutions</sub>
</div>
