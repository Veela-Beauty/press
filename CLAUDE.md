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
| press-ctrl | 89.167.116.92 | Press controller, scheduler, Docker registry (301G disk) |
| press-f1 | 89.167.57.21 | App + Build server, standalone (150G disk) |
| u4 | 157.90.244.216 | App server, sandbox cluster (38G disk) |
| u5 | 46.224.170.58 | App server, Mohammed's team benches (38G disk) |

SSH aliases: `ssh press-ctrl`, `ssh press-f1`, `ssh u4`
SSH key: `E:/.ssh/new_id_ed25519` (all three servers)
u4 uses ProxyCommand through press-ctrl (ProxyJump not supported by Windows OpenSSH client):
`ProxyCommand ssh -i E:/.ssh/new_id_ed25519 -o StrictHostKeyChecking=no root@89.167.116.92 -W %h:%p`

**Push method (canonical):** push DIRECTLY from this Hetzner dev box — `git push origin cloudflare-dns`. The local `~/.ssh/id_ed25519` is a personal GitHub-write key (`elgogary`) registered on both `Veela-Beauty/press` and `accurate-systems/press` with write access. **Do NOT bundle through press-ctrl** — press-ctrl's keys are read-only deploy keys; pushing from there ALWAYS fails with "Permission denied to deploy key". Full workflow: `~/.claude/projects/-home-eslam/memory/PRESS-WORKFLOW.md`.

**Deploy method:** press-ctrl is for DEPLOYING (cherry-pick local commits onto its `apps/press` clone, `bench build` if Vue changed, restart web). Bundle → SCP → cherry-pick → restart. Never run `git push` from press-ctrl.

## Commands

```bash
# On press-ctrl
sudo -u frappe bash -c 'cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com console'
bench --site demo.mvpstorm.com migrate
bench --site demo.mvpstorm.com clear-cache
supervisorctl status
supervisorctl restart all

# Build Vue dashboard (REQUIRED for any change under apps/press/dashboard/src/)
# `bench build` does NOT compile the Vue SPA — it only handles Frappe assets.
# You MUST run `yarn build` from the dashboard/ directory.
sudo -u frappe bash -lc 'cd /home/frappe/frappe-bench/apps/press/dashboard && yarn build'
sudo -u frappe bash -lc 'cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com clear-cache'
supervisorctl restart frappe-bench-web:

# For pure Frappe asset changes (Python templates, CSS, etc.) — bench build IS sufficient
sudo -u frappe bash -lc 'cd /home/frappe/frappe-bench && bench build --app press && bench clear-cache'
supervisorctl restart frappe-bench-web:frappe-bench-frappe-web

# Safe update (REQUIRED for any Python/deps/migration change — never use bare `bench update`)
sudo -u frappe bench-update-safe              # full pipeline: preflight + update + postflight + safe restart + smoke + auto-rollback
sudo -u frappe bench-update-safe --dry-run    # preview only
sudo -u frappe bench-update-safe --skip-update --no-restart  # validate env health, no disruption
sudo -u frappe /home/frappe/scripts/rollback.sh             # emergency rollback to latest snapshot

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
9. `press/press/doctype/site/site.py` — `set_development_mode`: fix invalid Site Activity action
10. `press/press/doctype/bench/bench.py` — `is_development_bench` field + `set_development_bench()` + `restart_bench()`

## Custom Files Added

### Backend APIs (sibling files — avoids editing upstream 5000-line controllers)
- `press/press/doctype/bench/bench_dev_overview.py` — Dev Overview + git status + console + logs APIs
  - `get_dev_overview_benches()` — all benches with commit/build/site/gap data
  - `get_dev_panel_data(bench_name)` — per-bench panel (sites, commits, build history)
  - `get_app_git_status(bench_name, site_name)` — per-app git branch/dirty/ahead/remote
  - `get_bench_dev_info()` — server IP, SSH port, is_development_bench
  - `push_app_to_github()` — git commit + push from inside container
  - `run_sql_on_site()` / `run_python_on_site()` — inline console
  - `get_recent_logs()` / `get_db_processlist()` — log browser + process list
- `press/press/doctype/bench/bench_app_management.py` — Local app creation + GitHub push
  - `create_app_locally(bench_name, app_name, app_title)` — bench new-app inside container
  - `init_github_for_app(bench_name, app_name, github_owner)` — create repo + push + register
  - `get_github_accounts()` — list GitHub user + orgs for current team
- `press/press/doctype/deploy_candidate_build/build_diagnostics.py` — Deploy failure analysis
  - `get_failure_details(dn)` — failed step, stage, output, progress count
- `press/api/create_app.py` — Create New App (GitHub-first flow from bench Apps tab)
  - `create_app()` — scaffold + GitHub repo + push + register + auto-add to bench
  - `get_github_owners()` — GitHub account selector

### AI Governance Layer (`press/press/ai/`) — Press is governance only, Sanad AI is the engine
Architecture: Sanad AI (installed on dev/staging sites) handles chat, tools, providers, billing.
Press (on press-ctrl) enforces governance — scope guard, escalation, rollback triggers, policy.

- `press/press/ai/site_scope_guard.py` — dev/staging/prod enforcement before AI actions
- `press/press/ai/escalation.py` — 3-category escalation chain (hard block, approval, warning)
- `press/press/ai/policy.py` — policy acknowledgment gate + per-team AI rules
- `press/press/ai/rollback_trigger.py` — trigger rollback on target site via agent API
- `press/press/ai/tests/` — 41 unit tests (TDD)

Previously had 15 duplicate files (~2,585 lines) for linter, context injector, key storage, token budget,
gateway, provider, DB setup. All deleted — now handled by Sanad AI's `ai_dev` module.

### Dashboard Pages & Components
- `dashboard/src/pages/DevOverview.vue` — Watch Tower dashboard at `/dashboard/dev-overview`
- `dashboard/src/pages/DeployCandidate.vue` — Enhanced deploy build page (7 UX improvements)
- `dashboard/src/components/SiteDevTab.vue` — Dev tab with git status, console, logs, app management
- `dashboard/src/components/group/CreateAppDialog.vue` — Create New App dialog with GitHub selector

## Patterns & Lessons

- **Standalone API module**: Add whitelisted methods in sibling files, not inside upstream controllers.
- **`bool("0")` trap**: Site config values are strings. Use `value in (True, 1, "1", "true")`.
- **Site Activity action enum**: Fixed option list — use `frappe.logger()` for custom audit events.
- **Vue 3 `<template v-for>`**: Put `:key` on the `<template>` tag for group headers.
- **Syntax-check before deploy**: `python3 -c "import ast; ast.parse(open('file.py').read())"`.
- **docker_execute quirks**: Agent passes command to `docker exec` with `sh -c` but `$()` subshells expand on the HOST, not the container. Use `git -C` instead of `cd` + subshells. One command per docker_execute call is safest.
- **Deploy page blank screen**: frappe-ui document resources have `get.loading` not `.loading`. Always use `$resources.x?.get?.loading` with optional chaining.
- **press-f1 disk**: 75G was too small for build server (each image ~3-4G). Expanded to 150G. Daily cleanup cron at `/etc/cron.d/docker-cleanup`.
- **GitHub token security**: `Press Settings.github_access_token` is global admin token. Team members should use per-team tokens via GitHub App. On self-hosted, global fallback is OK for trusted teams.
- **bench update is dangerous** (see [stability runbook](docs/wiki/06-deployment-ops/press-ctrl-stability-runbook.md)): On 2026-04-29, a bare `bench update` upgraded `pydantic` but wiped `pydantic_core`, hidden for 10h until workers recycled → all Python processes FATAL. Always use `bench-update-safe` (auto pre-flight + boot test before restart + auto-rollback). Iron rules in `/etc/sanad/press-ctrl-rules.md` on the box.

## Stability Runbook

The Press-Ctrl Stability Runbook is the source of truth for safe operations on press-ctrl:

- **Wiki**: [docs/wiki/06-deployment-ops/press-ctrl-stability-runbook.md](docs/wiki/06-deployment-ops/press-ctrl-stability-runbook.md)
- **On the box**: `/etc/sanad/press-ctrl-rules.md` (abridged operator-facing rules)
- **Scripts**: `/home/frappe/scripts/{lib.sh, pre-flight.sh, post-flight.sh, rollback.sh, bench-update-safe}`
- **Snapshots**: `/home/frappe/snapshots/<context>-YYYYMMDD-HHMMSS.txt`

Five iron rules: (1) NEVER `sudo pip install`, (2) NEVER bare `bench update`, (3) updates only in maintenance window, (4) NEVER force-push `cloudflare-dns`, (5) take snapshots before destructive ops.

## Ops Wiki

`press/docs/wiki/` — full self-hosted operations wiki
- `lessons-learned.md` — 63 lessons with status audit
- `02-operations/platform-risk-checklist.md` — MANDATORY before/after every change

## Environment

Secrets are on the servers, not in this repo:
- `/root/.cloudflare/credentials.ini` — Cloudflare API token
- `/home/frappe/agent/config.json` — agent access_token (PBKDF2 hash)
- Press `__Auth` table — all agent_passwords (encrypted)
