# GitHub App User-to-Server Tokens (Option C)

Per-user GitHub OAuth integration for in-bench git operations. Each team member clicks **Connect GitHub** once in Press Settings; afterwards, `git pull` and `git push` inside any of their benches work with their own GitHub identity. No long-lived secrets are stored on any server.

**Shipped:** commits `112bf3a425` → `6e6ac5a7a3` on `cloudflare-dns` (2026-04-22).
**SRS:** `docs/srs/2026-04-22-option-c-github-app-user-tokens.md`
**Test plan:** 14 automated unit tests (`bench run-tests --app press --module press.api.tests.test_github_auth --module press.api.tests.test_git_credentials --module press.press.doctype.user_github_auth.test_user_github_auth`)

---

## User-facing flow

```
┌──────────────┐   ┌──────────────────────────┐   ┌──────────────────────────┐
│ 1. Team owner│   │ 2. Member clicks Connect │   │ 3. Member SSHs into any  │
│    installs  │──►│    GitHub in Settings    │──►│    bench, runs           │
│    Press App │   │    → Developer           │   │    bench-git-setup       │
│    on GitHub │   │    → redirected to       │   │    → types their email   │
│    org (done)│   │    github.com authorize  │   │    → git works           │
└──────────────┘   └──────────────────────────┘   └──────────────────────────┘
```

No developer ever copies a token, pastes a PAT, generates an SSH key, or edits any config file. The three-step setup lives entirely in the dashboard + the bench shell.

---

## Architecture

### Components

| Component | Where | Purpose |
|---|---|---|
| **GitHub App** `mvpstorm-deploy` | `github.com/apps/mvpstorm-deploy` | Pre-installed on `Veela-Beauty` (installation `114894173`). Provides client_id + private key. |
| **User GitHub Auth** doctype | Press DB | One row per developer who clicked Connect. Stores `access_token` + `refresh_token` (encrypted via Frappe's `Password` field). |
| **Git Credential Session Log** doctype | Press DB | Audit log — every token mint by every developer on every bench. Pruned to 90 days by daily scheduled job. |
| `press/api/github_auth.py` | Press backend | OAuth connect/disconnect/status endpoints. |
| `press/api/git_credentials.py` | Press backend | The bench-facing endpoint that mints short-lived tokens. Auth via shared secret + team-membership check. |
| `press/www/github/authorize.py` | Press web | OAuth callback page (reused — already registered with the App). Routes by `state.flow`. |
| `bench-git-setup` shell script | Every bench container at `/usr/local/bin/` | Runs on demand; fetches a fresh token from Press and configures git. |
| `sync-bench-env.sh` cron | press-f1 host | Every 2 min, pushes `/etc/press/bench-env` (contains `PRESS_API_URL` + `PRESS_INTERNAL_TOKEN`) into any running bench container that doesn't have it. |

### Per-SSH-session sequence

```
Developer's laptop                       press-f1 bench container        Press-ctrl                    GitHub.com
────────────────────                     ─────────────────────────       ──────────                    ──────────
ssh -A bench-X@proxy ──────────────────► bench-git-setup
                                              │
                                              │  read /etc/press/bench-env
                                              │  (PRESS_API_URL, PRESS_INTERNAL_TOKEN)
                                              │
                                              │  prompt user for email ───────► (first time per session)
                                              │
                                              │  POST /api/method/press.api.git_credentials.get_for_session
                                              │     X-Press-Internal-Token: <secret>
                                              │     X-Press-User: mahmoud@team.com
                                              │     X-Press-Bench: bench-0011-000054-press-f1
                                              │  ────────────────────────────────►  _require_internal_secret()
                                              │                                      _validate_team_membership()
                                              │                                      get_for_user()
                                              │                                         └─► needs_refresh()?
                                              │                                             └─► Yes ─► refresh_access_token()
                                              │                                                 (Frappe cache lock: only one
                                              │                                                  refresh per user at a time)
                                              │                                                       │
                                              │                                                       │  POST /login/oauth/access_token
                                              │                                                       │  grant_type=refresh_token
                                              │                                                       │ ──────────────►  new access_token
                                              │                                                       │              (8h lifetime)
                                              │                                                       │ ◄──────────────
                                              │                                                       │
                                              │                                      log_credential_request()
                                              │                                      mark_used()
                                              │  ◄────────────────────────────────  { "github.com": "gho_…", expires_in: 28800 }
                                              │
                                              │  write /dev/shm/git-creds-<tty> (0600)
                                              │  git config --global credential.helper "store --file=…"
                                              │  git config --global user.email mahmoud@team.com
                                              │  git config --global user.name "Mahmoud Ahmed"
                                              │
                                              │  "✓ Git configured as MahmoudAhmed2003 — valid ~480 min"
                                              │
                                         frappe@bench$ git pull
                                                     └─► reads /dev/shm/git-creds-<tty>
                                                         uses token ─────────────────────────────────────►  git fetch …
                                                                                                           commits attributed
                                                                                                           to mahmoud@team.com
```

### Security model

| Asset | Where it lives | Protection |
|---|---|---|
| GitHub App private key | Press Settings (`github_app_private_key`) encrypted | Frappe field encryption + site-local key |
| Per-user `access_token` | `User GitHub Auth.access_token` (Password field) | Encrypted at rest; never logged; lifetime 8 h; cache-lock prevents concurrent refresh |
| Per-user `refresh_token` | `User GitHub Auth.refresh_token` (Password field) | Encrypted at rest; 6-month lifetime; auto-revoked on GitHub's `bad_refresh_token` or HTTP 401 response |
| `PRESS_INTERNAL_TOKEN` (shared secret) | `Press Settings.bench_internal_auth_secret` (Password field) + `/etc/press/bench-env` on press-f1 (0600 root) + every bench container's `/etc/press/bench-env` | 64-char random; rotatable — see Operations section below |
| Token **in-flight** (bench) | `/dev/shm/git-creds-<ssh-tty>` (tmpfs, 0600, owned by frappe user) | RAM-only; wiped on SSH logout via `~/.bash_logout` hook; separate file per SSH session |
| OAuth CSRF state | Frappe cache (`github_oauth_state:<nonce>`) | 10-min TTL; single-use — consumed on first callback |
| Team membership enforcement | `press/api/git_credentials.py:_validate_team_membership` | Security-critical boundary, covered by 4 tests; rejects PermissionError on outsider + unknown-bench |

### Revocation paths

| Triggered by | Effect |
|---|---|
| User clicks **Disconnect** in Settings → Developer | Press calls GitHub `DELETE /applications/{client_id}/grant` → tokens invalidated server-side; Press row marked `is_revoked=1` with `revoked_on` timestamp. |
| GitHub returns `bad_refresh_token` / HTTP 401 on refresh | `refresh_access_token` auto-marks record revoked; next SSH session shows "needs_connect" banner. |
| Team owner disables a member in Press | Pending enhancement (T15-T17) — will auto-call `disconnect()` via a Frappe hook. |
| GitHub org admin removes the App installation | All user-to-server tokens from that installation immediately invalid; next refresh returns `bad_refresh_token` → auto-revoke as above. |
| Press Settings secret rotated | Old `/etc/press/bench-env` stops authenticating within 2 min (next cron pass pushes the new secret to all containers). |

---

## Operations

### Rotating `PRESS_INTERNAL_TOKEN`

1. In Press desk (or via bench console), set a new value on **Press Settings → `bench_internal_auth_secret`** (Password field; Frappe will re-encrypt).
2. On press-f1:
   ```bash
   SECRET=$(ssh press-ctrl "su - frappe -c \"cd /home/frappe/frappe-bench && bench --site demo.mvpstorm.com console\"" <<'EOF' 2>&1 | grep -oP '(?<=TOKEN:)[^[:space:]]+'
   import frappe
   from frappe.utils.password import get_decrypted_password
   print('TOKEN:' + get_decrypted_password('Press Settings', 'Press Settings', 'bench_internal_auth_secret'))
   exit
   EOF
   )
   cat > /etc/press/bench-env.source <<ENV
   PRESS_API_URL=https://autodeploypanel.mvpstorm.com
   PRESS_INTERNAL_TOKEN=$SECRET
   ENV
   chmod 0600 /etc/press/bench-env.source
   ```
3. Wait ≤ 2 min for the `sync-bench-env.sh` cron to propagate, OR run it manually: `/usr/local/bin/sync-bench-env.sh`.
4. Verify a sample container: `docker exec -u frappe <bench> bash -c 'source /etc/press/bench-env && echo ${#PRESS_INTERNAL_TOKEN}'` should print `64`.

### Adding a new app server (e.g., press-f2)

Three commands on the new host (after SSH is set up):
```bash
# 1. Copy the source env (same secret value) + the sync script from press-f1
scp press-f1:/etc/press/bench-env.source /etc/press/bench-env.source
scp press-f1:/usr/local/bin/sync-bench-env.sh /usr/local/bin/sync-bench-env.sh
scp press-f1:/etc/press/bench-git-setup /etc/press/bench-git-setup

# 2. Add cron
echo "*/2 * * * * /usr/local/bin/sync-bench-env.sh" | crontab -

# 3. Seed now
/usr/local/bin/sync-bench-env.sh
```

### Rebuilding the bench Docker image

`press/docker/Dockerfile` now COPYs `press/docker/config/bench-git-setup` into `/usr/local/bin/`. New bench images ship with the script pre-baked — no need for the fallback `docker cp` path from the cron.

### Pruning the audit log

Automatic: `scheduler_events.daily` runs `press.press.doctype.git_credential_session_log.git_credential_session_log.prune_old_git_credential_logs`. Keeps the last 90 days (`LOG_RETENTION_DAYS = 90`).

Manual: `bench --site <site> execute press.press.doctype.git_credential_session_log.git_credential_session_log.prune_old_git_credential_logs`.

### Observability

| Signal | Where |
|---|---|
| Every token mint | `Git Credential Session Log` doctype (user, bench, timestamp, success, error_message). Browseable at `/app/git-credential-session-log`. |
| OAuth failures | Frappe Error Log — search for titles starting with "GitHub OAuth" / "GitHub token refresh" / "Malformed GitHub OAuth state" |
| Cron sync activity | `/var/log/sync-bench-env.log` on press-f1 (auto-trimmed to last 5000 lines) |
| Token refresh timeouts | Frappe Error Log — title "GitHub token refresh timed out" |

---

## Troubleshooting

### "Press API config missing" banner on SSH login

`/etc/press/bench-env` not present in this container. Causes:
- Container spawned in the last 2 min (wait for next cron pass) OR
- `sync-bench-env.sh` cron not running. Check: `ssh press-f1 "tail -20 /var/log/sync-bench-env.log"`.

Immediate fix: `ssh press-f1 "/usr/local/bin/sync-bench-env.sh"`.

### User sees "GitHub not connected" banner

The user's email wasn't in `User GitHub Auth` (or was revoked). They should:
1. Go to `<press-url>/dashboard/settings/developer`
2. Click **Connect GitHub**
3. Return to SSH session, re-run `bench-git-setup`.

Verify in backend:
```bash
mysql -e "SELECT user, github_username, is_revoked, expires_at FROM \`tabUser GitHub Auth\` WHERE user='USER@EMAIL.COM'"
```

### `git push` fails with `Authentication failed`

Check the token is still valid:
```bash
cat /dev/shm/git-session-*    # shows expires_in_seconds
```
If expired (session >8h old), run `bench-git-setup` again — it refreshes transparently.

### User disconnected themselves, wants back in

Just click Connect GitHub again in Settings → Developer. The disconnect/reconnect path is tested (`test_refresh_marks_revoked_on_bad_refresh_token`) and works idempotently via `get_or_create_for_user`.

### GitHub returned `redirect_uri is not associated with this application`

The GitHub App only accepts `<press-url>/github/authorize` as a callback URL. If you redeployed Press to a new URL, update the App's callback URL in GitHub settings to match.

### Audit logs show lots of failures with `reason: needs_connect`

Means a lot of users haven't run the 1-time setup. Broadcast the onboarding message again (see `docs/team-onboarding-github.md`).

---

## Rollout checklist

- [x] Day 1: doctypes + backend APIs shipped (commit `112bf3a425`)
- [x] Day 2: frontend Settings → Developer UI + bench-side script deployed to running containers
- [x] Day 3: code-review fixes (12 items) + 14 unit tests (commit `6e6ac5a7a3`)
- [x] Docker image template patched (`press/docker/Dockerfile` + `press/docker/config/bench-git-setup`)
- [x] Cron on press-f1 syncs env file to all running bench containers every 2 min
- [x] Daily pruning job for audit log registered in `hooks.py`
- [x] Memory updated (`press-ssh-agent-forwarding.md` "Option C" section)
- [ ] T15-T17: Team SSH tab column + auto-revoke on team removal (pending)
- [ ] T18: Playwright test for Connect GitHub button (deferred)
- [ ] T27: Owner broadcasts the onboarding message to the team

---

## Related docs

- `docs/srs/2026-04-22-option-c-github-app-user-tokens.md` — Full SRS (Objective / DoD / Before-After / risks / test plan)
- `docs/srs/CLAUDE-INDEX.md` — File index for future sessions
- `docs/team-onboarding-github.md` — 3-step user-facing guide (to send to every team member)
- `docs/wiki/01-backend-development/team-ssh-management.md` — Related feature (SSH key management)
