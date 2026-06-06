# Plan 2b Infrastructure Dashboard - progress handover (2026-06-07)

## Status: 6 of 13 tasks DONE + pushed. The list view + control plane are built. NOT YET DEPLOYED.

Branch `Veela-Beauty/press` `cloudflare-dns` HEAD `f2b8ea04e51`. All source committed source-only (the built bundle is committed separately at T12). The live `/dashboard/infrastructure` still serves the OLD bundle until the T12 build.

## Done (commits)
- T0 scaffold route `/infrastructure` + sidebar nav item + stub page (`623ee9a`)
- T1 `infra-derive.js` pure view-model (partition/nodeDot/loadState/isDown/uDot/stateLabel/stateTheme/controllable/issues/overloaded/summary) + **14 vitest tests** (`f2e31d2`)
- T2 `infra-api.js` resource wrappers (useInfraTree/unitAction/unitLog/testConnection/addHost) (`cae7c68`)
- T3 atoms MeterBar/StatusBadge/SummaryCards (`a7ce8dd`)
- T4 `ServerList.vue` (summary cards, status+type filters, search, sortable headers, paginate, table/cards) (`1abe34c`)
- T5 `InfraDashboard.vue` shell (nav toggle Servers/Infrastructure, breadcrumb, List/Cards toggle, 15s poll, 3-level routing) (`96a04b3`)
- T6 `HostDetail.vue` + `UnitTable.vue` - **live control**: restart/stop/kill via `host_unit_action` with confirm-for-destructive + optimistic + toast + busy spinner; plain hosts watch-only; press servers read-only benches + "Open server page" link (`f572f4e`)

All files under `dashboard/src/pages/infrastructure/`. The shell already stores `drawerUnit` (ref) on the Logs emit - T7 just renders the drawer bound to it.

## Remaining (resume from the plan: docs/infra-board/2026-06-06-plan-2b-infrastructure-dashboard.md)
- **T7 UnitDrawer.vue** - Logs (via `get_host_log(host, _id, tail)` -> string[]) + Inspect (kv from the unit dict) + Stats (honest "not collected in v1"); bind to the shell's `drawerUnit` ref; action bar mirrors UnitTable.
- **T8 NeedsAttention.vue** - triage panel (issues()+overloaded(), top 4, one-click Restart) composed ABOVE ServerList in the shell for the infra nav; Alerts panel best-effort from Watch Tower (hide if absent, no fake data).
- **T9 AddHostWizard.vue** - 3-step Dialog: form -> add_managed_host + test_connection -> success; wired to the shell's onAdd().
- **T10** confirms/toasts/optimistic-reload polish + skeleton + empty/loading states.
- **T11** Playwright human-flow (rule #9): spin the disposable docker test-host (reuse the Task-10 smoke harness: alpine sshd+socat+CA+victim), register via add_managed_host, then drive the UI step-by-step (open /infrastructure -> see host -> drill -> open logs -> restart -> toast -> verify Infra Action Log), video+trace, publish to ~/docs/tests/press/infrastructure-dashboard/.
- **T12** `cd dashboard && yarn build` (deploys to press/public/dashboard + www/dashboard.html) -> commit the bundle -> hard-refresh + verify live.

## Key facts / learnings for the next session
- **Light mode only** (dashboard has no dark mode). Use frappe-ui Tailwind utilities (inherit the Accurate-Systems blue rebrand). De-slop: no emoji, 7px geometric dots, monospace for ids/ports/metrics, hairline borders.
- **Backend reality:** managed hosts have a FLAT `units[]` (NO stack/compose group level - the prototype's stacks were aspirational). Press servers = server->bench->services. Managed unit control is docker-only (`_id` present); systemd watch-only.
- **Build/commit discipline:** commit SOURCE ONLY per task; the bundle (`press/public/dashboard`, `www/dashboard.html`) is TRACKED but built+committed ONCE at T12. Verify compile per task with a THROWAWAY build: `cd dashboard && yarn vite build --outDir /tmp/dash-check --emptyOutDir` (does NOT touch the live bundle). Orphan components (not yet imported by the routed page) need a temp-import into InfraDashboard.vue + build + `git checkout` revert to verify.
- **vitest** needs a dedicated `dashboard/vitest.config.js` (the frappe-ui vite plugin breaks vitest's default config load). Run `yarn vitest run <name>`.
- `Header` is NOT global (explicit `import Header from '../../components/Header.vue'`); `Breadcrumbs`/`Badge`/`Card` ARE global. `toast` from `vue-sonner`. `Dialog`/`Button`/`FormControl`/`createResource` from `frappe-ui`. `useRouter` from `vue-router`. Reactive busy tracking: use an object map, not a Set (Vue can't track Set mutations).
- **Push flow:** commit on press-ctrl container -> `git bundle` -> throwaway worktree off `press_local` -> merge origin -> push (NEVER push from press-ctrl). Per-task.
- Plan source of truth: `docs/infra-board/2026-06-06-plan-2b-infrastructure-dashboard.md` (in the repo) and `~/docs/plans/infrastructure/2026-06-06-plan-2b-infrastructure-dashboard.md`.
- Prototype (visual spec): `~/docs/prototypes/press-infrastructure.html` (the de-slopped notifications + server-maintenance prototypes are siblings).
