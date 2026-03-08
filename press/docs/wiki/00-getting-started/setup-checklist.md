# Setup Checklist

Complete checklist for deploying self-hosted Frappe Press from scratch.

## Prerequisites

- [ ] 2 Hetzner servers (or any VPS) with Ubuntu 22.04
- [ ] Domain with Cloudflare DNS
- [ ] SSH keys configured between servers
- [ ] GitHub account (for GitHub App integration)

## Server 1 (Press Controller)

- [ ] Install Frappe bench with Node 20.20+
- [ ] Install Press app: `bench get-app https://github.com/accurate-systems/press --branch cloudflare-dns`
- [ ] Create site: `bench new-site demo.mvpstorm.com`
- [ ] Install Press: `bench --site demo.mvpstorm.com install-app press`
- [ ] Run migrate: `bench --site demo.mvpstorm.com migrate` (creates 142+ scheduled jobs!)
- [ ] Setup production: `bench setup production frappe`
- [ ] Fix supervisor symlink if needed
- [ ] Pin setuptools: `env/bin/pip install "setuptools<81"` (razorpay dependency)
- [ ] Set `developer_mode = 1` in site_config.json (routes builds to default queue)

## SSL Certificates

- [ ] Install certbot + cloudflare plugin
- [ ] Obtain wildcard cert: `certbot certonly --dns-cloudflare -d '*.demo.mvpstorm.com'`
- [ ] Obtain root cert: `certbot certonly --dns-cloudflare -d demo.mvpstorm.com`
- [ ] Fix permissions: `chmod -R 755 /etc/letsencrypt/live/ /etc/letsencrypt/archive/`

## Server 2 (App Server)

- [ ] Run `setup_server()` from Press (installs agent, nginx, docker, etc.)
- [ ] Run `setup_standalone()` (configures standalone mode)
- [ ] Create dummy SSH CA key: `ssh-keygen -t ed25519 -f /tmp/ca_key -N ''`
- [ ] Install MariaDB server if not installed by Ansible
- [ ] Add Docker insecure registry: `"insecure-registries": ["89.167.116.92:5000"]`
- [ ] Fix agent config: set `press_url` to `https://demo.mvpstorm.com`

## Press Configuration

### DocType Records (create in this order)

1. [ ] **Root Domain**: `demo.mvpstorm.com` with Cloudflare token + zone ID
2. [ ] **Cluster**: "Default" — set `public = 1`
3. [ ] **Database Server**: `press-f1.demo.mvpstorm.com` — set `mariadb_root_password`
4. [ ] **Proxy Server**: `press-f1.demo.mvpstorm.com`
5. [ ] **Server**: `press-f1.demo.mvpstorm.com` — link to DB + Proxy, set `team`, `cluster`
6. [ ] **Frappe Version**: Ensure "Version 15" has `public = 1`
7. [ ] **App** + **App Source** + **App Release**: For each app (frappe, erpnext, etc.)
8. [ ] **Marketplace App**: For each app — set `frappe_approved = 1`
9. [ ] **Site Plan**: At least one plan (free or paid)
10. [ ] **Release Group**: Link apps + server
11. [ ] **Deploy Candidate**: Create and build

### Press Settings

- [ ] `domain`: demo.mvpstorm.com
- [ ] `cluster`: Default
- [ ] `docker_registry_url`: 89.167.116.92:5000
- [ ] `build_server`: press-f1.demo.mvpstorm.com
- [ ] `clone_directory`: /home/frappe/frappe-bench/clones
- [ ] `build_directory`: /home/frappe/frappe-bench/builds
- [ ] `default_apps`: frappe + erpnext
- [ ] `erpnext_apps`: erpnext, hrms, payments, webshop, lending
- [ ] `github_app_id` + `github_app_client_id` + `github_app_client_secret` + `github_app_private_key`
- [ ] `github_app_public_link`: https://github.com/apps/mvpstorm-press

### Dashboard Visibility (all required)

- [ ] App Source: `public = 1`, `frappe = 1`, `enabled = 1`
- [ ] Frappe Version: `public = 1`
- [ ] Cluster: `public = 1` (resets on save — re-check!)
- [ ] Marketplace App: `frappe_approved = 1`, `status = Published`
- [ ] Server: `team` = dashboard user's team hash
- [ ] All resources: `team` = dashboard user's team (not Administrator's)

### Agent Authentication

- [ ] Server `agent_password` in `__Auth` table matches agent's `access_token`
- [ ] Proxy Server `agent_password` ALSO matches (separate record, same physical agent)
- [ ] Agent `access_token` is pbkdf2-sha256 hash of the password
- [ ] Agent `press_url` = `https://demo.mvpstorm.com`

## Verification

- [ ] Dashboard login works at `/dashboard`
- [ ] "New Bench" shows Version 14 + 15
- [ ] Build completes (all steps Success)
- [ ] "New Site" creates site successfully
- [ ] Site status auto-updates (poll_pending_jobs running)
- [ ] Backups work (check Agent Job "Backup Site" → Success)
- [ ] GitHub "Add app" flow works (OAuth token saved)
