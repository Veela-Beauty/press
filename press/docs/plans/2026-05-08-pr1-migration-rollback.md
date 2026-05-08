# PR #1 Migration + Rollback Plan

**PR**: https://github.com/Veela-Beauty/press/pull/1 (`feat/clone-bench-and-site` → `cloudflare-dns`)
**Date**: 2026-05-08
**Status**: pre-merge — read this BEFORE merging.

---

## Why this doc exists

PR #1 adds 6 new doctypes, 5 Custom Fields, and 4 hourly scheduler jobs. First production migrate will create them all at once. This doc:
1. Lists the schema additions (so a DBA can audit before merge).
2. Calls out the order migrate runs them.
3. Documents the rollback path if a migration step fails.
4. Notes the **commit-hygiene recommendation** for the merge itself.

---

## Schema additions

### New DocTypes (6)

| DocType | Purpose | Tables created |
|---|---|---|
| **Press Lock** | Advisory lock state on Site / Release Group (Obj 3) | `tabPress Lock` |
| **Press MCP Token** | Hashed MCP access tokens with scope + resource allowlist (Obj 4a, 4e) | `tabPress MCP Token` + `__Auth` row per token |
| **Press MCP Auth Attempt** | Brute-force tracking on `issue_token` (Obj 4a) | `tabPress MCP Auth Attempt` |
| **Press MCP Call Log** | Per-MCP-call audit log with hash chain (Obj 4b, 7) | `tabPress MCP Call Log` |
| **Press MCP Admin Action** | Admin actions on tokens (revoke, approve, reject) (Obj 4d, 5) | `tabPress MCP Admin Action` |

All have `permissions` restricted to System Manager. Indices on `target_doctype + target_name`, `token_prefix`, `expires_at`, `tool`, `user`, `creation` for query performance.

### Custom Fields via fixture (5)

Applied via `fixtures/custom_field.json` on `bench migrate`:

| dt (target DocType) | fieldname | fieldtype | Default |
|---|---|---|---|
| Release Group | `cloned_from` | Link → Release Group | — |
| Release Group | `clone_lifetime` | Select (sandbox/persistent) | persistent |
| Release Group | `clone_expires_at` | Datetime | — |
| Press Settings | `mcp_script_repo_allowlist` | Code (JSON list) | `[]` |
| Press Settings | `mcp_script_timeout_max_seconds` | Int | 600 |

**Hash-chain `prev_hash`/`row_hash` on Press MCP Call Log**: starts as "GENESIS" string for the first row. No pre-existing rows because the doctype is new — no risk of broken chain at first migrate.

### Scheduler events added to `hooks.py` (4 hourly jobs)

```python
"hourly": [
    # ... existing entries ...
    "press.cleanup.sandbox_cleanup.expire_sandbox_release_groups",
    "press.cleanup.expired_locks.cleanup_expired_locks",
    "press.cleanup.expired_auth_attempts.cleanup_expired_auth_attempts",
    "press.cleanup.expired_mcp_call_logs.cleanup_old_mcp_call_logs",
],
```

These are no-ops on first run (no rows to clean up yet).

---

## Migrate order (informational)

Frappe migrate processes in this order:
1. **Schema sync** — all 6 new doctype tables created in MariaDB.
2. **Custom Field fixtures** — 5 fields appended to existing doctypes.
3. **Scheduler hooks reload** — 4 new hourly entries registered.
4. **Patches** (if any) — none in this PR.
5. **after_migrate hooks** — none in this PR.

Total time on demo.mvpstorm.com: typically 30-60s. No data backfill, no row migration.

---

## Pre-merge checklist (operator)

Before merging PR #1 to `cloudflare-dns`:

- [ ] **Snapshot press-ctrl** per the stability runbook: `sudo -u frappe /home/frappe/scripts/lib.sh snapshot pre-pr1`
- [ ] **Confirm bench-update-safe is green**: `sudo -u frappe bench-update-safe --skip-update --no-restart`
- [ ] **Schedule a maintenance window** — even though migrate is fast, scheduler restarts cause 5-10s of agent downtime.

After merging:

- [ ] **Apply via bench-update-safe** (NEVER bare `bench update` — see press-ctrl-stability-runbook.md).
- [ ] **Verify the 6 new tables exist**: `bench --site demo.mvpstorm.com mariadb -e "SHOW TABLES LIKE 'tabPress MCP%'; SHOW TABLES LIKE 'tabPress Lock';"` — expect 5 tables (Press Lock, Press MCP Token, Press MCP Auth Attempt, Press MCP Call Log, Press MCP Admin Action).
- [ ] **Verify the 5 Custom Fields**: query `tabCustom Field` for the names listed above.
- [ ] **Populate `Press Settings.mcp_script_repo_allowlist`** (Frappe Desk: Press Settings doc → MCP Script Repo Allowlist field). Empty allowlist = no scripts can run; this is intentional fail-closed default. Suggested initial value: `["accurate-systems/wazin_mx", "Veela-Beauty/wazin_mx"]`.
- [ ] **Optional smoke test**: run [docs/plans/2026-05-08-pr1-smoke-test.md](2026-05-08-pr1-smoke-test.md) (E2E proven on press-ctrl 2026-05-08).

---

## Rollback

If migrate fails or post-merge smoke reveals a regression:

1. **Snapshot rollback** (per stability runbook):
   ```bash
   sudo -u frappe /home/frappe/scripts/rollback.sh
   ```
   This restores press-ctrl's filesystem + database to the pre-merge snapshot.

2. **Revert the merge commit on GitHub**:
   ```bash
   git checkout cloudflare-dns
   git revert -m 1 <merge-commit-sha>
   git push accurate-systems cloudflare-dns
   ```

3. **Re-deploy**: standard `bench-update-safe` from the reverted state.

### Partial rollback (specific objective)

If only ONE objective is problematic (e.g., Obj 5 risky-tools sandbox), the per-objective commits are clean enough to `git revert <commit>` individually. Each objective is self-contained:

| Objective | Commit range (approx) |
|---|---|
| Obj 1 (Clone) | `5b7825a2c4` ... `8b8ef02a5c` |
| Obj 2 (Move) | `476e6b56fb` ... `dd3dbab4ff` |
| Obj 3 (Locks) | `d949179` ... `060bd2cf83` |
| Obj 4a (MCP auth) | `4948756806` ... `a6c541dd62` |
| Obj 4b (MCP server + tools) | `fb1697ca20` ... `1813d7a2d6` |
| Obj 4c (Vue panel) | `53ef3ef413` ... `85ec18c98a` |
| Obj 4d (Admin panel) | `aa91f20583` ... `1281eceb59` |
| Obj 4e (resource scope + catalog) | `21f0dcc570` ... `4d2eb57b` |
| 16-fix review pass | `21f0dcc570` ... `8f5ae0aa62` |
| Obj 5 (risky tools) | (check with `git log --grep=Obj 5`) |
| Obj 9 (SSH tools) | (check with `git log --grep=ssh`) |
| Obj 6 (file ops) | (check with `git log --grep=fileops`) |
| Obj 7 (rate limit + audit chain) | (check with `git log --grep=hardening`) |
| Obj 8 (catalog completion) | (check with `git log --grep=Obj 8`) |
| Obj 10 (deploy flow) | `9214ddcd50` ... `55c78b6982` |
| Items 1-8 polish | (this PR's tail) |

---

## Commit-hygiene recommendation (for the reviewer)

The PR is currently **~70 commits**. Two options:

### Option A: Squash-merge (recommended)

GitHub UI → "Squash and merge" with a custom commit message:

```
feat: multi-agent MCP isolation stack (Obj 1-10 + hardening)

Adds clone bench/site (Obj 1), move site between RGs (Obj 2),
advisory locks (Obj 3), MCP server with tokens + risky-tools sandbox +
Vue panels + admin (Obj 4a-d), resource-scoping + 30-tool catalog
(Obj 4e), risky-tools approval workflow (Obj 5), SSH access tools
(Obj 9), file/config ops (Obj 6), rate limit + tamper-evident audit
chain (Obj 7), catalog completion (Obj 8), deploy/release flow tools
(Obj 10), and 8 follow-up hardening items.

84+ tests added across 9 modules, all passing on demo.mvpstorm.com.
See docs/plans/2026-05-07-multi-agent-press-isolation.md for the
overall plan and per-objective plans for details.
```

History becomes one reviewable commit; full history preserved in PR conversation.

### Option B: Keep individual commits via "Create merge commit"

Useful if you want `git blame` to point at the exact per-objective commit. Trade-off: reviewer sees ~70 commits in `git log`.

**Default to Option A** unless someone is doing forensic blame work and needs the granularity.

---

## Production readiness gates

After merge + deploy + smoke test:

- [ ] First 24h: monitor `Press MCP Call Log` row count growth — should be ~0 if no agents are using MCP yet.
- [ ] First 7d: monitor `Press MCP Auth Attempt` for unexpected entries.
- [ ] First 30d: confirm `cleanup_old_mcp_call_logs` runs (check Scheduler Logs for the function name).
- [ ] First 30d: run `audit_verify_chain` once and confirm `breaks: []` — proves the chain is intact across the first cleanup cycle.

If any gate fails: document in DEVLOG, file an issue, consider rollback.
