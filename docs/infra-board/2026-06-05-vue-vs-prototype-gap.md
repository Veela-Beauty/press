# Press server Vue vs approved prototype: gap analysis (2026-06-05)

Produced by a 6-reader + synthesis workflow over the live Press dashboard Vue and the approved prototype.

## Headline
Plan 2 is an enhancement, not a rebuild: ~70% of the prototype's data + components already exist in Press (ServerCharts metrics, LogBrowser/LogViewer logs, `get_processes` service table, plan/region columns). The genuinely new surface is the 3-level drill control panel (Servers > Benches > Services/Sites) with per-service inline restart/stop, a card/list toggle, an aggregate environment summary, and a right-side log drawer wired to Plan 1's `get_infra_tree` + `service_action` + `host_probes`. The existing `server.js` detail tabs, analytics, plans, regions, and all server actions MUST be kept, not dropped.

## Key discoveries (new vs my earlier read)
- A per-bench **Processes tab already exists** in `dashboard/src/objects/bench.ts` with `getProcessesTab` + `getProcessesColumns()` over `press.api.bench.get_processes`. The prototype's service table is mostly REUSE of these columns, not new.
- `bench.ts` carries a literal **`TODO: allow issuing supervisorctl commands`** (~line 259). Plan 1's `service_action` is exactly that backend; the inline Restart/Stop buttons resolve this TODO.
- The existing Log Browser (`LogBrowser/LogList/LogViewer.vue` + `log_browser.get_log`) is a **full page**, not a drawer. The prototype's drawer is a re-skin embedding `LogViewer.vue` -> wire, don't rebuild.
- `ObjectList.vue` is **table-only, no card/grid toggle** -> the Card view must be a sibling component with view-state in the parent, not an ObjectList option.

## KEEP: Press has it, prototype omitted it (do NOT drop)
- Full analytics suite (18 time-series metrics) - `ServerCharts.vue`/`ReleaseGroupCharts.vue`, `press.api.server.analytics` (Analytics + Bench Analytics tabs). Panel should LINK here, never replace.
- App/DB Server Plan columns + `planTitle()` - `server.js` list.columns[2-3].
- Region/cluster column (flag) + Region filter - list.columns[4], filterControls[1].
- Status filter (Active/Pending/Archived) + title search + creation-desc order.
- 13 detail tabs: Overview, Analytics, Bench Analytics, Sites, Benches, Snapshots, Jobs, Plays, Actions, Auto Scale, Firewall, Tags, Activity.
- Server lifecycle actions (reboot/rename/resize) - `ServerActions.vue` (tab 8).
- Options menu (View in Desk, View DB, Visit Server, Impersonate Owner) - detail.actions.
- Snapshots (EC2), Auto Scale, Firewall, Tags, Plays (Ansible), Jobs, Activity - whole categories with no prototype equivalent.
- Provisioning flows (New Server/Bench/Site/Snapshot), gated on status=Active.
- ObjectList rich features: multi-row select / bulk ops, row-action dropdowns, badge theming, Load-More pagination.

## BUILD: prototype has it, Press lacks it (the actual work)
| Feature | Level | Effort | Target |
|---|---|---|---|
| Aggregate env summary tiles (servers/benches/svc up-down/affected) | global | small | new `InfraOverview.vue`, data from `get_infra_tree` |
| 3-level drill + clickable breadcrumb | whole | large | new `objects/infrastructure.js` or `pages/Infrastructure.vue`, consumes `get_infra_tree` |
| Per-bench service table co-located WITH sites | L3 | medium | new `BenchControlPanel.vue`, reuse `getProcessesColumns()` |
| Per-service inline Restart/Stop/View-log buttons | L3 | medium | `BenchControlPanel.vue` -> `service_action` (resolves bench.ts TODO) |
| Bench-level Restart bench / Restart web only | L3 | small | `BenchControlPanel.vue` toolbar -> `service_action` |
| Right-side sliding log drawer + action bar | global | medium | new `LogDrawer.vue` embedding `LogViewer.vue` + `log_browser.get_log` |
| Card/List view-mode toggle | server+bench | medium | `ViewToggle.vue` + sibling card components (ObjectList has no toggle) |
| Instant CPU/Mem/Disk metric bars + threshold coloring | server+bench | small | `MetricBar.vue`, data from `host_probes` (live, distinct from chart history) |
| Health roll-up dots (downstream-aware) | all | small | `HealthDot.vue` + compute in `get_infra_tree` |
| Co-located sites at leaf (DB/files/reqs/HTTP) | L3 | medium | `BenchControlPanel.vue` sites section (reqs/HTTP need a light check) |
| Down-service hint banner | L3 | small | `BenchControlPanel.vue` conditional |
| Live auto-refresh pulse + polling (~12s) | global | small | header + TanStack Query `refetchInterval` on `get_infra_tree`/`host_probes` |
| Agent-extension log chips (journalctl/docker, disabled) | drawer | small | `LogDrawer.vue` disabled chips, backend deferred |

## WIRE ONLY: exists in both, just connect
- Per-service status/uptime/PID -> `bench.ts getProcessesColumns()` + `get_processes` (+ Plan 1 `get_infra_tree`).
- Log viewing -> `LogViewer.vue` + `log_browser.get_log` (embed, don't rebuild).
- Service control -> Plan 1 `service_action` (backend shipped).
- List + status badges + row-click nav + filters/pagination -> `ObjectList.vue` for the List view-mode.
- Instant CPU/Mem/Disk -> Plan 1 `host_probes`; link "history" to existing Analytics tab.
- Infra tree -> Plan 1 `get_infra_tree` (frontend drill is new, payload exists).
- Design tokens / light-dark -> existing dashboard frappe-ui theme; map the prototype's `hsl(var(--token))`.

## Plan 2 task list (additive; existing pages untouched)
1. Top-level "Infrastructure" nav + page consuming `get_infra_tree` (`objects/infrastructure.js` new, router, sidebar).
2. `InfraOverview.vue` (summary tiles + per-server cards/rows + `MetricBar.vue` + `HealthDot.vue`).
3. Card/List `ViewToggle.vue` (Card = sibling components; List = reuse ObjectList).
4. `BenchList.vue` (level 2: benches-on-server + breadcrumb).
5. `BenchControlPanel.vue` (level 3: service table via `getProcessesColumns()` + co-located sites + hint banner).
6. Wire inline + bench-level controls to `service_action` (resolves bench.ts TODO).
7. `LogDrawer.vue` (embed `LogViewer.vue`, file chips, action bar, disabled ext chips).
8. Live auto-refresh (pulse + `refetchInterval`).
9. Token mapping + light/dark parity.
10. Additivity check: confirm `server.js` tabs/analytics/actions/plans/regions untouched; cross-link panel -> Analytics tab + Log Browser; run `pre-deploy-smoke.test.ts`.

## Open design decision (for resume)
Two shapes for the panel:
- (A) NEW additive "Infrastructure" page consuming `get_infra_tree` (workflow's recommendation; keeps existing server pages pristine, cleaner separation, more new files).
- (B) ENHANCE the existing `/servers` list in place (add metric columns + a card/list toggle) and deepen the Benches tab (the lighter-touch ask). Note: the existing list is billing/region-oriented and ObjectList has no toggle, so (B) still needs a sibling card component.
Recommendation: (A) for the drill/control/drawer, plus a small slice of (B) - add instant metric columns to the existing `/servers` list since that is cheap and was the original ask.
