# Infra Control Panel: Plan 2 direction (REVISED 2026-06-05)

## Decision: enhance the EXISTING server pages, do NOT build a new page

After reviewing the live dashboard (`/dashboard/servers` and `/dashboard/servers/<server>/groups`), the existing Press server pages already provide ~the structure we want. Plan 2 is therefore an ENHANCEMENT of existing components, not a new `InfraBoard.vue` page.

## What already exists (reuse, do not rebuild)
- `dashboard/src/objects/server.js` : the `/servers` list (columns: Server, Status, App/DB Plan, Region) + the server `detail` with tabs: Overview, Analytics, Bench Analytics, and the Benches/Groups tab (the Level-2 bench list under a server).
- `dashboard/src/components/server/ServerOverview.vue` : already renders `Progress` bars + opens `StorageBreakdownDialog` (disk). Some metric UI is already here.
- `dashboard/src/components/ObjectList.vue` : Frappe-UI `ListView` driven list. LIST-ONLY today (no card/grid toggle).

## The three enhancements (the only new work)
1. **Metrics on the lists.** Add CPU% / Mem% / Disk% columns to the servers list (`server.js` `list.columns`) and to the benches/groups view. Values come from the new `press.api.infra_board.get_infra_tree` (host + per-bench) or the existing `press.api.server.usage` / `Server.get_storage_usage`. Render as a small value + usage bar (amber >=75%, red >=90%), matching the approved prototype `docs/infra-board/press-control-panel.prototype.html`.
2. **Card / List / Line view toggle.** `ObjectList.vue` (or a thin wrapper) gains a Cards | List segmented toggle. Cards = the prototype's grid (status dot + metrics footer); List/Line = the dense table (current). Apply on the servers list AND the benches view.
3. **Per-service drill + control + logs** (the deeper Level-3, optional in this phase). On a bench, surface its services from `press.api.bench.get_processes` with state badges + the per-service `service_action` (start/stop/restart, already built in Plan 1) + the existing Log Browser (`press.api.log_browser.get_log` + `LogViewer.vue`) in a drawer. This is the only part that is genuinely new UI; metrics + toggle (1 + 2) are the immediate asks.

## Files to touch (Plan 2)
- `dashboard/src/objects/server.js` : add metric columns; (optionally) a `bench` object or reuse `get_infra_tree` for the benches view.
- `dashboard/src/components/ObjectList.vue` : add the Cards/List view-mode toggle + a card renderer (token-styled, Sanad UI).
- Reuse (no change): `ServerOverview.vue`, `StorageBreakdownDialog.vue`, `LogViewer.vue`, `press.api.infra_board.*` (Plan 1, shipped), `press.api.bench.get_processes` / `service_action`.

## Backend status (Plan 1, SHIPPED 2026-06-05)
`get_infra_tree`, `host_probes`, `service_action` are live on `cloudflare-dns` with 9 green tests (pushed). The frontend enhancement consumes them; no further backend needed for metrics + toggle, except wiring per-bench disk/cpu if `get_infra_tree` should carry them (currently it carries memory/agent/ssh per server + per-bench service status; add per-server disk via `get_storage_usage` and per-bench cpu/mem from docker stats if the cards need them).

## Reference
- Approved prototype: `docs/infra-board/press-control-panel.prototype.html` (live: sanad-preview /sanad-protos/press-control-panel.html)
- Capability audit: `docs/infra-board/2026-06-05-capability-audit.md`
- Backend plan (done): `docs/infra-board/2026-06-05-plan-1-backend.md`
