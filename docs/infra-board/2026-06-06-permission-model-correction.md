# Infrastructure: permission-model correction (2026-06-06)

Supersedes the spec's R6 ("System-Manager only"). The panel MUST align with the Press team/user permission model, not be blanket admin. Decided: **team-scoped for Press resources, role-gated for external hosts.**

## The model
- **Servers nav (Press benches/sites/services)** - **team-scoped**. A team sees and controls only the servers/benches/services it OWNS, via the existing Press `@protected(...)`/team-ownership checks (same scoping the dashboard server list already uses). System Manager sees and controls all.
- **Infrastructure nav (external managed hosts)** - **role-gated**. External hosts are not team-owned, so they are gated by a role (System Manager, or a dedicated `Press Infra Manager` role). This is still permission-aligned (a role check, not a bypass).

## What changed already (done, pushed)
- `press/api/bench.py:service_action` - removed the `frappe.only_for("System Manager")` gate; it is now gated only by `@protected("Bench")`, so the team that owns a bench can start/stop/restart its own services (System Manager owns all via @protected). 9 Plan-1 + 5 infra tests still green. Commit `7c988b5db`.

## REQUIRED before the team-facing panel ships (Plan 2b) - do deliberately
`press/api/infra_board.py:get_infra_tree` is still `frappe.only_for("System Manager")` (a safe interim: admin-only, no leak, but no team self-service on the new panel - which is not built yet). Before the Infrastructure/Servers UI is team-facing it MUST become team-scoped:

1. **Scope reads by team.** Replace `_all_servers()` (all Active servers) with: System Manager -> all servers; otherwise -> only `Server` rows where `team == get_current_team()` (mirror `press.api.server.all`'s team filter). Managed hosts are included ONLY for System Manager / Infra Manager.
2. **CRITICAL - per-team cache key.** The tree is Redis-cached under the single key `infra_board:tree`. If reads are team-scoped but the cache stays global, **team A would be served team B's cached tree** - a cross-team data leak. The cache key MUST include the scope: `infra_board:tree:<team-or-'admin'>`. This is the single most important part of this change.
3. **Update the gate test.** `test_get_infra_tree_requires_system_manager` asserts `only_for("System Manager")` is called; it must change to assert the team-scoped behaviour (non-admin path returns only the team's servers + no managed hosts, and uses the per-team cache key).
4. **host_unit_action / get_host_log (managed hosts, Plan 2a Task 8)** stay role-gated (System Manager / Infra Manager) - external hosts are not team-owned. The Plan-2a doc's `frappe.only_for("System Manager")` on those is correct as written.

## Why interim is safe
Leaving `get_infra_tree` admin-only for now does NOT leak (it is more restrictive, not less) and the new merged panel is Plan 2b, not yet shipped. Teams already control their own bench services today through the existing Processes tab (which calls the now-relaxed `service_action`). The team-scoping above lands as part of Plan 2b with the per-team cache key.
