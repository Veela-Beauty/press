# Session changelog — 2026-04-22 / 2026-04-23

Bench access features: per-user GitHub OAuth (Option C) + Code Server UX + Team SSH management.
All commits on `cloudflare-dns` branch at `accurate-systems/press`.

---

## Commits in order

### Team SSH key management (earlier in session)

| Hash | Subject |
|------|---------|
| `6f8b039edf` | fix(dev-tab): fix Web VS Code fallback + Local VS Code SSH state |
| `9e45fdce22` | fix(dev-tab): allow Code Server launch on all benches, fix SSH key URL |
| `97fd1b5c6c` | feat(ssh): team SSH key management — labels, disable, admin control |
| `b80e223fb6` | fix(dev-tab): allow team members access to Dev tab APIs |
| `afe3171e04` | feat(ssh): enable SSH agent forwarding for in-bench git access |
| `7761de561a` | fix(ssh): enable AllowAgentForwarding in bench container sshd |
| `d4dd899ef4` | docs(team-ssh): full SRS + wiki + test plan + CLAUDE-INDEX |

### Option C — Per-user GitHub OAuth for in-bench git

| Hash | Subject |
|------|---------|
| `3fdc64a25b` | docs(srs): Option C plan — git-in-bench via GitHub App user-to-server tokens |
| `112bf3a425` | feat(github-auth): Option C Day 1+2 — per-user OAuth + bench git credentials |
| `1ea0b09998` | fix(github-auth): reuse registered /github/authorize callback URI |
| `1cfad50743` | feat(docker): bake bench-git-setup into Press bench Docker image |
| `4ec5100f78` | fix(github-auth): use frappe.utils.now_datetime() for DB-compatible naive UTC |
| `6e6ac5a7a3` | refactor(github-auth): code-review fixes (Arch/Code/Perf/Tests batches) |
| `784f7911ee` | docs(option-c): wiki page, CLAUDE-INDEX, team onboarding, broadcast (T21-T27) |
| `9d3ee883ac` | fix(github-auth): remove broken cache lock in refresh_access_token |

### Code Server on bench Actions

| Hash | Subject |
|------|---------|
| `8f509a26ac` | feat(dev-tab): per-bench Launch Code Server button on Release Group Actions |
| `daa805e618` | fix(dev-tab): auto-enable is_code_server_enabled in setup_code_server |
| `f20a855376` | fix(code-server): supervisor.conf regens when flag flips + show password in UI |
| `4362ae4671` | fix(code-server): sync flag into bench_config JSON + queue agent job |

---

## What shipped

### Backend

| File | What |
|---|---|
| `press/api/github_auth.py` | OAuth connect / disconnect / status endpoints; `handle_user_auth_callback` + shared `_exchange_and_persist` helper |
| `press/api/git_credentials.py` | Bench-facing `get_for_session` endpoint; internal-secret auth + team-membership guard |
| `press/api/account.py` | +4 admin APIs: `get_team_ssh_keys`, `set_team_ssh_key_disabled`, `remove_team_ssh_key`, `set_ssh_key_label` |
| `press/auth.py` | `ALLOWED_WILDCARD_PATHS` includes 3 new dev-tab module prefixes |
| `press/press/doctype/user_ssh_key/user_ssh_key.json` | +4 fields: `label`, `is_disabled`, `disabled_by`, `disabled_on` |
| `press/press/doctype/user_github_auth/` | New doctype + controller (refresh, revoke, mark_used, mark_revoked, get_fresh_access_token, `GitHubAppCredentials` dataclass) + 4 unit tests |
| `press/press/doctype/git_credential_session_log/` | New audit doctype + daily prune (90-day retention) |
| `press/press/doctype/press_settings/press_settings.json` | +1 field: `bench_internal_auth_secret` (Password/encrypted) |
| `press/press/doctype/bench/bench_dev_overview.py` | `_ensure_team_access()` helper replaces `frappe.only_for("System Manager")` on 14 methods; `setup_code_server` auto-enables flag + queues agent job; `get_bench_dev_info` exposes `has_ssh_key` + `release_group` |
| `press/press/doctype/bench/bench_app_management.py` | Same `_ensure_team_access()` pattern |
| `press/press/doctype/release_group/release_group.py` | `generate_certificate(ssh_key_name=None)` + `get_certificate(ssh_key_name=None)` |
| `press/www/github/authorize.py` | OAuth callback routes by `state.flow`; narrow except + `frappe.log_error` on malformed state |
| `press/docker/Dockerfile` | COPY `bench-git-setup` into bench image `/usr/local/bin/` |
| `press/docker/config/bench-git-setup` | Shell script that prompts email, fetches token, configures git |
| `press/docker/config/ssh/sshd_config` | `AllowAgentForwarding yes` |
| `press/hooks.py` | Daily scheduler entry for `prune_old_git_credential_logs` |

### Frontend

| File | What |
|---|---|
| `dashboard/src/components/SiteDevTab.vue` | Setup SSH Key button + Local VS Code link + Launch Code Server button; `-A` in SSH command |
| `dashboard/src/components/group/SSHCertificateDialog.vue` | Key selector with labels + disabled state; `-A` default |
| `dashboard/src/components/group/ReleaseGroupActions.vue` | **NEW**: per-bench Launch/Open Code Server button + password copy |
| `dashboard/src/components/settings/TeamSSHAccess.vue` | **NEW**: owner-only admin table |
| `dashboard/src/components/settings/DeveloperSettings.vue` | **NEW**: GitHub Connection section |
| `dashboard/src/pages/Settings.vue` | +Team SSH tab (owner-only) |
| `dashboard/src/router.js` | +route `SettingsTeamSSH` |

### Unit tests — 14 passing

| File | Tests |
|---|---|
| `press/press/doctype/user_github_auth/test_user_github_auth.py` | 4 — refresh auto-revoke on 401/bad_refresh_token/happy-path/revoked guard |
| `press/api/tests/test_github_auth.py` | 6 — URL shape, happy path, expired nonce, missing state, missing access_token, full cache callback |
| `press/api/tests/test_git_credentials.py` | 4 — team owner pass, team member pass, outsider reject, unknown bench reject |

### Out-of-band on press-f1 (host-level, outside the repo)

| Path | Purpose |
|---|---|
| `/home/frappe/agent/repo/agent/ssh.py` | PATCHED: SSH proxy principals use `pty,agent-forwarding` + `ssh -A` (was `restrict,pty`) |
| `/etc/press/bench-env.source` | Authoritative `PRESS_INTERNAL_TOKEN` + `PRESS_API_URL` (0600 root) |
| `/usr/local/bin/sync-bench-env.sh` | Cron: every 2 min, `docker cp`s env file + script into any running bench container missing them |
| `/etc/press/bench-git-setup` | Fallback copy for images predating the Dockerfile patch |
| crontab: `*/2 * * * * /usr/local/bin/sync-bench-env.sh` | Triggers the sync |
| `/var/log/sync-bench-env.log` | Trimmed to 5000 lines |

---

## Docs created this session

| Path | Purpose |
|---|---|
| `docs/srs/2026-04-22-team-ssh-management.md` | SRS — team SSH feature |
| `docs/srs/2026-04-22-option-c-github-app-user-tokens.md` | SRS — Option C feature |
| `docs/srs/CLAUDE-INDEX.md` | Entry point for future Claude sessions |
| `docs/wiki/01-backend-development/team-ssh-management.md` | Wiki — Team SSH architecture |
| `docs/wiki/03-integrations/github-app-user-tokens.md` | Wiki — Option C architecture + ops + troubleshooting |
| `docs/plans/2026-04-22-team-ssh-test-plan.md` | 17-scenario test plan |
| `docs/team-onboarding-github.md` | 3-step user-facing guide |
| `docs/team-onboarding-github-broadcast.md` | Slack-ready announcements |
| `memory://frappe-press-lessons.md` (lessons 110-120) | 11 new lessons from this session |
| `memory://press-ssh-agent-forwarding.md` (Option C section) | Out-of-band server-side patches |
| `memory://MEMORY.md` | Updated with `docs/srs/CLAUDE-INDEX.md` resume point |

---

## Known issues / follow-ups

- **Code-server binary missing in old bench images** (lesson 116). Existing benches built with `is_code_server_enabled=False` need either (a) a manual runtime install via `docker exec curl https://code-server.dev/install.sh`, (b) a full rebuild with flag set, or (c) a new agent step that installs on first Launch. **Proper fix: (c)**, not shipped.
- **Playwright tests for Connect GitHub flow** (SRS T18) — deferred.
- **Proper SETNX cache lock on token refresh** (lesson 118) — uses `frappe.cache()._conn.set(key, val, nx=True, ex=30)`. Follow-up; current state is bounded idempotent thundering herd.
- **HMAC challenge auth** for bench-internal calls (lesson 115 of review: shared-secret blast radius) — deferred.
- **Admin view: "GitHub Connected" column + auto-revoke-on-team-removal** (T15-T17) — not shipped.
- **`bench.save()` silently reverts `is_code_server_enabled`** (lesson 115) — worked around; root cause in Press validate chain not identified.

---

## Verified end-to-end (via Playwright on `demo.mvpstorm.com`)

1. **Option C OAuth:** User clicks Connect GitHub → authorize → redirects to dashboard with success panel → `User GitHub Auth` row created with encrypted tokens → `get_for_session` API returns valid `ghu_...` token → token authenticates against github.com as the real user → token can read Veela-Beauty/prime_textile (pull=True, push=False — matches user's real GitHub perms).
2. **Code Server provisioning:** Click Launch Code Server → "Update Bench Configuration" → "Add Code Server to Upstream" → "Setup Code Server" all Success → status=Running → UI shows ✓ Open Code Server + password copy → clicking the link loads `https://code-bench-...sandbox.mvpstorm.com/` with "Welcome to code-server" login page.

---

**Session owner:** `elgogary` / eng.elgogary@gmail.com
**Pushed to:** `accurate-systems/press` branch `cloudflare-dns`
**HEAD:** `4362ae4671`