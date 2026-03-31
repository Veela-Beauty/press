# Features Matrix — Accurate Systems Press Fork

All customizations and enhancements to the upstream `frappe/press` on the `cloudflare-dns` branch.

## Infrastructure & DNS

| Feature | Status | Files | Description |
|---------|--------|-------|-------------|
| Cloudflare DNS | Done | `utils/dns.py`, `root_domain.py`, `root_domain.json` | Replaces AWS Route53 with Cloudflare REST API |
| Cloudflare TLS | Done | `tls_certificate.py` | `certbot dns-cloudflare` for wildcard SSL |
| Standalone server mode | Done | `server.py`, provisioning scripts | Single server = Server + DB + Proxy |
| SSH proxy container | Done | Docker image on press-f1 | Auto-setup on new proxies + new benches |
| Hetzner VMs (no VPC) | Done | `virtual_machine.py` | Null guards for `vpc_id`, `security_group_id` |
| Docker registry (HTTP) | Done | `89.167.116.92:5000` | Local registry, all servers use `insecure-registries` |
| Post-provision hook | Done | `post_provision.py` | Auto-fixes 6 issues on new unified/standard servers |

## GitHub & Deploy Pipeline

| Feature | Status | Files | Description |
|---------|--------|-------|-------------|
| GitHub App webhook | Done | `github.py` (hook endpoint) | Real-time push notifications from GitHub → instant App Release |
| Webhook secret | Done | Press Settings | HMAC-SHA1 validation on incoming webhooks |
| Deploy marker `[deploy]` | Done | Press Settings | Commit-message triggered auto-deploy (opt-in per Release Group) |
| Public repo auto-detect | Done | `app_source.py` | `is_public_github_repo()` — auto-sets `public=1` on save |
| GitHub re-auth fix | Done | `app_source.py`, `github.py` | Reuses existing App Source installations when team OAuth token expires |
| Retry failed sources | Done | `app.py`, `hooks.py` | `retry_failed_releases()` every 30 min — retries `last_github_poll_failed=True` sources |
| Poll new releases | Upstream | `app.py`, `hooks.py` | Every 5 min, polls enabled App Sources for new commits (limit 300) |

## Dashboard & UI

| Feature | Status | Files | Description |
|---------|--------|-------|-------------|
| White-label rebrand | Done | Multiple dashboard `.vue` files | Accurate Systems branding, colors, logo |
| Dark sidebar | Done | CSS tokens | `#1E293B` sidebar, `#046BD2` primary blue |
| Login gradient | Done | Login page | `#046BD2 → #197972` gradient background |
| Site restore upload | Done | Dashboard + server | Direct/chunked upload, S3 fallback, progress tracking |
| Plans visibility fix | Done | `plans.py` | Show all plans for private bench sites |
| Stale dashboard cache fix | Done | nginx config | `no-cache` headers on `/dashboard` HTML |
| Cluster public flag guard | Done | `cluster.py` | Prevents `public` flag reset on save |

## Monitoring & Health

| Feature | Status | Files | Description |
|---------|--------|-------|-------------|
| Watch Tower module | Done | `frappe_theme_switcher` | 5 rules: stuck builds, failed deploys, stuck agent jobs, scheduler health, error spike |
| Daily health report | Done | scheduler hooks | CPU/RAM/disk, supervisor, Press scheduler, servers, sites, deploys, errors |
| Error log cleanup | Done | scheduler hooks | 7-day retention, noise filter (CSS/translation/cssutils) |
| Auto-archive broken benches | Done | `release_group.py` | Archives benches with no active sites + failed builds |

## Demo Data Engine

| Feature | Status | Files | Description |
|---------|--------|-------|-------------|
| Demo Data Set DocType | Done | `frappe_theme_switcher` | JSON payload storage, file import/export |
| Demo Data Session | Done | `frappe_theme_switcher` | Load/flush sessions with record tracking |
| App-safe dependency handling | Done | `engine.py`, `utils.py` | Skips DocTypes from uninstalled apps, cascade skip for dependencies |
| Time shift | Done | `utils.py` | Shifts all dates in payload by N days |
| Construction trading seed | Done | `demo_data/` | 162 records across 31 DocTypes for construction material trading company |

## Backup Integration (Daman Backup)

| Feature | Status | Files | Description |
|---------|--------|-------|-------------|
| daman_backup app | Done | Separate app | SFTP/SSH/Frappe Cloud backup management |
| Borgmatic auto-mount | Done | `mount.py` | SSHFS with key+password fallback |
| Frappe Cloud auto-setup | Done | `fc_setup.py` | Smart cycle: download → borg archive |

## Security & Auth

| Feature | Status | Files | Description |
|---------|--------|-------|-------------|
| Agent auth PBKDF2 | Upstream | Agent config | Press stores plaintext (encrypted), agent stores PBKDF2-SHA256 |
| Proxy upstream fallback | Done | proxy config | Falls back to public IP for Docker bench HTTP |
| Cross-server site routing | Done | proxy template | `hostnames;` directive fix for wildcard matching |

## Operational Scripts

| Script | Location | Purpose |
|--------|----------|---------|
| `provision-server.sh` | `scripts/` | Automate 13-step new server setup |
| `setup-build-worker.sh` | `scripts/` | Add dedicated build queue worker |
| `fix-letsencrypt-permissions.sh` | `scripts/hooks/` | Post-renewal chmod hook |
| `docker-cleanup.sh` | `scripts/hooks/` | Daily container prune |
| `sync-press-tls-records.sh` | `scripts/hooks/` | Sync cert expiry to Press DB |
| `fix_nginx_cache.py` | `scripts/` | Re-add no-cache headers after `bench setup nginx` |
| `do_retry.py` | `scripts/` | Retry failed agent jobs via bench execute |

## Patched Files Summary (vs upstream frappe/press)

| # | File | Patch Type |
|---|------|-----------|
| 1 | `press/utils/dns.py` | Cloudflare DNS API |
| 2 | `press/press/doctype/root_domain/root_domain.py` | Cloudflare headers |
| 3 | `press/press/doctype/root_domain/root_domain.json` | New cloudflare fields |
| 4 | `press/press/doctype/tls_certificate/tls_certificate.py` | certbot dns-cloudflare |
| 5 | `press/press/doctype/virtual_machine/virtual_machine.py` | Null guards for VPC |
| 6 | `press/press/doctype/server/server.py` | CA key in unified setup |
| 7 | `press/playbooks/roles/user_ssh_certificate/tasks/main.yml` | Accept ca_public_key var |
| 8 | `press/press/doctype/app_source/app_source.py` | Public repo detect + auth fallback |
| 9 | `press/api/github.py` | Re-auth fix + installation reuse |
| 10 | `press/press/doctype/app/app.py` | retry_failed_releases |
| 11 | `press/hooks.py` | Retry cron (*/30) |
| 12 | `press/press/doctype/app_release/app_release.py` | Python 3.14 fallback |
| 13 | `press/press/doctype/deploy_candidate/validations.py` | Warn instead of raise |
| 14 | `press/press/doctype/support_access/support_access.py` | Operator precedence fix |
| 15 | `press/press/doctype/cluster/cluster.py` | Preserve public flag |

## GitHub Update Flow

```
Push to GitHub
  │
  ├── Webhook path (instant)
  │   GitHub → POST /api/method/press.api.github.hook
  │   → HMAC verify → GitHubWebhookLog → App Release created
  │   → Dashboard shows new update immediately
  │   → User clicks Deploy when ready
  │
  ├── Poll path (every 5 min, fallback)
  │   Scheduler → poll_new_releases()
  │   → GET /repos/{owner}/{repo}/branches/{branch}
  │   → Compare hash → Create App Release if new
  │
  └── Retry path (every 30 min)
      Scheduler → retry_failed_releases()
      → Retries sources with last_github_poll_failed=True
      → Resets flag on success
```
