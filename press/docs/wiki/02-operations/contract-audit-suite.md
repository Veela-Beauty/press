# Contract-Audit Suite

Five scripts that enforce the implicit contracts between the Press backend
and the Vue dashboard. Each catches a class of bug we've hit multiple times
since 2026-05-10. The suite ships as part of `press.test_auth` — `bench
run-tests --module press.test_auth` fails CI if any contract has drifted.

---

## Why these exist

Press is fork-based and ships fast. Every time we add a whitelisted method,
wire a Vue button, or add an MCP tool, three or four places need to stay in
sync. Documentation said "MUST stay in sync"; humans forgot. The result was
a string of identical "non-System team users force-logged-out" incidents:

| Date | Missing piece | Triggered by |
|------|----------------|--------------|
| 2026-05-10 | `deploy_candidate_build.*` not in `ALLOWED_WILDCARD_PATHS` | Marco's deploy |
| 2026-05-18 | `bench_dev_watch.*` + `bench_code_health.*` not in allowlist | Marco's Launch Code Server click |
| 2026-05-19 | `release_group_clone.*` + `bench_vscode.*` + `press.ai.api.*` not in allowlist; VSCode caller had wrong dotted path; `Bench Shell Log` blocked non-System users; 5 Vue→Python calls pointed at non-existent methods | Ahmed's first day on the team |

Each incident has the same recipe: a feature ships, the new method+wiring
work for System users (developers test as Administrator), the gap is
invisible until a real Website User clicks the button. **The suite makes
those gaps visible in CI instead of in production.**

---

## The 5 audits

| # | Script | Catches |
|---|--------|---------|
| 1 | `scripts/audit_dashboard_allowlist.py` | Vue caller is not covered by `ALLOWED_WILDCARD_PATHS` in `press/auth.py` |
| 2 | `scripts/audit_dashboard_method_exists.py` | Vue caller's dotted path doesn't resolve to a real Python symbol |
| 3 | `scripts/audit_dashboard_whitelisted.py` | The target method exists but lacks `@frappe.whitelist()` |
| 4 | `scripts/audit_audit_log_inserts.py` | `Bench Shell Log` insert must keep `ignore_permissions=True` |
| 5 | `scripts/audit_mcp_catalog_parity.py` | `press/mcp_server/tools.py` and `dashboard/src/components/mcp/_tool_catalog.js` list the same MCP tools |

Each script is independently runnable for local dev:

```bash
cd /home/eslam/data/erpnext-app-repos/press_local
python3 scripts/audit_dashboard_allowlist.py
python3 scripts/audit_dashboard_method_exists.py
python3 scripts/audit_dashboard_whitelisted.py
python3 scripts/audit_audit_log_inserts.py
python3 scripts/audit_mcp_catalog_parity.py
```

Combined runtime <2s. Exit code 0 = clean.

`--print` (where supported) lists every caller + which rule covers it —
useful when reviewing a PR that changes the call surface.

---

## The wrapper test

```bash
sudo -u frappe bash -lc 'cd /home/frappe/frappe-bench && \
  bench --site demo.mvpstorm.com run-tests --module press.test_auth'
```

5 tests, one per audit. Wraps each script in a subprocess and asserts
exit 0. A failure dumps the script's stdout + stderr so the CI log is
self-explaining.

The wrapper file: `press/test_auth.py`.

---

## When you're adding a new feature

1. Add the whitelisted method on the backend.
2. Wire the Vue caller.
3. Add `/api/method/<dotted.path>.` to `ALLOWED_WILDCARD_PATHS` in
   `press/auth.py` if it's a new module.
4. Run `python3 scripts/audit_dashboard_allowlist.py` locally — exits 0
   means the allowlist is right.
5. Run `python3 scripts/audit_dashboard_method_exists.py` — exits 0
   means the dotted path actually resolves.
6. If MCP: add to `press/mcp_server/tools.py` AND
   `dashboard/src/components/mcp/_tool_catalog.js` — the parity audit
   enforces both.
7. Push. CI runs the wrapper test and stops the merge if anything drifted.

---

## The exclusion-list discipline

`scripts/audit_dashboard_method_exists.py` has a `KNOWN_DYNAMIC` set for
callers that legitimately can't be statically resolved (e.g. dotted path
built from a runtime variable). **As of 2026-05-19 this set is empty()**.

If a future change makes the audit fail on a path that genuinely cannot
be resolved statically, add the path to `KNOWN_DYNAMIC` with a comment
naming why. **Never use this list to defer real bugs** — every entry
without a justification is a deferred ticket pretending to be code.

The same discipline applies to `audit_audit_log_inserts.py`'s
`AUDIT_LOG_INSERTS_REQUIRING_BYPASS` (currently only `Bench Shell Log`).
If you find a second audit-log doctype that needs the same
`ignore_permissions=True` treatment, add it there with a comment.

---

## What each script does NOT catch

These contracts are NOT enforced (yet):

- **Param-shape drift.** If Vue sends `{site: "x"}` but the method expects
  `{site_name: "x"}`, the dispatcher returns 400 — but the audit only
  checks that the method exists, not that the param names match. The MCP
  Test Tool Call form's JSON Schema partly addresses this for MCP tools;
  dashboard callers are still on trust.
- **Return-shape drift.** If the backend returns a dict and Vue treats it
  as a string (or vice versa), no audit catches it. The Clone Site
  `[object Object]` bug was this — fixed manually after the fact.
- **Permission-row coverage on user-facing doctypes.** The Bench Shell
  Log audit is narrowly scoped to the one fix. The wider problem (any
  System-Manager-only doctype written from a user-facing flow) is not
  enforced.
- **MCP `args_schema` ↔ implementation drift.** A tool can declare
  `required_args: [foo]` and the Python method can rename to `bar`
  without the audit noticing.

Each of these is a candidate for a future audit script. Add one when the
underlying bug hits a second time.

---

## Files

- `scripts/audit_dashboard_allowlist.py`
- `scripts/audit_dashboard_method_exists.py`
- `scripts/audit_dashboard_whitelisted.py`
- `scripts/audit_audit_log_inserts.py`
- `scripts/audit_mcp_catalog_parity.py`
- `press/test_auth.py` — wrapper test
- `press/docs/wiki/lessons-learned.md` — the recurring incidents and
  the rule "when the same documented mistake happens 3+ times, write
  the linter instead of writing the doc"

## Related

- [Auth allowlist memory](../../../../../../.claude/projects/-home-eslam/memory/feedback_press-auth-allowlist.md) — the operator playbook that predates the audit
- [Frappe Password fields wipe on save](../../../../../../.claude/projects/-home-eslam/memory/feedback_frappe-password-fields-wipe-on-save.md) — Sister trap, fixed via `before_save` hook on Press Settings (2026-05-19)
