# CLAUDE-INDEX — Bench Access features (Team SSH + Option C GitHub)

**If you (a future Claude session) are asked to work on SSH / bench access / Dev tab / git-in-bench / GitHub auth, read these files FIRST — in this order.**

All paths are relative to the `press` repo root (`/home/frappe/frappe-bench/apps/press/`) unless prefixed with `memory://` (in which case the file is in the Claude memory directory at `/home/eslam/.claude/projects/-home-eslam/memory/`).

---

## Read first — context (cross-feature)

| # | File | Why |
|---|---|---|
| 1 | `memory://MEMORY.md` | Master memory index with SSH/Press context |
| 2 | `memory://press-ssh-agent-forwarding.md` | **Critical** — press-f1 agent + ssh-proxy patches + Option C cron + env file. Must be re-applied after agent `git pull`. |
| 3 | `memory://frappe-press-lessons.md` (lessons 110–114) | What broke historically and why |
| 4 | `docs/srs/2026-04-22-team-ssh-management.md` | SRS for **feature 1** (team SSH key management) |
| 5 | `docs/srs/2026-04-22-option-c-github-app-user-tokens.md` | SRS for **feature 2** (per-user GitHub OAuth — Option C) |
| 6 | `docs/wiki/01-backend-development/team-ssh-management.md` | Wiki: feature 1 architecture |
| 7 | `docs/wiki/03-integrations/github-app-user-tokens.md` | Wiki: feature 2 architecture + operations + troubleshooting |
| 8 | `docs/plans/2026-04-22-team-ssh-test-plan.md` | 17-scenario test plan for feature 1 |
| 9 | `docs/team-onboarding-github.md` | User-facing 3-step guide (share with team) |

---

## Feature 1 — Team SSH key management

### Backend files

| File | Purpose |
|---|---|
| `press/press/doctype/user_ssh_key/user_ssh_key.json` | Doctype — includes `label`, `is_disabled`, `disabled_by`, `disabled_on` |
| `press/press/doctype/release_group/release_group.py` | `generate_certificate(ssh_key_name=None)` + `get_certificate(ssh_key_name=None)` |
| `press/api/account.py` | 4 admin APIs after `get_user_ssh_keys()`: `get_team_ssh_keys`, `set_team_ssh_key_disabled`, `remove_team_ssh_key`, `set_ssh_key_label` + `_require_team_owner` helper |
| `press/auth.py` | `ALLOWED_WILDCARD_PATHS` — 3 dev-tab module prefixes whitelisted |
| `press/press/doctype/bench/bench_dev_overview.py` | Dev tab APIs + `_ensure_team_access()` helper |
| `press/press/doctype/bench/bench_app_management.py` | Push-to-GitHub / create-app APIs + same `_ensure_team_access()` helper |
| `press/overrides.py` | `has_permission()` — the team-scoped permission hook |

### Frontend files

| File | Purpose |
|---|---|
| `dashboard/src/components/SiteDevTab.vue` | Site Dev tab — Launch Code Server / Setup SSH Key / Local VS Code buttons |
| `dashboard/src/components/group/SSHCertificateDialog.vue` | SSH Access dialog — cert flow + key selector + `ssh -A` + agent forwarding tip |
| `dashboard/src/components/settings/TeamSSHAccess.vue` | Team SSH admin table (owner only) |
| `dashboard/src/pages/Settings.vue` | Tabs — "Team SSH" visible only to team owner |
| `dashboard/src/router.js` | Route `SettingsTeamSSH` |

---

## Feature 2 — Option C: Per-user GitHub OAuth (in-bench git)

### Backend files

| File | Purpose |
|---|---|
| `press/press/doctype/user_github_auth/user_github_auth.json` | Doctype — per-user GitHub tokens (encrypted via Password field) |
| `press/press/doctype/user_github_auth/user_github_auth.py` | Controller — `refresh_access_token` (cache-locked), `revoke_on_github`, `get_fresh_access_token`, `GitHubAppCredentials.load()` dataclass, `get_or_create_for_user`, `get_for_user` |
| `press/press/doctype/user_github_auth/test_user_github_auth.py` | **4 unit tests**: refresh auto-revoke on 401, auto-revoke on `bad_refresh_token`, happy-path refresh, revoked guard |
| `press/press/doctype/git_credential_session_log/git_credential_session_log.json` | Audit doctype — one row per token mint |
| `press/press/doctype/git_credential_session_log/git_credential_session_log.py` | `log_credential_request` (fire-and-forget) + `prune_old_git_credential_logs` (daily scheduled job, 90-day retention) |
| `press/api/github_auth.py` | **4 endpoints**: `start_connect`, `disconnect`, `get_status`, `handle_user_auth_callback` (called from authorize.py); `_exchange_and_persist` helper; `CallbackResult` TypedDict |
| `press/api/git_credentials.py` | **Security-critical** — `get_for_session` endpoint called by bench-git-setup; `_require_internal_secret` + `_validate_team_membership` helpers |
| `press/api/tests/test_github_auth.py` | **6 tests**: OAuth URL shape, happy path, expired nonce, missing state, bad access_token, full callback path |
| `press/api/tests/test_git_credentials.py` | **4 security tests**: team owner passes, team member passes, outsider rejected, unknown bench rejected |
| `press/www/github/authorize.py` | OAuth callback page — routes by `state.flow`; narrow-except + `frappe.log_error` on malformed state |
| `press/press/doctype/press_settings/press_settings.json` | Added field `bench_internal_auth_secret` (Password, encrypted) |
| `press/docker/config/bench-git-setup` | Shell script baked into bench Docker image (prompts email, fetches token, configures git) |
| `press/docker/Dockerfile` | COPY `bench-git-setup` → `/usr/local/bin/` |
| `press/hooks.py` | `scheduler_events.daily` registers `prune_old_git_credential_logs` |

### Frontend files

| File | Purpose |
|---|---|
| `dashboard/src/components/settings/DeveloperSettings.vue` | "GitHub Connection" section with Connect/Disconnect buttons + OAuth callback query-param handler |

### Out-of-band infrastructure (press-f1 host, outside the repo)

| Path | Purpose |
|---|---|
| `/etc/press/bench-env.source` | Authoritative `PRESS_API_URL` + `PRESS_INTERNAL_TOKEN` (0600 root) |
| `/etc/press/bench-git-setup` | Fallback copy of the shell script (for containers built before Dockerfile patch) |
| `/usr/local/bin/sync-bench-env.sh` | Cron-run script: every 2 min, injects env + script into any running bench container missing them |
| Crontab: `*/2 * * * * /usr/local/bin/sync-bench-env.sh` | Triggers the sync |
| `/var/log/sync-bench-env.log` | Trimmed to last 5000 lines |
| `/home/frappe/agent/repo/agent/ssh.py` | Patched to generate principals with `pty,agent-forwarding` + `ssh -A` for forwarding (see `press-ssh-agent-forwarding.md`) |

### GitHub App

- App handle: `mvpstorm-deploy` — https://github.com/apps/mvpstorm-deploy
- Installation IDs: Veela-Beauty=`114894173`, accurate-systems=`114895817`, elgogary=`114979006`
- `client_id`: `Iv23liVsf63hgRg9ZSqw` (stored in Press Settings)
- Callback URL registered: `<press-url>/github/authorize`
- Private key + secrets: Press Settings

---

## How to resume work on this feature

1. Read items 1–9 from "Read first" above.
2. Run the tests: `bench --site demo.mvpstorm.com run-tests --app press --module press.api.tests.test_github_auth --module press.api.tests.test_git_credentials --module press.press.doctype.user_github_auth.test_user_github_auth` — all 14 should pass.
3. Check recent git log: `cd /home/frappe/frappe-bench/apps/press && git log --oneline -20` on press-ctrl.

### Diagnostic decision tree

| Symptom | Likely cause | Where to look |
|---|---|---|
| "Press API config missing" in bench-git-setup | `/etc/press/bench-env` missing from container | `ssh press-f1 "tail -20 /var/log/sync-bench-env.log"` — should run every 2 min |
| "redirect_uri is not associated with this application" on Connect GitHub | GitHub App callback URL mismatch | Should be `<press-url>/github/authorize` |
| "Incorrect datetime value" on OAuth callback | timezone-aware datetime hitting MariaDB | Should use `frappe.utils.now_datetime()` (naive UTC) — lesson 114 |
| Team member can't see Dev tab / "Access not allowed for this URL" | `_ensure_team_access()` or `ALLOWED_WILDCARD_PATHS` misconfig | `press/auth.py` + `press/press/doctype/bench/bench_dev_overview.py` |
| `git pull` fails with `Permission denied (publickey)` | Old cert / wrong bench name / agent not forwarded | Check memory `press-ssh-agent-forwarding.md` — `restrict,pty` vs `pty,agent-forwarding` in principals |
| "GitHub not connected" banner inside bench | User hasn't clicked Connect GitHub in Settings → Developer, OR tokens revoked | `SELECT user, github_username, is_revoked FROM \`tabUser GitHub Auth\`` |
| `A valid certificate already exists` error | Frontend calling `.fetch()` instead of `.submit()` on whitelisted methods | `SSHCertificateDialog.vue` — lesson 113 |
| Team SSH tab missing for owner | `Settings.vue` condition `$team.doc?.user === $session.user` — team owner != System Manager | Verify session user is the Team's `user` field |
| Bench sshd refuses agent forwarding | `AllowAgentForwarding no` in `/home/frappe/frappe-bench/config/ssh/sshd_config` | Fixed in Docker template (lesson 114); cron re-fixes running containers |

### Common gotchas

- **Python file changes need worker restart**: `supervisorctl restart frappe-bench-workers: frappe-bench-web:`
- **Dashboard changes need build**: `cd dashboard && npm run build` (no restart after)
- **Frappe `run_doc_method` needs `.submit()` not `.fetch()`** for whitelisted methods with params
- **`@dashboard_whitelist()` has no extra auth** — the real auth is in `press/auth.py` allowlist
- **`X-Press-Team` header** from `localStorage.current_team` can be stale after user switch
- **Password fields are encrypted** — always `get_password()` / `get_decrypted_password()` to read; `doc.field = val` to write (not raw SQL)
- **Datetime columns are timezone-naive in MariaDB** — use `frappe.utils.now_datetime()` everywhere, NOT `datetime.now(timezone.utc)`

---

## Commit history (chronological)

```
# Feature 1 — Team SSH key management
6f8b039edf  fix(dev-tab): fix Web VS Code fallback + Local VS Code SSH state
9e45fdce22  fix(dev-tab): allow Code Server launch on all benches, fix SSH key URL
97fd1b5c6c  feat(ssh): team SSH key management — labels, disable, admin control
b80e223fb6  fix(dev-tab): allow team members access to Dev tab APIs
afe3171e04  feat(ssh): enable SSH agent forwarding for in-bench git access
7761de561a  fix(ssh): enable AllowAgentForwarding in bench container sshd
d4dd899ef4  docs(team-ssh): full SRS + wiki + test plan + CLAUDE-INDEX

# Feature 2 — Option C Per-user GitHub OAuth
3fdc64a25b  docs(srs): Option C plan — git-in-bench via GitHub App user-to-server tokens
112bf3a425  feat(github-auth): Option C Day 1+2 — per-user GitHub App OAuth + bench git credentials
1ea0b09998  fix(github-auth): reuse registered /github/authorize callback URI
1cfad50743  feat(docker): bake bench-git-setup into Press bench Docker image (Option C T11)
4ec5100f78  fix(github-auth): use frappe.utils.now_datetime() for DB-compatible naive UTC
6e6ac5a7a3  refactor(github-auth): code-review fixes (12 items + 14 tests)
```

---

**Last updated:** 2026-04-22 — Option C shipped with 14 unit tests; code-review fixes applied; wiki + SRS + onboarding docs in place.


---

## Feature 3 — Code Server on bench Actions tab

**Entry point:** Bench group `/dashboard/groups/<bench>/actions` → Dev Actions section → per-bench "Launch Code Server" button.

### Commits



### Files

| File | Purpose |
|---|---|
| `dashboard/src/components/group/ReleaseGroupActions.vue` | UI — per-bench Launch/Starting/Open button + password copy |
| `press/press/doctype/bench/bench_dev_overview.py` (`setup_code_server`) | Backend — direct DB write of flag + bench_config JSON, manual Agent.update_bench_config call, archive-stale-docs cleanup |

### Known limitation (unfixed)

Benches built with `is_code_server_enabled=False` on the Deploy Candidate have NO code-server binary in their Docker image — the Dockerfile at line 138-140 gates the install on that flag. Manual runtime install via `docker exec -u root <bench> bash -c "curl -fsSL https://code-server.dev/install.sh | sh"`. See lesson 116.

### Diagnostic decision tree (Code Server)

| Symptom | Cause | Fix |
|---|---|---|
| Launch Code Server → "Code Server not enabled for the selected Bench" (validate error) | bench.save() silently reset `is_code_server_enabled` back to 0 | Use `frappe.db.set_value` + manual agent job; see lesson 115 |
| "supervisorctl start code-server: exit 2" (program not found) | supervisor.conf not regenerated; `is_code_server_enabled` not in bench_config JSON | Queue Update Bench Configuration agent job first |
| "supervisorctl start code-server: exit 1" (program found, fails on start) | code-server binary not installed in container | Install via `docker exec curl` or rebuild image; see lesson 116 |
| "Code Server xxx already exists" | Archived doc with same deterministic name blocks new create | `frappe.delete_doc("Code Server", name, force=True)` before insert; see lesson 117 |
| "TypeError: RedisWrapper.set_value() got an unexpected keyword argument 'nx'" | Cache lock using unsupported kwarg | Use raw Redis connection `frappe.cache()._conn.set(nx=True)`; see lesson 118 |
| "Incorrect datetime value: ...+00:00" on DB write | Timezone-aware datetime rejected by MariaDB | Use `frappe.utils.now_datetime()`; see lesson 119 |
| Password field reads back as None after write | Wrote via `db.set_single_value` (skips encryption) | Write via `doc.save()`; see lesson 120 |

### Lessons in memory (this feature)

- memory://frappe-press-lessons.md lessons **115-120** (bench.save reset, Dockerfile gate, autoname collisions, RedisWrapper limits, timezone, Password field encryption)
