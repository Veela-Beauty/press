# SRS — Git-in-Bench via GitHub App User-to-Server Tokens (Option C)

**Document version:** 1.0
**Date:** 2026-04-22
**Status:** DRAFT — awaiting approval
**Author:** Press fork dev team
**Supersedes:** n/a (new feature)

---

## Objective

Let every team member do `git pull` / `git push` from inside any of their benches using their own GitHub identity — without storing any long-lived secrets on the server, without requiring local SSH agent setup, and without deploy keys (blocked by the Veela-Beauty org policy). Authentication uses the existing **mvpstorm-deploy** GitHub App (installation `114894173` on Veela-Beauty) via the User-to-Server flow: each dev authorizes the App once in Press, and Press mints short-lived tokens for them on every SSH session.

**One-sentence summary:** Reuse the existing GitHub App, add a per-user "Connect GitHub" OAuth flow in Press, and inject a fresh 1-hour User-to-Server token into every SSH session so `git` works out of the box with the dev's own GitHub identity.

---

## Definition of Done

All criteria testable. Every item is a checkbox a QA lead can tick.

### Data model
- [ ] New doctype `User GitHub Auth` with: `user` (Link→User), `github_username` (Data), `access_token` (encrypted), `refresh_token` (encrypted), `expires_at` (Datetime), `refresh_expires_at` (Datetime), `scopes` (Data), `connected_on` (Datetime), `last_used_on` (Datetime), `is_revoked` (Check).
- [ ] Migration script runs cleanly on `demo.mvpstorm.com`.
- [ ] Token fields use Frappe's `Password` field type (encrypted at rest).

### Backend — OAuth connect flow
- [ ] Endpoint `GET /api/method/press.api.github_auth.start_connect` returns the GitHub App authorization URL with CSRF-safe state.
- [ ] Endpoint `GET /api/method/press.api.github_auth.oauth_callback` (allow_guest, rate-limited) handles the `code` exchange, creates or updates `User GitHub Auth`.
- [ ] Scopes requested: (App's declared scopes — no extras needed; user-to-server inherits App permissions).

### Backend — token minting for SSH sessions
- [ ] New API `press.api.bench.get_git_credentials_for_session(bench_name)` — team-member-only — returns a dict `{ "github.com": "<short-lived-token>" }` for the calling user.
- [ ] Function refreshes expired tokens transparently via `refresh_token` exchange.
- [ ] If the user has no `User GitHub Auth` record: returns `{ "needs_connect": true, "authorize_url": "..." }` so the SSH login script can print a friendly message.
- [ ] Token response time < 2 seconds (measured with 100 concurrent calls).

### Backend — revocation
- [ ] Endpoint `POST /api/method/press.api.github_auth.disconnect` — user revokes their own connection; Press calls `DELETE /applications/{client_id}/grant` on GitHub to invalidate the token server-side.
- [ ] Team owner can revoke any team member's connection via `set_team_ssh_key_disabled`-style admin endpoint.
- [ ] When a user is `disabled=1` on Team or removed from Team Member, their `User GitHub Auth` is auto-revoked.

### SSH-login integration
- [ ] New shell helper `/usr/local/bin/bench-git-setup` (~40 lines) is executed at the start of every SSH session into a bench container. It:
  1. Calls the Press API `get_git_credentials_for_session` (via an internal token).
  2. If token received → writes `~/.git-credentials` to `/dev/shm/git-creds-${USER}-${SESSION}` (tmpfs only, no disk).
  3. Configures `git config credential.helper "store --file=/dev/shm/git-creds-..."`.
  4. Sets `git config user.email` and `user.name` from the user's Press profile.
  5. If `needs_connect: true` → prints a message: "Connect your GitHub at <URL> to enable git push/pull".
- [ ] The script is called by the ssh-proxy's ForceCommand wrapper (extend `add_principal` in `/home/frappe/agent/repo/agent/ssh.py`).
- [ ] `~/.bash_logout` wipes the tmpfs credentials file.
- [ ] If the Press API call fails, `git` still works for read-only public repos; the SSH session continues (graceful degradation).

### Frontend
- [ ] Settings → Developer tab shows a new **GitHub Connection** section with status: ✅ Connected as `<username>` (since `<date>`) OR "Not connected — [Connect GitHub] button".
- [ ] Click **Connect GitHub** → opens OAuth flow → on success, page refreshes showing connected state.
- [ ] Click **Disconnect** → confirmation dialog → revokes on GitHub + clears Press record.
- [ ] A new Settings → Team SSH column shows "GitHub Connected" Y/N for every team member (owner-only).

### Security
- [ ] Tokens never logged — audited grep of all log files for the word "token" returns only encrypted or masked values.
- [ ] Tokens never written to disk on the bench — only `/dev/shm` tmpfs.
- [ ] API `get_git_credentials_for_session` rejects requests from non-team-members with a clear 403.
- [ ] OAuth callback endpoint has CSRF state verification + 5-minute state expiry + rate limit (10/min/IP).
- [ ] Frappe's audit log records every token mint with `{user, bench, timestamp, token_expiry}`.

### Observability
- [ ] Every `get_git_credentials_for_session` call logged to a new `Git Credential Session Log` doctype (user, bench, timestamp, success Y/N, error msg).
- [ ] Frappe Error Log captures any OAuth failures with full context.
- [ ] Dashboard admin view "GitHub Audit" lists last 100 token mints across all users.

### Tests
- [ ] 25+ automated test scenarios (Playwright + Python unit) covering: OAuth flow, token refresh, SSH session token delivery, git pull inside bench, git push, disconnect, revoke, non-team-member rejected, expired-token refresh, network-error graceful failure.
- [ ] Load test: 100 concurrent SSH sessions → all get tokens < 2s.
- [ ] End-to-end flow verified by Mahmoud and Marco on actual benches.

### Documentation
- [ ] Wiki page `docs/wiki/03-integrations/github-app-user-tokens.md` — full architecture, sequence diagrams.
- [ ] Updated `docs/srs/CLAUDE-INDEX.md` adds this feature.
- [ ] `docs/plans/2026-04-23-option-c-test-plan.md` — detailed test scenarios.
- [ ] Team onboarding doc updated: "One-time GitHub connect in Press → git works everywhere".

---

## Before / After

### Current flow (Before — doesn't work)

```
Team member logs into Press
   ↓
SSHs into bench via "ssh -A bench-...@proxy -p 2222"
   ↓
Inside bench, tries "git pull"
   ↓
┌─────────────────────────────────────────────────────────────────┐
│  Option 1: HTTPS remote  → "Username:" prompt → no way to auth  │
│  Option 2: SSH remote    → "Permission denied (publickey)"      │
│  Option 3: Deploy key    → blocked by org policy                │
│  Option 4: Copy key in   → violates security model              │
│  Option 5: Agent forward → requires each dev to:                │
│                            - start ssh-agent on Windows         │
│                            - ssh-add id_ed25519                 │
│                            - verify with ssh-add -L             │
│                            - 30% of team can't get it working   │
└─────────────────────────────────────────────────────────────────┘
   ↓
Dev gives up / copies key onto bench (security incident)
```

### New flow (After — Option C)

```
One-time setup (per dev, lifetime ~1 min):
  Settings → Developer → [Connect GitHub]
  Browser redirect → GitHub authorize → back to Press
  ✅ Connected as <username>

On every SSH session:
   Team member SSHs into bench
      ↓
   (ForceCommand) /usr/local/bin/bench-git-setup runs transparently
      ↓
   Press API returns 1-hour user-to-server token for <user>
      ↓
   ~/.git-credentials written to tmpfs (never touches disk)
      ↓
   git config user.email/name set from Press profile
      ↓
   Normal shell starts
      ↓
   cd ~/frappe-bench/apps/<app>
   git pull                 ← works instantly, uses dev's GitHub identity
   git push                 ← works instantly, commits show dev's email
   (token expires after 1h — invisible to dev unless session > 1h,
    in which case bench-git-refresh auto-runs from a bash prompt hook)
      ↓
   Dev logs out
      ↓
   ~/.bash_logout wipes /dev/shm/git-creds-*
```

### State comparison

| Dimension | Before | After |
|---|---|---|
| Devs who can git push/pull in bench | 0 | 100% after 1-min connect |
| Local setup required on dev's laptop | SSH agent + key management | None (just connect in browser) |
| Long-lived secrets on server | Zero (broken) | Zero (working) |
| Commit attribution in Git log | N/A | ✅ Dev's email |
| GitHub audit log actor | N/A | `mvpstorm-deploy[bot] on behalf of <user>` |
| Admin can disable 1 dev's git without SSH | Impossible | Yes (Settings → Team SSH → disconnect) |
| Scope boundary | N/A | App-declared scopes ∩ user's GitHub access |
| Revocation path | N/A | 3 paths: user self-serve / admin / GitHub org admin |
| Blast radius if Press DB leaks | N/A | N encrypted user tokens, all refreshable |
| MFA required? | N/A | Inherits user's GitHub MFA |

---

## Architecture

### Component map

```
┌──────────────────────────────────────────────────────────────────────┐
│                          GitHub.com                                  │
│  ┌──────────────────────────┐        ┌───────────────────────────┐   │
│  │ GitHub App:              │        │ User: marco               │   │
│  │   mvpstorm-deploy        │        │  ↳ authorized App         │   │
│  │   client_id: Iv23...     │  ←──→  │  ↳ has access to repos    │   │
│  │   installation:          │        │  ↳ refresh_token stored   │   │
│  │     Veela-Beauty (114…)  │        │                           │   │
│  └──────────────┬───────────┘        └───────────────────────────┘   │
│                 │ User-to-Server token (1h)                          │
└─────────────────┼────────────────────────────────────────────────────┘
                  │
         ┌────────▼──────────┐     ┌────────────────────────────────┐
         │   Press Dashboard  │←───│   Press Settings → Developer   │
         │                    │     │   [Connect GitHub] button      │
         └────────┬──────────┘     └────────────────────────────────┘
                  │ REST
         ┌────────▼──────────────────────────────────────────────────┐
         │                  Press Backend                            │
         │                                                           │
         │  press/api/github_auth.py                                 │
         │   ├─ start_connect()              ← generates state+URL  │
         │   ├─ oauth_callback(code,state)   ← exchanges for tokens │
         │   ├─ disconnect()                 ← revokes on GitHub    │
         │                                                           │
         │  press/api/bench.py                                       │
         │   └─ get_git_credentials_for_session(bench_name)          │
         │      ↳ fetches User GitHub Auth for session user          │
         │      ↳ if expired → refresh                               │
         │      ↳ returns {"github.com": access_token}               │
         │                                                           │
         │  Doctype: User GitHub Auth (encrypted tokens)             │
         │  Doctype: Git Credential Session Log (audit)              │
         └────────┬──────────────────────────────────────────────────┘
                  │
         ┌────────▼─────────────────────────────────────────────────┐
         │                   press-f1 host                          │
         │                                                          │
         │  ssh-proxy container (port 2222)                         │
         │   /etc/ssh/principals/<bench-user>:                      │
         │     pty,agent-forwarding,…,                              │
         │     command="ssh -A -o SendEnv=PRESS_USER                │
         │              frappe@<bench-ip>                           │
         │              -t '/usr/local/bin/bench-git-setup;         │
         │                   cd frappe-bench; exec bash --login'"   │
         │                                                          │
         └──────────────────────┬───────────────────────────────────┘
                                │
         ┌──────────────────────▼────────────────────────────────────┐
         │ bench container (port 2200X)                              │
         │  /usr/local/bin/bench-git-setup  (new, ~40 lines bash):   │
         │    1. export GIT_USER=$(get-press-user)                   │
         │    2. curl $PRESS_URL/api/method/                         │
         │            press.api.bench.get_git_credentials_for_session│
         │    3. echo "https://oauth2:$token@github.com"             │
         │            > /dev/shm/git-creds-$USER                     │
         │    4. git config --global credential.helper               │
         │            "store --file=/dev/shm/git-creds-$USER"        │
         │    5. git config --global user.email "$EMAIL"             │
         │    6. git config --global user.name "$FULL_NAME"          │
         │                                                           │
         │  ~/.bash_logout (new):                                    │
         │    rm -f /dev/shm/git-creds-$USER                         │
         └───────────────────────────────────────────────────────────┘
```

### Data flow (per SSH session)

1. **Dev SSHs** — `ssh -A bench-…@proxy -p 2222`
2. **Proxy sshd** authenticates via cert; matches principal; runs ForceCommand
3. **ForceCommand** runs `ssh -A -o SendEnv=PRESS_USER frappe@bench-ip -t 'bench-git-setup; exec bash --login'`
   - `PRESS_USER` env var carries the dev's email (set from SSH cert's `key-identity` which already contains the user's login — extract during the ssh-proxy hop)
4. **Bench sshd** accepts the connection (now with agent-forwarding yes from lesson 114)
5. **bench-git-setup** runs:
   - Reads `$PRESS_USER`
   - Fetches an internal service token from env (`PRESS_INTERNAL_TOKEN`, injected at bench provisioning time)
   - `curl -H "X-Press-Internal-Token: $T" -H "X-Press-User: $PRESS_USER" https://<press>/api/method/press.api.bench.get_git_credentials_for_session`
   - Receives `{"github.com": "gho_…"}`
   - Writes `https://oauth2:gho_…@github.com` to `/dev/shm/git-creds-<user>`
   - Sets git config (global scope for this user's session)
6. **Login shell** starts normally
7. **Dev runs `git pull`** — git reads `/dev/shm/git-creds-<user>` via the configured helper → uses token → succeeds
8. **After 1h**: token expires. A bash prompt hook (`PROMPT_COMMAND`) detects stale credentials and refreshes transparently (< 500ms latency on next prompt)
9. **Dev logs out** → `.bash_logout` → `rm /dev/shm/git-creds-<user>`

### Security boundaries

| Boundary | What crosses it | Protection |
|---|---|---|
| Laptop → Press API (OAuth connect) | user's OAuth grant | TLS + CSRF state + redirect_uri whitelist |
| Press API → GitHub | App credentials + user code exchange | GitHub App private key (in Press Settings) + client_secret |
| Press DB | User GitHub Auth rows | Frappe field encryption, encryption key in site_config |
| Press API → ssh-proxy container | — | — (same host, no external traffic) |
| ssh-proxy → bench container | ForceCommand invocation | SSH (existing) |
| bench → Press API (credential fetch) | short-lived internal token | service-account token, scoped to `get_git_credentials_for_session` only, per-bench |
| bench filesystem | `/dev/shm/git-creds-*` | tmpfs (RAM only) + user-owned + 0600 mode |
| bench → GitHub (git operations) | user's 1h access token | HTTPS + token bearer |

### Failure modes

| Failure | Observable to dev | Fallback |
|---|---|---|
| Press API unreachable from bench | "warning: could not fetch git credentials" on login | shell starts anyway; git read-only on public repos |
| User never connected GitHub | "Connect GitHub at <URL> to enable git" on login | shell starts anyway; git fails with helpful error |
| Refresh token revoked | Token fetch returns `needs_reconnect: true` | clear message + disconnect record auto-marked |
| GitHub API rate limit (60/h without token) | handled by Press proxy caching tokens 50 min | tokens cached 55min, refresh in background |
| bench-git-setup script corrupted | login continues (`|| true` wrapper) | logged to journal; admin alerted |

---

## Test Plan

Full plan: `docs/plans/2026-04-23-option-c-test-plan.md`.

### Happy-path tests (5)
1. Marco connects GitHub in Press → sees "Connected as elgogary" (his GitHub handle)
2. Marco SSHs into a bench → `git config user.email` is `marco@…`
3. Marco runs `git pull` → succeeds, no prompt
4. Marco runs `git push` → succeeds, commit shows his email on GitHub
5. Marco stays in SSH for > 1h → token refreshes on next git op, no manual intervention

### Negative-path tests (8)
6. Non-team-member calls `get_git_credentials_for_session` directly → 403
7. User without `User GitHub Auth` SSHs in → gets "Connect GitHub" message, git fails cleanly
8. User's refresh token revoked on GitHub → Press detects on next mint, marks record disconnected
9. Press DB restore from backup with stale encryption key → tokens unreadable, API returns reconnect flow
10. Network failure to GitHub during OAuth callback → user sees "Connection failed, try again" screen
11. Replay attack: OAuth state reused → rejected
12. Malicious dev runs `cat ~/.git-credentials` → finds tmpfs file; logs + rotates on next session
13. Team owner disables user's connection → `git pull` fails on next session with "admin revoked" message

### Load tests (3)
14. 50 concurrent SSH sessions (different users) → all receive tokens < 2s each
15. 1000 git pulls with existing tokens → p99 < 150ms (tmpfs read + GitHub HTTPS)
16. Token refresh storm (50 users with expired tokens simultaneously) → no GitHub rate-limit hits

### Attribution tests (3)
17. Marco commits + pushes → GitHub shows `marco's email` as author
18. Mahmoud commits + pushes same repo → shown as distinct author
19. GitHub org audit log shows `mvpstorm-deploy[bot] on behalf of <username>` for each push

### Revocation tests (3)
20. User self-disconnects in Press → GitHub API `DELETE /grant` succeeds → Press record marked revoked
21. Team owner disables user → background job auto-calls disconnect
22. GitHub org admin revokes App installation → all bench git operations start failing within 1h

### Admin view tests (3)
23. Owner views Team SSH tab → sees GitHub Connected column
24. Owner views Git Credential Session Log → sees recent token mints
25. Owner filters audit log by user → correct subset

---

## Implementation Tasks

Grouped by day, ordered by dependency.

### Day 1 — Backend foundations
- [ ] **T01** — Create `User GitHub Auth` doctype (JSON + controller)
- [ ] **T02** — Create `Git Credential Session Log` doctype
- [ ] **T03** — Migration on demo site
- [ ] **T04** — Write `press/api/github_auth.py` with `start_connect`, `oauth_callback`, `disconnect`
- [ ] **T05** — Token refresh helper (`refresh_user_token(user_github_auth)`)
- [ ] **T06** — Unit tests for OAuth code exchange + refresh

### Day 2 — SSH session integration
- [ ] **T07** — Write `/usr/local/bin/bench-git-setup` shell script
- [ ] **T08** — Patch `/home/frappe/agent/repo/agent/ssh.py` to extend ForceCommand to call the script on first SSH
- [ ] **T09** — Write `press/api/bench.py::get_git_credentials_for_session`
- [ ] **T10** — Add `press.api.bench.get_git_credentials_for_session` to `ALLOWED_WILDCARD_PATHS` (already covered by `press.api.*`)
- [ ] **T11** — Bake `bench-git-setup` into bench Docker image via `press/docker/config/...`
- [ ] **T12** — Migrate existing running containers (scp + chmod)

### Day 3 — Frontend + revocation
- [ ] **T13** — New "GitHub Connection" section in `DeveloperSettings.vue`
- [ ] **T14** — OAuth redirect handler Vue page (`/dashboard/github-connected`)
- [ ] **T15** — Add "GitHub Connected" column to Team SSH admin table
- [ ] **T16** — "Disconnect" button + confirmation
- [ ] **T17** — On team-member removal: auto-revoke (hook)
- [ ] **T18** — Playwright tests for connect + disconnect flows

### Day 4 — Testing + docs
- [ ] **T19** — Run the 25 test scenarios with Mahmoud + Marco
- [ ] **T20** — Fix any discovered bugs
- [ ] **T21** — Wiki page `03-integrations/github-app-user-tokens.md`
- [ ] **T22** — Update `CLAUDE-INDEX.md` + `MEMORY.md`
- [ ] **T23** — Update team onboarding cheat-sheet

### Day 5 — Deploy + rollout
- [ ] **T24** — Commit + push all changes
- [ ] **T25** — Deploy to press-ctrl + restart workers
- [ ] **T26** — Notify team — one-line message: "Go to Settings → Developer → Connect GitHub. Your bench git will just work from now on."
- [ ] **T27** — Monitor `Git Credential Session Log` for 24h

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Veela-Beauty org blocks OAuth grants to 3rd-party Apps | Low | High | Use the existing mvpstorm-deploy App which is already allowlisted |
| Token refresh logic has race condition under load | Medium | Medium | Use DB row lock during refresh; load-test scenario 15 |
| `bench-git-setup` script breaks login for everyone | Medium | **High** | Wrap every step in `|| true`; script never blocks login; comprehensive logging |
| User confused by "Connect GitHub" step | High | Low | Clear UI with screenshots + inline "Why?" tooltip; team owner onboards new members |
| tmpfs credentials readable by other users on same bench | Low | Medium | File mode 0600 + owned by the user; bench containers don't have multi-user concerns in practice |
| Press's SECRET_KEY rotated without re-encrypting tokens | Low | Medium | Add `is_stale` flag + prompt reconnect on decrypt failure |
| GitHub changes user-to-server API | Low | High | Pin to `Accept: application/vnd.github.v3+json` header; monitor GitHub changelog |
| Team grows beyond GitHub App rate limit (5000 req/h per installation) | Low | Medium | Cache tokens 55 min locally; only refresh at 5-min-to-expiry |

---

## Rollout Plan

### Phase 1: Internal (Day 5 afternoon)
- Deploy to press-ctrl
- You (team owner) connect first
- Mahmoud + Marco connect, test
- Verify Git Credential Session Log populates

### Phase 2: Team opt-in (Days 6-7)
- Announce to team with clear onboarding steps
- Provide support via Slack for connect issues
- Keep the existing SSH-only flow as fallback (doesn't conflict)

### Phase 3: Cleanup (Day 14)
- Remove the "agent forwarding with local ssh-add" recommendation from onboarding docs (since it's now optional, not required)
- Close old Option-A-like workarounds in the doc

---

## Acceptance Criteria (what means "done")

All 25 test scenarios green. Mahmoud + Marco each demonstrate:
1. Connect GitHub in Press (1 click + authorize)
2. SSH into their bench
3. `git pull` — works with no prompts
4. `git push` with a trivial commit — succeeds
5. GitHub shows commit attributed to their email
6. Press Audit log shows the token mint events

Plus: team owner can see both connected in Team SSH tab; disconnect one and watch their bench git fail.

---

## References

- GitHub App: https://github.com/apps/mvpstorm-deploy
- Installation IDs: Veela-Beauty=114894173, accurate-systems=114895817, elgogary=114979006
- Existing code: `press/api/github.py::get_access_token` (App-to-installation — reuse for the refresh)
- Existing code: `press/www/github/authorize.py` (partial OAuth — extend for user flow)
- Related SRS: `docs/srs/2026-04-22-team-ssh-management.md`
- Lessons: `memory://frappe-press-lessons.md` (110-114)
- Test plan: `docs/plans/2026-04-23-option-c-test-plan.md`
