# CLAUDE-INDEX — Team SSH Access Management

**If you (a future Claude session) are asked to work on SSH / bench access / Dev tab / git-in-bench, read these files FIRST — in this order.**

All paths are relative to the `press` repo root (`/home/frappe/frappe-bench/apps/press/`) unless prefixed with `memory://` (in which case the file is in the Claude memory directory at `/home/eslam/.claude/projects/-home-eslam/memory/`).

---

## Read first — context

| # | File | Why |
|---|---|---|
| 1 | `memory://MEMORY.md` | Master memory index with SSH/Press context |
| 2 | `memory://press-ssh-agent-forwarding.md` | **Critical** — describes the press-f1 agent patch that must be re-applied after any agent `git pull` |
| 3 | `memory://frappe-press-lessons.md` (lessons 110–113) | What broke historically and why |
| 4 | `docs/srs/2026-04-22-team-ssh-management.md` | Full SRS — goals, DOD, before/after |
| 5 | `docs/wiki/01-backend-development/team-ssh-management.md` | Full feature architecture |
| 6 | `docs/plans/2026-04-22-team-ssh-test-plan.md` | 17-scenario test plan |

## Backend source files

| File | Purpose |
|---|---|
| `press/press/doctype/user_ssh_key/user_ssh_key.json` | Doctype schema — includes `label`, `is_disabled`, `disabled_by`, `disabled_on` |
| `press/press/doctype/release_group/release_group.py` | `generate_certificate(ssh_key_name=None)` + `get_certificate(ssh_key_name=None)` |
| `press/api/account.py` | 4 new admin APIs after `get_user_ssh_keys()`: `get_team_ssh_keys`, `set_team_ssh_key_disabled`, `remove_team_ssh_key`, `set_ssh_key_label` + `_require_team_owner` helper |
| `press/auth.py` | `ALLOWED_WILDCARD_PATHS` — includes the 3 dev-tab module prefixes |
| `press/press/doctype/bench/bench_dev_overview.py` | Dev tab APIs + `_ensure_team_access()` helper |
| `press/press/doctype/bench/bench_app_management.py` | Push-to-GitHub / create-app APIs + same `_ensure_team_access()` helper |
| `press/overrides.py` | `has_permission()` — the team-scoped permission hook |
| `press/press/doctype/team/team.py` | `has_permission()` for Team — how team owner vs member is detected |

## Frontend source files

| File | Purpose |
|---|---|
| `dashboard/src/components/SiteDevTab.vue` | Site Dev tab — Launch Code Server / Setup SSH Key / Local VS Code buttons |
| `dashboard/src/components/group/SSHCertificateDialog.vue` | SSH Access dialog — cert flow + key selector + `ssh -A` command + agent forwarding tip |
| `dashboard/src/components/settings/TeamSSHAccess.vue` | Team SSH admin table (owner only) |
| `dashboard/src/pages/Settings.vue` | Tab definitions — "Team SSH" conditional on owner |
| `dashboard/src/router.js` | Route `SettingsTeamSSH` added alongside SettingsDeveloper |
| `dashboard/src/main.js` | `X-Press-Team` header middleware (for context) |
| `dashboard/src/objects/group.js` | Release Group resource — `generateCertificate` / `getCertificate` method registrations |

## Out-of-band (server-side, outside the press repo)

| Host | File | Purpose |
|---|---|---|
| press-f1 | `/home/frappe/agent/repo/agent/ssh.py` | **PATCHED** — `add_principal()` method writes `pty,agent-forwarding,...` instead of `restrict,pty,...` and includes `-A` in the inner ssh command. Patch lost on agent `git pull` — re-apply per `press-ssh-agent-forwarding.md`. |
| press-f1 ssh container | `/etc/ssh/principals/<bench-user>` | Existing files migrated via sed loop (see memory file). New files written correctly by patched agent. |
| press-f1 bench containers | `/home/frappe/.ssh/known_hosts` | github.com keys pre-seeded on each container (one-time ssh-keyscan) |

## How to resume work on this feature

1. Read items 1–6 from "Read first — context" above.
2. Check `git log --oneline -20` on press-ctrl to see recent changes.
3. If a user issue is reported, diagnose along these lines:
   - **Team member can't see Dev tab / "Access not allowed for this URL"** → check `_ensure_team_access()` + `ALLOWED_WILDCARD_PATHS` in `auth.py`
   - **`git pull` fails in bench with "Permission denied (publickey)"** → check that `ssh -A` is used AND the principals file is the patched version (sample should show `pty,agent-forwarding` not `restrict,pty`)
   - **Cert generation fails with "A valid certificate already exists"** → old cert exists; the frontend/backend must respect `ssh_key_name` parameter (check `SSHCertificateDialog.vue` uses `.submit()` not `.fetch()`)
   - **Team SSH tab missing for owner** → `Settings.vue` condition `$team.doc?.user === $session.user`; make sure user is the team owner not just a System Manager
   - **SSH URL 404** → `sshKeySetupUrl` in `SiteDevTab.vue` should point to `/dashboard/settings/developer` NOT `/dashboard/profile#ssh-keys`

## Commit history for this feature

```
afe3171e04  feat(ssh): enable SSH agent forwarding for in-bench git access
b80e223fb6  fix(dev-tab): allow team members access to Dev tab APIs
97fd1b5c6c  feat(ssh): team SSH key management — labels, disable, admin control
9e45fdce22  fix(dev-tab): allow Code Server launch on all benches, fix SSH key URL
6f8b039edf  fix(dev-tab): fix Web VS Code fallback + Local VS Code SSH state
```

Use `git show <hash>` to see exact file/line changes for each.

## Gotchas to remember

- Changes to `press/api/account.py` or any Python file under `press/press/doctype/` require **worker restart** (`supervisorctl restart frappe-bench-workers: frappe-bench-web:`) — Python module cache doesn't auto-reload in production.
- Changes to `dashboard/src/**` require `npm run build` (from `dashboard/` dir), then **no restart needed** — files are served statically.
- Frappe's `run_doc_method` passes params via `args` dict — our frontend uses `.submit({ssh_key_name: x})`. `.fetch()` does NOT pass params to whitelisted methods correctly (caused "A valid certificate already exists" bug).
- `@dashboard_whitelist()` is just a thin wrapper around `@frappe.whitelist()` + a tracked set. No extra permission behavior. The real auth lives in `press/auth.py` allowlist + method-level guards.
- The `X-Press-Team` header is set by `dashboard/src/main.js` from `localStorage.getItem('current_team') || window.default_team`. Stale localStorage from a previous user can cause "PermissionError".

---

**Last updated:** 2026-04-22 by implementation of the team SSH management feature.
