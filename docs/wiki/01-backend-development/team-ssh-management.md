# Team SSH Access Management

Team-level SSH key management for bench access. Team owners control which members can SSH into benches, with named keys, enable/disable controls, and agent-forwarded git workflows.

Shipped in commits:
- `6f8b039edf` — fix Web VS Code fallback + Local VS Code SSH state
- `9e45fdce22` — allow Code Server launch on all benches, fix SSH key URL
- `97fd1b5c6c` — team SSH key management (labels, disable, admin control)
- `b80e223fb6` — allow team members access to Dev tab APIs
- `afe3171e04` — enable SSH agent forwarding for in-bench git access

---

## Feature Overview

| Capability | Where | Who |
|---|---|---|
| Add / remove your own SSH key | Settings → Developer → SSH Keys | Any team member |
| Label an SSH key | Settings → Developer (own) or Team SSH (owner) | Owner of key / team owner |
| Generate SSH certificate | Bench → Options → SSH Access | Any team member |
| Pick WHICH key signs the cert | Bench → Options → SSH Access → Reissue | Any team member |
| Enable / disable any team member's key | Settings → Team SSH | Team owner only |
| Remove (soft-delete) any team member's key | Settings → Team SSH | Team owner only |
| Use local GitHub key inside bench via `ssh -A` | SSH shell → git | Any team member |

---

## Architecture

### Data model — User SSH Key DocType

Added in commit `97fd1b5c6c`.

| Field | Type | Purpose |
|---|---|---|
| `user` | Link → User | Owner of the key |
| `ssh_public_key` | Code | Raw OpenSSH public key |
| `ssh_fingerprint` | Data | Auto-computed SHA256 |
| `is_default` | Check | Used when `generate_certificate` called without `ssh_key_name` |
| `is_removed` | Check | Soft-delete flag |
| **`label`** | Data | Friendly name — "MacBook Work" |
| **`is_disabled`** | Check | Blocks cert generation without deleting |
| **`disabled_by`** | Link → User | Audit trail |
| **`disabled_on`** | Datetime | Audit trail |

Migration automatic via `bench --site <site> migrate` — no patch needed.

### Data model — SSH Certificate DocType (existing, unchanged)

Each call to `Release Group.generate_certificate(ssh_key_name=)` creates a new `SSH Certificate` signed by the Press CA. Validity = **6 hours**. No DB change — we just added an optional parameter.

### Backend APIs

**`press/press/doctype/release_group/release_group.py`** (modified):
- `generate_certificate(self, ssh_key_name=None)` — now accepts optional key name. Validates ownership + `is_disabled=0`, throws "This SSH key has been disabled by your team admin" if blocked.
- `get_certificate(self, ssh_key_name=None)` — returns cert for the specific key (lets UI show per-key cert state).

**`press/api/account.py`** (new functions):
- `_require_team_owner()` — private helper, throws `PermissionError` if caller is not `team.user`.
- `get_team_ssh_keys()` — returns every team member's keys with user, label, fingerprint, disabled state, audit fields. Owner only.
- `set_team_ssh_key_disabled(key_name, disabled)` — owner toggles + records `disabled_by`/`disabled_on`.
- `remove_team_ssh_key(key_name)` — owner soft-deletes (`is_removed=1`).
- `set_ssh_key_label(key_name, label)` — either the key owner OR the team owner can rename.
- `get_user_ssh_keys()` — *existing*, updated to also return `label` + `is_disabled` for the cert dialog.

All four new APIs are under the `press.api.*` wildcard allowlist in `auth.py` — accessible to Website Users in the team.

### Dev tab access control

**Blocker before the fix:** every `@frappe.whitelist()` in `press/press/doctype/bench/bench_dev_overview.py` + `bench_app_management.py` started with `frappe.only_for("System Manager")`. Team members (Website User type) got `Access not allowed for this URL` because:
1. The method-level `frappe.only_for` raised `PermissionError`
2. AND the path wasn't in `ALLOWED_WILDCARD_PATHS` in `press/auth.py`

**Fix in commit `b80e223fb6`:**
- Added `_ensure_team_access(bench_name=None, site_name=None)` helper to both modules. Allows System Users, System Manager role, or team members of the bench/site's team.
- Replaced 16 `frappe.only_for("System Manager")` calls with `_ensure_team_access(bench_name=bench_name)` or `_ensure_team_access(site_name=site_name)` based on each function's first argument.
- Added three module prefixes to `ALLOWED_WILDCARD_PATHS`:
  - `press.press.doctype.bench.bench_dev_overview.`
  - `press.press.doctype.bench.bench_app_management.`
  - `press.press.doctype.bench.health_analysis.`
- Kept `frappe.only_for("System Manager")` on the one module-level API that returns a cross-team dashboard (`get_dev_overview_benches`).

---

## SSH Agent Forwarding (for `git pull`/`git push` inside bench)

### The pipeline

```
Laptop (ssh-agent with GitHub key)
       │  ssh -A
       ▼
ssh-proxy container (port 2222)
  Auth:     TrustedUserCAKeys + AuthorizedPrincipalsFile
  Forces:   /etc/ssh/principals/<bench-user> "command=..."
       │  ssh -A (inner hop)
       ▼
Bench container (port 22001-220NN)
  User:  frappe
  Result: SSH_AUTH_SOCK is set → git uses laptop's GitHub key
```

### Critical patch on press-f1

File: `/home/frappe/agent/repo/agent/ssh.py`, method `add_principal`.

**Before** — blocked forwarding:
```python
force_command = f"ssh frappe@{ssh['ip']} -p {ssh['port']} -t '{cd_command}'"
principal_line = f'restrict,pty,command="{force_command}" {principal}'
```

**After** — enables forwarding end-to-end:
```python
force_command = f"ssh -A frappe@{ssh['ip']} -p {ssh['port']} -t '{cd_command}'"
principal_line = f'pty,agent-forwarding,no-port-forwarding,no-x11-forwarding,no-user-rc,command="{force_command}" {principal}'
```

**Two fixes in one patch:**
1. Added `-A` to the inner `ssh` — without it, the agent socket dies at the proxy.
2. Replaced `restrict,pty` with granular options — `restrict` disables agent forwarding; we need to opt-in explicitly.

New principals get written with the fix automatically. Existing principals are migrated one-time with:
```bash
docker exec ssh bash -c '
  cd /etc/ssh/principals
  for f in *; do
    sed -i -E "s|^restrict,pty,command=\"ssh frappe@|pty,agent-forwarding,no-port-forwarding,no-x11-forwarding,no-user-rc,command=\"ssh -A frappe@|" "$f"
  done
'
```

### Bench container pre-setup

Each bench container gets `github.com`'s host key seeded into `~/.ssh/known_hosts` on provisioning so first-time `git fetch` doesn't prompt:
```bash
for c in $(docker ps --format "{{.Names}}" | grep bench-); do
  docker exec -u frappe "$c" bash -c "mkdir -p ~/.ssh && ssh-keyscan -t ed25519,rsa github.com 2>/dev/null >> ~/.ssh/known_hosts && sort -u ~/.ssh/known_hosts -o ~/.ssh/known_hosts"
done
```

### Security model

- **No secrets on the server.** Team members' GitHub keys never leave their laptop. SSH agent forwarding means the bench has a Unix socket pointing back to the laptop's agent, usable only while the SSH session is open.
- **Each git commit is attributed to the real person.** No shared service account.
- **Short-lived.** SSH cert expires in 6 hours — stale sessions lose auth automatically.
- **Admin-revocable.** Owner flips `is_disabled=1` in Team SSH → next cert request fails immediately. Existing 6h cert is still valid until it expires (or admin can force-expire via Frappe desk if urgent).

---

## Frontend

### Settings → Team SSH tab (new, owner-only)

File: `dashboard/src/components/settings/TeamSSHAccess.vue`

Table columns: Team Member | Key Label (editable inline) | Fingerprint | Status (Active / Disabled) | Actions (Enable/Disable + Remove).

Visibility: gated in `Settings.vue` by `$team.doc?.user === $session.user || $session.isSystemUser`. Non-owners never see the tab.

### SSH Access dialog updates

File: `dashboard/src/components/group/SSHCertificateDialog.vue`

- **Before cert exists:** radio list of all the user's SSH keys. Disabled keys shown with red background + `Disabled` pill + `disabled` attribute on radio. Single-key users see "Using your only registered key: <label>".
- **After cert exists:** shows "Certificate issued for key: <label>" + "Reissue for a different key" button to go back to radio selection.
- **Step 2 SSH command:** now includes `-A` flag by default (`ssh -A bench@proxy -p 2222`) with an inline tip explaining agent forwarding.
- **Generate button:** disabled with "Selected key is disabled by admin" text when the chosen key is blocked.

### Dev tab updates (Site Dev tab)

File: `dashboard/src/components/SiteDevTab.vue`

- **Web VS Code button:** removed hard-coded `code.sandbox.mvpstorm.com` fallback (Frappe Cloud login page). Now always shows "Launch Code Server" for any bench with no running code-server.
- **Local VS Code button:** shows the `vscode://vscode-remote/ssh-remote+...` link when user has `has_ssh_key=true`. Otherwise shows a yellow **Setup SSH Key** button linking to `/dashboard/settings/developer` (the correct URL — `/dashboard/profile#ssh-keys` was a 404).

---

## Testing Checklist

See `docs/plans/2026-04-22-team-ssh-test-plan.md` for the full 17-test plan covering:
- Member self-service (add key, add second key)
- Owner admin view (see tab, label, disable, enable, remove, non-owner blocked)
- Certificate flow (single-key, multi-key pick, disabled-key blocked)
- Dev tab integration (Setup SSH Key button, Local VS Code button, Launch Code Server)
- End-to-end SSH into bench + git operations via agent forwarding

---

## Related Files — quick map

| Area | File |
|---|---|
| DocType schema | `press/press/doctype/user_ssh_key/user_ssh_key.json` |
| Certificate backend | `press/press/doctype/release_group/release_group.py` — `generate_certificate`, `get_certificate` |
| Admin APIs | `press/api/account.py` — 4 new functions after `get_user_ssh_keys` |
| Auth allowlist | `press/auth.py` — `ALLOWED_WILDCARD_PATHS` |
| Team member gate | `press/press/doctype/bench/bench_dev_overview.py` — `_ensure_team_access` + 14 call sites |
| Team member gate | `press/press/doctype/bench/bench_app_management.py` — same pattern |
| Agent forwarding patch | press-f1 `/home/frappe/agent/repo/agent/ssh.py` (see `press-ssh-agent-forwarding.md`) |
| Dev tab UI | `dashboard/src/components/SiteDevTab.vue` |
| SSH cert dialog | `dashboard/src/components/group/SSHCertificateDialog.vue` |
| Team SSH admin UI | `dashboard/src/components/settings/TeamSSHAccess.vue` |
| Settings tabs | `dashboard/src/pages/Settings.vue` |
| Router | `dashboard/src/router.js` — `SettingsTeamSSH` route |
