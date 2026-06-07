# Unified Infrastructure View - Design Spec

**Date:** 2026-06-07
**Status:** Approved (design), pending implementation plan
**Scope:** Dashboard only (`dashboard/src/pages/infrastructure/*`). Backend, native Servers pages, and Gate-0 logic are untouched.

## Goal

Replace the in-page `Servers | Infrastructure` toggle with ONE list that shows Press servers and managed Docker/hosts together, so "Infrastructure" is a single monitoring surface and the duplicate read-only Servers mirror is removed.

## Background: the duplication

Today the same Press servers appear in two UI places:

1. Left-nav **Servers** -> `/servers` -> the full upstream Press server management (provision, plans, benches; read-write). Defined in `dashboard/src/objects/server.js` + `components/NavigationItems.vue:120`.
2. Left-nav **Infrastructure** -> `/infrastructure` -> `InfraDashboard.vue`, which has its OWN `nav` toggle (`InfraDashboard.vue:152`, `ref('infra')`):
   - `nav==='infra'` -> managed hosts (drill -> units -> control -> logs).
   - `nav==='servers'` -> Press servers + benches, **read-only** (a mirror built from `get_infra_tree`).

The backend already returns one merged tree: `get_infra_tree().servers` mixes both kinds, distinguished by `n.kind === 'managed'` (`infra-derive.js:7`, `isManaged`). Only the UI splits it, via `partition()` (`infra-derive.js:8`) feeding a `navNodes` computed (`InfraDashboard.vue:169`). The split is the duplication.

## Decisions (from brainstorming)

- **Unify scope:** merge the in-page toggle into one list. KEEP the native left-nav Servers page for deep management. (Not retiring the Servers nav; not making Infrastructure managed-only.)
- **List layout:** one flat, sortable list with a **Type badge** (Press / Managed) and a **Type filter** chip.
- **Row click:** opens a **type-aware detail drawer** (slide-over), not a full-page drill.
  - Managed host -> the existing control panel (units, start/stop/restart/kill, logs).
  - Press server -> READ-ONLY status (benches/services + metrics) with one button, "Open full server page" -> `/servers/<name>`.

## Design

### 1. One flat list (remove the toggle)
- `InfraDashboard.vue`: delete `nav`, `setNav`, and the toggle markup (lines ~51-68, 152, 187-191). `navNodes` -> just `allNodes` (`tree.data?.servers || []`). Breadcrumb label is always "Infrastructure".
- `ServerList.vue`: collapse the two per-`nav` column templates (`v-if="nav==='servers'"` / `v-if="nav==='infra'"`) into ONE row template that renders every node, with a Type badge column. The `nav` prop is removed.

### 2. Type badge + filter
- New **Type** column rendering a badge: `Press` (neutral) or `Managed` (blue), from `isManaged(node)`.
- A filter chip group **All / Press / Managed** at the top of the list (replaces what the toggle did). The existing Status filter and the managed-only docker/plain "Type" segment stay, but the docker/plain segment is relabeled to avoid clashing with the new Press/Managed Type badge (call it "Runtime: docker / plain", and only show it when the Managed filter is active or mixed).

### 3. Unified metric accessor
Press and managed nodes expose metrics on different paths:
- Press: `node.host.cpu.used_pct`, `node.host.memory.used_pct`, `node.host.disk.used_pct`.
- Managed: `node.metrics.cpu`, `node.metrics.mem`, `node.metrics.disk`.

Add a pure helper in `infra-derive.js`, e.g. `cpuPct(node) / memPct(node) / diskPct(node)`, that reads the right path by `isManaged(node)` and returns a number or `null`. The single row template uses these so one `<MeterBar>` set covers both kinds. Unit-tested in `infra-derive.test.js`.

### 4. Type-aware detail drawer (replaces the drill)
- `InfraDashboard.vue`: replace `path` (`server`/`group`) + `current` + `drill()` + the LEVEL-2/LEVEL-3 blocks with a single `detailNode` ref. Clicking a row sets `detailNode = node`.
- New `HostDrawer.vue` (slide-over) renders by `isManaged(node)`:
  - **Managed** -> reuse `HostDetail` + `UnitTable` + `UnitDrawer` (units list with start/stop/restart/kill + logs) inside the drawer.
  - **Press** -> read-only: server health + metrics + its benches/services list (from the node's existing children), and a single primary `Button` "Open full server page" -> `router.push('/servers/' + node.name)`. No control actions, no rebuilt management.
- The drawer closes back to the list (no breadcrumb levels).

### 5. Needs-attention spans both kinds
`NeedsAttention` currently takes managed nodes only (`issues(infraNodes)` in `infra-derive.js:36`). Extend the attention set to also include Press servers whose `health === 'down'` (or `'unknown'`), so a down Press server surfaces in the same strip. Show the strip whenever there is at least one attention item of either kind.

### 6. Gate-0 banner unchanged
The Gate-0 preflight banner is about managed hosts (they cannot connect without Gate 0). Keep it; show it when at least one managed host exists AND `gate0.ready` is false. It is no longer gated behind `nav==='infra'` (that variable is gone) but its condition is otherwise identical.

## Files

| File | Change |
|---|---|
| `dashboard/src/pages/infrastructure/InfraDashboard.vue` | Remove `nav`/`setNav`/toggle; `navNodes`->`allNodes`; replace drill `path` with `detailNode` drawer state; mount `HostDrawer`. |
| `dashboard/src/pages/infrastructure/ServerList.vue` | One row template for both kinds; add Type badge column + All/Press/Managed filter; drop the `nav` prop; relabel the docker/plain segment to "Runtime". |
| `dashboard/src/pages/infrastructure/HostDrawer.vue` | NEW slide-over; renders managed control vs Press read-only by `isManaged`. |
| `dashboard/src/pages/infrastructure/infra-derive.js` | Add `cpuPct/memPct/diskPct` accessors; extend the attention set to include down Press servers. |
| `dashboard/src/pages/infrastructure/infra-derive.test.js` | Tests for the metric accessors + the widened attention set. |

`HostDetail.vue`, `UnitTable.vue`, `UnitDrawer.vue`, `NeedsAttention.vue` are reused (small prop tweaks at most). `infra-api.js` and all backend code are untouched.

## Out of scope

- `get_infra_tree` and any backend change.
- The native `/servers/*` pages and the left-nav "Servers" item (kept as-is).
- Provisioning, Gate-0 provisioning, host onboarding.

## Definition of Done

- [ ] Infrastructure shows ONE list with both Press and managed nodes; no in-page toggle.
- [ ] Each row has a Type badge; the All/Press/Managed filter works.
- [ ] CPU/Mem/Disk render for both kinds via the shared accessors.
- [ ] Clicking a managed host opens the drawer with working units control + logs.
- [ ] Clicking a Press server opens a read-only drawer with an "Open full server page" link to `/servers/<name>`.
- [ ] Needs-attention surfaces both a down managed host and a down Press server.
- [ ] Gate-0 banner still appears when managed hosts exist and Gate 0 is not ready.
- [ ] `infra-derive.test.js` passes (accessors + attention set); existing vitest stays green.
- [ ] Verified live on press-ctrl after `yarn build` (full-width, filter, drawer for each type).

## Before / After

**Before:** two left-nav entries for servers (Servers, Infrastructure) PLUS a third Servers/Infrastructure toggle inside Infrastructure; Press servers shown twice (native page + read-only mirror); managed hosts drill through breadcrumb levels.

**After:** Infrastructure is one flat list of all servers with a Type badge + filter; a click opens a type-aware drawer (managed control vs Press read-only + deep-link); the native Servers nav stays for deep Press management. One monitoring surface, no mirrored Servers tab.
