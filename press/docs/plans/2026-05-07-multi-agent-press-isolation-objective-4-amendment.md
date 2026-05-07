# Objective 4 Amendment — MCP Server with Admin Auth, Token Persistence & Logs Panel

**Date:** 2026-05-07
**Amends:** `docs/plans/2026-05-07-multi-agent-press-isolation.md` § Objective 4
**Why:** During implementation of Objective 1, the user surfaced concrete operational pain that was missing from the original Objective 4 spec.

---

## Objective (this amendment)

Make the MCP server a **first-class operational surface** that handles real-world auth churn (admin passwords change ~5×/day in normal use), exposes itself **inside the Vue dashboard** for transparency, and **inherits Press's existing team-role permission model** so agents are never granted wider access than the human operator who created their token.

**One-sentence summary**: Replace the original Objective 4's bare MCP token auth with a fresh-token endpoint (admin password → token), persistent scoped tokens, a Vue **Developer Tools › MCP** panel showing live logs and active tokens, and full integration with Press Team Member + Press Role permission systems.

---

## What changes vs the original Objective 4

| Original Objective 4                                         | Amended Objective 4                                                                                                            |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| Token auth (per-agent API key:secret pair)                   | Same, BUT tokens are issued via a **fresh-auth endpoint** (admin password → token) so frequent admin password changes don't require regenerating long-lived API key pairs |
| Audit log (data only)                                        | **Vue Developer Tools › MCP panel** — live log table, active tokens, revoke buttons, last-used timestamps                       |
| `agent_identity` field on every call                         | Same                                                                                                                           |
| (no team integration)                                        | **Token inherits the issuing user's `Team Member.press_role` + `Press Role` permission flags** — agent CANNOT exceed human's access |
| (no admin panel surface)                                     | New **Admin Panel** sub-page for system admins to see all tokens across all teams + revoke them globally                        |

---

## Definition of Done — overall

- [ ] All Objective 4 DoD items from the original plan still apply.
- [ ] Plus the 4 new sub-objectives below (4a, 4b, 4c, 4d) all complete.
- [ ] All previous Objective 4 tools (clone_bench, clone_site, lock_acquire, etc.) accept the new token format and emit logs visible in the Vue panel.
- [ ] No Objective 4 MCP tool can perform an action that the issuing user can't perform via the regular dashboard (permission parity verified by test).

---

## Sub-objective 4a — Fresh-Auth Endpoint (`mcp.auth.issue_token`)

### Why

Operator workflow: admin password rotates ~5 times/day. Long-lived API key pairs are wrong because (1) they don't auto-revoke when password rotates, (2) they're hard to scope per-task. Better: agent submits the current admin password and gets back a short-lived token scoped to a specific task.

### DoD

- [ ] `press.mcp_server.auth.issue_token(username, password, scope, ttl_minutes=60, label=None)` whitelisted method (callable BEFORE the agent has any MCP token — guest-allowed but rate-limited).
  - `username` — Frappe user identity (typically `<email>` of a Team Member).
  - `password` — current Frappe password for that user. Validated via `frappe.local.login_manager.check_password(...)` — same path the dashboard login uses.
  - `scope` — list of tool names from the MCP tool catalog the token may invoke (e.g., `["clone_bench", "clone_site", "lock_acquire", "lock_release"]`). Default: ALL read-only tools.
  - `ttl_minutes` — 1–1440 (24h max). Token records `expires_at`.
  - `label` — free-text "what is this token for", e.g. `"Agent Claude-1 — refactor task"`. Required for audit clarity.
  - Returns `{token, expires_at, scope, label}`.
- [ ] Failed `issue_token` calls log to `Press MCP Auth Attempt` doctype with username, success/fail, IP, timestamp. Brute-force guard: 5 failed attempts in 5 minutes from same IP → block IP for 1 hour.
- [ ] Successful issue logs an `MCP Token Issued` event in the audit log.
- [ ] **Token format**: opaque random 64-char string. Stored hashed (PBKDF2-SHA256, same hash algo Frappe uses for passwords) in the new `Press MCP Token` doctype. The plaintext value is shown ONCE on issue, never again.
- [ ] Test: `test_issue_token_with_correct_password_succeeds`, `test_issue_token_with_wrong_password_fails`, `test_issue_token_brute_force_blocks_after_5_fails`, `test_issue_token_scope_defaults_to_readonly`, `test_token_hashed_not_plaintext_in_db`.

### Files

- `press/mcp_server/auth.py` — new module, `issue_token()` + `verify_token()` helpers.
- `press/mcp_server/doctype/press_mcp_token/press_mcp_token.json` — new doctype with fields: `user` (Link User), `token_hash` (Password), `scope` (Code, list of tool names), `expires_at` (Datetime), `label` (Small Text), `last_used_at` (Datetime), `revoked` (Check), `created_via_password_at` (Datetime), `team` (Link Team — denormalized from User for quick filtering).
- `press/mcp_server/doctype/press_mcp_auth_attempt/press_mcp_auth_attempt.json` — new doctype: `username`, `ip_address`, `success` (Check), `creation`.
- `press/mcp_server/test_auth.py` — 5 unit tests above.

---

## Sub-objective 4b — Token Verification + Permission Inheritance

### Why

When an agent calls an MCP tool with a token, the server must:
1. Validate the token (not expired, not revoked, scope includes this tool).
2. Resolve the token's issuing user.
3. Run the tool **as that user** — `frappe.set_user(token.user)` — so all permission checks (Team Member roles, Press Role flags from lesson #128) work transparently.

### DoD

- [ ] `verify_token(token_plaintext, tool_name)` returns the resolved User docname OR raises `frappe.PermissionError`.
- [ ] All MCP tool wrappers call `verify_token` first, then `frappe.set_user(user)`, then dispatch.
- [ ] Last-used timestamp updates on each successful verify.
- [ ] Permission parity test: a Team Member with `press_role=Member` (limited) cannot use their token to clone a bench owned by a different team.
- [ ] Permission parity test: a System User (Administrator) token bypasses team checks (mirrors existing pattern).
- [ ] Token revocation: `mcp.auth.revoke_token(token_id)` flips `revoked=1`. Token verifies fail thereafter.
- [ ] Test: `test_token_inherits_team_member_role`, `test_token_cannot_exceed_user_access`, `test_revoked_token_rejected`, `test_expired_token_rejected`, `test_token_with_wrong_scope_rejected`.

### Files

- `press/mcp_server/auth.py` — `verify_token`, `revoke_token`.
- `press/mcp_server/server.py` — every tool entry calls `verify_token` then `frappe.set_user`.
- `press/mcp_server/test_permission_parity.py` — 5 tests above.

---

## Sub-objective 4c — Vue Developer Tools › MCP Panel

### Why

User said: "added mcp log or something on Vue dashboard under developer tools tab and have mcp access token". Operators need a single place to see what's happening, who has tokens, and revoke them on the fly.

### DoD

- [ ] New tab "Developer Tools › MCP" in the Vue dashboard at route `/dashboard/dev-tools/mcp`. Visible only to users with `Team Member.press_role` granting MCP access (a new flag `can_manage_mcp` on `Press Role`).
- [ ] **Active Tokens** section: table of the user's own tokens (or all team tokens if user is team admin). Columns: Label, Scope (truncated, expandable), Issued, Expires, Last Used, Status (Active/Expired/Revoked), Action button (Revoke).
- [ ] **Recent Calls** section: live-ish (manual refresh + auto-poll every 10s) feed of the last 200 MCP calls. Columns: Timestamp, Token Label, User, Tool, Target (e.g., "Release Group: bench-X"), Status (Success/PermissionError/ValidationError), Duration. Click row → expands to show full request/response payload.
- [ ] **Issue New Token** button: opens dialog with fields Label, Scope (multi-select from tool catalog), TTL slider (1m–24h, default 60m). Asks for current password (re-auth to issue). On success, shows the plaintext token in a "Copy this — you won't see it again" panel.
- [ ] All UI strings consistent with existing dashboard tone.
- [ ] Test: build passes; manual smoke test on `demo.mvpstorm.com`.

### Files

- `dashboard/src/pages/DevToolsMcp.vue` — new page.
- `dashboard/src/router.js` — register the route.
- `dashboard/src/components/mcp/IssueTokenDialog.vue` — issue dialog.
- `dashboard/src/components/mcp/TokenList.vue` — active tokens table.
- `dashboard/src/components/mcp/CallLog.vue` — recent calls table.
- New whitelisted methods: `press.mcp_server.dashboard.list_my_tokens()`, `list_my_calls(limit=200)`, `revoke_token(name)` (different from auth.revoke_token — UI wrapper).

---

## Sub-objective 4d — Admin Panel Surface

### Why

User said: "this will integrate with team role permission… and admin panel". The team has an existing Admin Panel concept (per CLAUDE.md "Admin Panel surface"). System admins need a global view across teams.

### DoD

- [ ] New section in the Admin Panel: "MCP Tokens (Global)" — visible only to users with `Press Settings.is_system_user` truthy.
- [ ] Lists ALL tokens across ALL teams. Filters: team, user, scope, status, label substring.
- [ ] Bulk-revoke action.
- [ ] Drill-down: click a token → full call log for that token (last 1000 calls).
- [ ] Audit log of admin actions (who revoked which token, when).
- [ ] Permission integration: requires `Press Role.is_global_mcp_admin` flag (new flag, defaults to 0).
- [ ] Test: `test_admin_panel_lists_all_team_tokens`, `test_admin_panel_blocked_for_non_admin`, `test_bulk_revoke_emits_audit`.

### Files

- `dashboard/src/pages/AdminPanelMcp.vue` — new admin page.
- `dashboard/src/router.js` — register route under `/admin/mcp` (mirror existing Admin Panel routes).
- `press/mcp_server/admin.py` — `list_all_tokens()`, `bulk_revoke(token_names, reason)` whitelisted with `@allow_only_system_user` decorator.
- `press/mcp_server/test_admin.py` — 3 tests above.

---

## Permission Model Integration (cross-cutting)

### `Press Role` flag additions

Two new boolean flags on `Press Role` doctype (extends the 18-flag system from MEMORY.md lesson #128):

1. `can_manage_mcp` — user can issue/revoke their own MCP tokens via the Vue Developer Tools panel. Default: ON for "Member" role, OFF for "Viewer".
2. `is_global_mcp_admin` — user can see + revoke MCP tokens across ALL teams via the Admin Panel. Default: OFF for everyone; admin enables manually for trusted system admins.

### Token authorization flow per call

```
Agent → MCP /api/method/press.mcp_server.handle
        Authorization: Bearer <token-plaintext>
        Body: { tool: "clone_bench", args: {...} }
              ↓
press.mcp_server.handle
              ↓
        verify_token(plaintext, tool_name="clone_bench")
              ↓ resolves to User
        frappe.set_user(user)         ← from this point, all
                                        permission checks see the
                                        agent as the human user
              ↓
        dispatch_tool("clone_bench", args)
              ↓ calls
        clone_release_group(...)      ← Objective 1 method, runs
                                        with correct user identity
              ↓
        record MCP Call Log entry
              ↓
        return {ok, data, error?}
```

---

## Why this changes ordering

The original plan had Objective 4 as the LAST objective (after locks). With this amendment, Objective 4 grows enough that it's worth splitting:

- **Objective 4a (Auth + Token persistence)** — ship first. Even without other tools, this delivers value: any future internal tool can use the token system.
- **Objective 4b (Permission inheritance)** — ship second.
- **Objective 4c (Vue Developer Tools panel)** — ship third.
- **Objective 4d (Admin Panel)** — ship last.

Each sub-objective remains independently testable and shippable. The original order (1 → 2 → 3 → 4) is preserved at the top level.

---

## Risks & Mitigations

1. **Password-based token issue is a privilege escalation surface** — if the agent runs on a compromised machine, a stolen password gives token issue. Mitigation: short TTLs (default 60 min), brute-force IP block, audit log every issue.
2. **Token leak in logs** — never log plaintext tokens. The dashboard call log shows the token's *label*, not the value. The hashed value never leaves the DB.
3. **Stale tokens after password change** — by design, password change does NOT auto-revoke existing tokens (they're independent). Operators manually revoke if compromise suspected. Document this in the panel.
4. **Vue panel auto-poll load** — every 10s × N panel viewers × small query = manageable. Rate-limit to one poll per 10s per user.
5. **Press Role flag count growth** — already 18 flags per lesson #128; adding 2 more is not a structural concern, but document the new flags in `docs/wiki/02-frontend-development/team-role-integration.md` (or wherever role flags are catalogued).

---

## Out of scope (still)

- OAuth2/OIDC token issue flow — out. We use Frappe's existing password-auth path. Future enhancement.
- Per-team MCP server isolation — out. One MCP endpoint serves all teams; isolation comes from token scoping.
- MFA on token issue — out. Trust the password for now; can layer MFA later via Frappe's existing MFA hooks.
- Token rotation API — out. Operators just issue a new token and revoke the old.

---

## Anchors (where this lands in code)

| Sub-objective | New files                                           | Modified files                                         |
| ------------- | --------------------------------------------------- | ------------------------------------------------------ |
| 4a            | `press/mcp_server/auth.py`, 2 new doctypes          | -                                                      |
| 4b            | `press/mcp_server/test_permission_parity.py`        | `press/mcp_server/server.py` (every tool wrapper)      |
| 4c            | 4 Vue files + 3 new whitelisted methods             | `dashboard/src/router.js`                              |
| 4d            | 1 Vue file + `press/mcp_server/admin.py` + tests    | `dashboard/src/router.js`                              |
| Cross-cutting | -                                                   | `press/doctype/press_role/press_role.json` (+2 flags)   |
