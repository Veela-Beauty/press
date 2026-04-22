# SRS — Team SSH Access Management

**Document version:** 1.0
**Date:** 2026-04-22
**Author:** Press fork dev team
**Status:** Implemented and deployed

---

## Objective

Enable team members in Press to access bench containers securely — via Web VS Code, Local VS Code, or raw SSH — using their own GitHub identities for git operations, without any shared credentials stored on the server, while giving the team owner per-key enable/disable controls.

**One-sentence summary:** Each team member registers their SSH key in Press, the owner audits and can block/allow per-key, and cert-based SSH + agent forwarding means git operations inside benches use the developer's own GitHub account with no secrets on disk.

---

## Definition of Done

All criteria below must pass. Every item is testable via UI flow or API call.

- [x] `User SSH Key` doctype has `label`, `is_disabled`, `disabled_by`, `disabled_on` fields, migrated into the DB.
- [x] Team owner can view all team members' SSH keys in **Settings → Team SSH** — table with label, fingerprint, status (Active/Disabled).
- [x] Team owner can inline-edit the label for any team member's key; persists to DB.
- [x] Team owner can click **Disable** on any team member's key; status flips to red "Disabled"; `disabled_by` = owner's email; `disabled_on` = current time.
- [x] Team owner can re-enable a disabled key; audit fields cleared.
- [x] Team owner can **Remove** (soft-delete; `is_removed=1`).
- [x] Non-owner (regular team member) does NOT see the Team SSH tab in Settings.
- [x] Direct navigation to `/dashboard/settings/team-ssh` by a non-owner returns no data (permission error from `_require_team_owner`).
- [x] Bench → SSH Access dialog lets the user pick which of their keys signs the certificate when >1 exists.
- [x] Key selector displays the **label** (not the raw fingerprint) as the primary identifier.
- [x] Disabled keys appear in the selector with a red "Disabled" pill and `disabled` attribute on the radio input.
- [x] Generate SSH Certificate button is disabled with text "Selected key is disabled by admin" when the selected key is blocked.
- [x] Backend `generate_certificate(ssh_key_name=)` rejects disabled keys with "This SSH key has been disabled by your team admin. Contact them to re-enable it."
- [x] Dev tab on any site shows **Launch Code Server** button regardless of bench `is_code_server_enabled` flag.
- [x] Dev tab shows yellow **Setup SSH Key** button (linking to `/dashboard/settings/developer`) when the user has no registered key; otherwise shows the **Local VS Code** SSH Remote link.
- [x] Dev tab APIs are reachable by team members (Website User type), not just System Managers — verified by logging in as a member and loading the tab with no "Access not allowed" error.
- [x] SSH Access dialog's Step 2 command includes `-A` flag and an inline tip explaining agent forwarding.
- [x] Team member can SSH into a bench with `ssh -A ...`, run `ssh -T git@github.com` and see "Hi <their-github-handle>!"
- [x] Team member can `git pull` / `git push` in `~/frappe-bench/apps/<app>` using their own GitHub credentials.
- [x] Agent forwarding works through the press-proxy → bench-container hop (patched via `/home/frappe/agent/repo/agent/ssh.py`).
- [x] `github.com` host key is pre-seeded in every bench container's `~/.ssh/known_hosts` to avoid first-time prompts.

---

## Before / After

### Flow diagram — Before

```
Team member logs in
   ↓
Opens Site → Dev tab
   ↓
"Access not allowed for this URL"          ← HTTP 417 from press/auth.py allowlist
   │                                         (press.press.doctype.bench.* not in
   │                                          ALLOWED_WILDCARD_PATHS)
   ↓ (workaround: grant System Manager role)
   ↓
Loads, but every API calls frappe.only_for("System Manager")
   → still denied for Website Users
   ↓ (workaround: make the user System Manager)
   ↓
Web VS Code button → code.sandbox.mvpstorm.com (Frappe Cloud)
  → redirects to external login → dead end
   ↓
Local VS Code button → vscode://ssh-remote+frappe@... link fires
   → VS Code opens → SSH connects to port 2222
   → SSH proxy forces inner command "ssh frappe@..." WITHOUT -A
   → bench container has no SSH key for "frappe" user
   → auth fails (~/.ssh/ doesn't even exist in the container)
   ↓
User opens shell, tries "git pull"
   → Permission denied (publickey) from github.com
   → no agent forwarded, no GitHub key in container, no credential flow
   ↓
User gives up / copies their private key into the container (insecure)
```

### Flow diagram — After

```
Team member logs in
   ↓
Opens Site → Dev tab                       ← APIs under allowlist +
   ↓                                         _ensure_team_access(bench_name=...)
   ↓                                         allows team members
Dashboard renders:
  • "Launch Code Server" (blue button, works universally)
  • "Setup SSH Key" (yellow, if no key) OR "Local VS Code" (if key exists)
  • "Restart Bench"
   ↓
(One-time) Member goes to Settings → Developer → adds SSH key
   ↓
Returns to Bench → Options → SSH Access
   ↓
Dialog lists all their keys with LABELS (not raw fingerprints)
  Disabled keys shown grayed out + "Disabled" pill + disabled radio
   ↓
Pick a key → Generate SSH Certificate (6h validity)
   ↓
Copy Step 1 (store cert) + Step 2 ("ssh -A ...") locally
   ↓
ssh -A bench@proxy -p 2222
   │  SSH agent forwarded laptop → ssh-proxy
   ↓
ssh-proxy's principals file: pty,agent-forwarding + command="ssh -A frappe@..."
   │  Agent forwarded proxy → bench container
   ↓
Lands in frappe@bench-xxx:~/frappe-bench$
   ↓
ssh -T git@github.com → "Hi <dev-handle>!"
git pull / git push → works with dev's OWN GitHub credentials
```

### State comparison

| Metric | Before | After |
|---|---|---|
| Team members can open Dev tab | ❌ (System Manager only) | ✅ |
| Team members can see Setup SSH Key button | ❌ (403) | ✅ |
| Web VS Code fallback URL | Frappe Cloud login page (dead end) | "Launch Code Server" native flow |
| Sshv Key setup URL | `/dashboard/profile#ssh-keys` (404) | `/dashboard/settings/developer` (correct) |
| Owner can audit team SSH keys | ❌ (no UI) | ✅ (Settings → Team SSH) |
| Owner can disable a member's key | ❌ | ✅ (blocks cert generation) |
| Key has a human-readable name | ❌ (only fingerprint) | ✅ (label field) |
| SSH agent forwarding works end-to-end | ❌ (proxy strips it) | ✅ (principals patched) |
| `git pull` inside bench uses member's GitHub | ❌ (no auth) | ✅ (via forwarded agent) |
| GitHub keys stored on server | N/A (no way to auth) | Still NONE — agent-forwarded only |
| SSH cert lifetime | 6h (unchanged) | 6h (unchanged) |
| Files in bench container's `~/.ssh/` | Doesn't exist | `known_hosts` only (github.com pre-trusted) |

---

## Functional Requirements

### FR-1 — SSH Key Metadata
- The `User SSH Key` doctype SHALL have fields: `label` (Data), `is_disabled` (Check), `disabled_by` (Link User), `disabled_on` (Datetime).
- Labels SHALL be user-editable from two places: (a) any key's owner via Developer Settings, (b) team owner via Team SSH.
- `is_disabled=1` SHALL prevent `generate_certificate()` from creating new certificates for this key.

### FR-2 — Team SSH Admin View
- SHALL only be visible in Settings for users where `team.user == session.user`.
- SHALL list every enabled team member's keys (filter `is_removed=0`) with columns: full name, email, label, fingerprint, status, actions.
- SHALL show each key's `disabled_by` + `disabled_on` as a tooltip on the Disabled pill.
- SHALL provide actions: **Enable/Disable** (toggle), **Remove** (soft-delete with confirmation).
- SHALL refresh the list after every successful mutation.

### FR-3 — Certificate Generation
- `Release Group.generate_certificate` SHALL accept an optional `ssh_key_name` parameter.
- When provided: SHALL validate the key belongs to `session.user`, is not removed, AND not disabled.
- When omitted: SHALL fall back to the user's default key (`is_default=1 AND is_disabled=0 AND is_removed=0`).
- SHALL throw `"This SSH key has been disabled by your team admin. Contact them to re-enable it."` for disabled keys.
- Certificate validity SHALL remain 6 hours.

### FR-4 — Dev Tab Team Member Access
- Dev tab SHALL be accessible to any member of the team that owns the site.
- Backend APIs for Dev tab (in `bench_dev_overview.py`, `bench_app_management.py`) SHALL validate team membership via `_ensure_team_access()` helper instead of `frappe.only_for("System Manager")`.
- Cross-team administrative endpoints (e.g., `get_dev_overview_benches`) SHALL remain System Manager-only.

### FR-5 — SSH Agent Forwarding
- The press-agent's generated `/etc/ssh/principals/<bench-user>` files SHALL use options `pty,agent-forwarding,no-port-forwarding,no-x11-forwarding,no-user-rc` (not `restrict,pty`).
- The forced inner SSH command SHALL include `-A` flag: `ssh -A frappe@<ip> -p <port> -t '...'`.
- The SSH Access dialog Step 2 command SHALL include `-A` flag by default: `ssh -A bench@proxy -p 2222`.
- Bench containers SHALL have `github.com` ed25519 + rsa host keys pre-seeded in `/home/frappe/.ssh/known_hosts` at provisioning time.

### FR-6 — UX Defaults
- SSH Access dialog default selection SHALL be the user's default key if it's active; else first non-disabled key.
- Key selector SHALL display `label` as primary text and `ssh_fingerprint` as secondary (small, gray).
- Single-key users SHALL NOT see the radio list — just a "Using your only registered key: <label>" line.

---

## Non-Functional Requirements

### NFR-1 — Security
- **No GitHub tokens or private keys shall be stored on the Press server** or in any bench container. Authentication to GitHub MUST be via SSH agent forwarding from the developer's laptop.
- All team admin APIs MUST check `session.user == team.user` — never trust the X-Press-Team header alone for authorization.
- SSH certificates MUST remain 6h-lived. No extensions without explicit renewal.
- When a key is disabled, NEW cert requests MUST fail immediately. Existing certs (already-issued within the last 6h) remain valid until expiry; administrators may force-expire via Frappe desk if urgent.

### NFR-2 — Auditability
- Every disable/enable action MUST record `disabled_by` + `disabled_on` (set on disable, cleared on enable).
- The Press `Error Log` doctype MUST capture any unauthorized access attempt to team admin APIs.
- SSH session logins MUST remain logged via `press.auth.log` to `/home/frappe/frappe-bench/logs/press.auth.json.log`.

### NFR-3 — Compatibility
- The feature MUST NOT break existing single-key certificate flows. Users who only have 1 key MUST NOT see UI changes.
- The feature MUST work for both Press-owned teams and teams with `parent_team` set.
- Must work alongside `@action_guard(ReleaseGroupActions.SSHAccess)` — the existing ACTIONS_RULES permission check.

### NFR-4 — Operability
- After any `git pull` on the press-f1 agent repo (agent update), the `/home/frappe/agent/repo/agent/ssh.py` patch MUST be re-applied. A pre-deploy checklist step is documented at `press-ssh-agent-forwarding.md` in the Claude memory.
- Migration of existing `/etc/ssh/principals/*` files requires a single sed command documented in the same memory file.

### NFR-5 — Testability
- All tests MUST be runnable without production data — standard Press development site suffices.
- A dedicated test plan (17 scenarios) lives at `docs/plans/2026-04-22-team-ssh-test-plan.md`.
- Automated Playwright coverage MUST be added to `dashboard/tests/` (future work).

---

## Architecture

### Component interactions

```
┌──────────────────────────────────────────────────────────────────────┐
│                      Press Dashboard (Vue 3)                         │
│  ┌──────────────────┐   ┌────────────────────┐  ┌─────────────────┐  │
│  │ TeamSSHAccess    │   │ SSHCertificate     │  │ SiteDevTab      │  │
│  │ (owner only)     │   │ Dialog             │  │ (team member)   │  │
│  └────────┬─────────┘   └──────────┬─────────┘  └────────┬────────┘  │
│           │                        │                     │           │
│           │ call('press.api.       │ runDocMethod        │ call APIs │
│           │  account.X')           │  (Release Group)    │           │
└───────────┼────────────────────────┼─────────────────────┼───────────┘
            ▼                        ▼                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       Press Backend (Frappe)                         │
│                                                                      │
│  press/auth.py — ALLOWED_WILDCARD_PATHS gatekeeper                   │
│                                                                      │
│  press/api/account.py                                                │
│   ├─ get_team_ssh_keys()        (owner only)                         │
│   ├─ set_team_ssh_key_disabled()  (owner only)                       │
│   ├─ remove_team_ssh_key()      (owner only)                         │
│   └─ set_ssh_key_label()        (owner OR key owner)                 │
│                                                                      │
│  release_group.generate_certificate(ssh_key_name)                    │
│   └─ validates key → creates SSH Certificate doc                     │
│                                                                      │
│  bench_dev_overview.py / bench_app_management.py                     │
│   └─ _ensure_team_access(bench_name) → allows team members           │
└──────────────────────────────────────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         press-f1 host                                │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ ssh-proxy container (port 2222)                                 │ │
│  │  /etc/ssh/principals/<bench-user>:                              │ │
│  │    pty,agent-forwarding,... command="ssh -A frappe@..." ...     │ │
│  │    ▲                                                            │ │
│  │    │  (patched from restrict,pty)                               │ │
│  └────┼────────────────────────────────────────────────────────────┘ │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ bench container (port 2200X)                                    │ │
│  │   frappe user                                                   │ │
│  │   ~/.ssh/known_hosts ← github.com pre-seeded                    │ │
│  │   SSH_AUTH_SOCK forwarded from laptop                           │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Test Plan

Full test plan: `docs/plans/2026-04-22-team-ssh-test-plan.md` (17 scenarios, 5 parts).

Summary of coverage:
- **Part 1 (member self-service):** add key, add second key
- **Part 2 (owner admin):** see tab, label key, disable, enable, remove, non-owner can't see tab
- **Part 3 (certificate flow):** single-key, multi-key selection, disabled-key blocked (UI + backend)
- **Part 4 (Dev tab):** Setup SSH Key flow, Local VS Code opens, Launch Code Server
- **Part 5 (SSH + git):** actual shell access, `git fetch` via agent forwarding

---

## Roll-out Log

| Commit | Date | Description |
|---|---|---|
| `6f8b039edf` | 2026-04-22 | fix Web VS Code fallback + Local VS Code SSH state |
| `9e45fdce22` | 2026-04-22 | allow Code Server launch on all benches, fix SSH key URL |
| `97fd1b5c6c` | 2026-04-22 | team SSH key management (labels, disable, admin control) |
| `b80e223fb6` | 2026-04-22 | allow team members access to Dev tab APIs |
| `afe3171e04` | 2026-04-22 | enable SSH agent forwarding for in-bench git access |
| + `ssh.py` patch on press-f1 agent + `/etc/ssh/principals/*` migration | 2026-04-22 | out-of-band server changes (see press-ssh-agent-forwarding.md) |

---

## References

- Wiki page: `docs/wiki/01-backend-development/team-ssh-management.md`
- Lessons learned: `frappe-press-lessons.md` — lessons 110–113
- Press-f1 agent patch memo: `press-ssh-agent-forwarding.md` (Claude memory)
- Test plan: `docs/plans/2026-04-22-team-ssh-test-plan.md`
- File index for future sessions: `docs/srs/CLAUDE-INDEX.md`
