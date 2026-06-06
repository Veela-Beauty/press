# Plan 2b: Infrastructure Dashboard (Vue) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. After EACH task: push (bundle->worktree, never push from press-ctrl) + run /code-review. Never lose work.

**Goal:** Turn the approved `press-infrastructure.html` prototype into a real, bespoke Vue page in the Press dashboard at `/dashboard/infrastructure`, wired to the proven `get_infra_tree` / `host_unit_action` / `get_host_log` backend - a Portainer-style monitor + control panel for Press benches (read) and managed docker/plain hosts (control).

**Architecture:** One bespoke `.vue` page tree under `dashboard/src/pages/infrastructure/`, NOT the ObjectList generator (the UI is a tree + drawers). All data from one polled `createResource('press.api.infra_board.get_infra_tree')` (15s server cache). Pure view-model logic is isolated in a testable `infra-derive.js` module (vitest TDD); presentational components are frappe-ui + Tailwind utilities translating the prototype 1:1; control actions go through `host_unit_action` (managed docker units only) with optimistic-update-then-reload.

**Tech Stack:** Vue 3 `<script setup>`, frappe-ui (`createResource`, `Button`, `Dialog`, `Badge`, `FormControl`, global `Header`/`Breadcrumbs`/`Card`), Tailwind (frappe-ui preset, rebrand vars), vite build, vitest, Playwright (human-flow test).

---

## Scope + key decisions (read before any task)

- **Light mode only.** The dashboard has no dark-mode strategy; drop the prototype's dark toggle. Use frappe-ui utility classes (`bg-gray-50`, `text-gray-600`, `border`, `rounded-lg`) which inherit the fork rebrand (Accurate-Systems blue `#046BD2`).
- **Two control planes, v1 scope:**
  - **Managed hosts** (`node.kind === 'managed'`, `server_type` docker/plain): the live control plane. Docker units (have `_id`) get Restart/Start/Stop/Kill via `host_unit_action` + Logs via `get_host_log`. Plain/systemd units are **watch-only** (no `_id`, no control) - show the prototype's watch-only callout.
  - **Press servers** (no `kind`, have `benches[]`): **read-only** tree in v1 - show benches + services + health + host probes. Bench service control already exists on the Press server page; v1 links there rather than re-implementing. (Wiring `press.api.bench._service_action` into the unit table is a tracked phase-2.)
- **One data source.** `get_infra_tree()` returns `{servers:[...]}` with BOTH node kinds. The two navs (Servers / Infrastructure) are client-side partitions of that one list: Servers = nodes without `kind`; Infrastructure = nodes with `kind==='managed'`.
- **Polling.** Poll `get_infra_tree` every 15s (matches the server cache TTL; faster gives only cache hits). After a control action: optimistic UI update + `tree.reload()` (the cache lags up to 15s, so don't rely on it alone).
- **Alerts panel.** The prototype's Alerts panel is sourced from Watch Tower. v1: render it from a best-effort `frappe_theme_switcher.watch_tower` resource IF present; otherwise hide the panel (no fake data). Tracked as a soft dependency, not a blocker.
- **Add-host wizard** wires to the existing `press.api.infra_board.add_managed_host` + `test_connection` (both proven in the live smoke).

## Backend contract (frozen - from research, do not re-derive)

`get_infra_tree()` -> `{ servers: [ Node ] }`, System-Manager gated, 15s Redis cache, no args.

**Press server node** (no `kind`): `{ name, benches:[Bench], host:HostProbe, health:'up'|'down' }`
- `Bench`: `{ name, group, status, site_count, services:[{program,state:'run'|'down',status}], services_up, services_down, health:'unknown'|'up'|'down' }`
- `HostProbe`: `{ server, memory:null|{verdict,used_pct,available_mb,total_mb}, agent:null|{verdict}, ssh:{ok} }`

**Managed host node** (`kind:'managed'`): `{ name, kind:'managed', server_type:'docker'|'plain', benches:[], units:[Unit], metrics:{cpu,mem,disk,req}, overload:null|'high'|'crit', host:{server}, health:'unknown'|'up'|'down' }`
- `Unit`: `{ name, kind:'container'|'systemd', state, sub, uptime, restarts, ports, health, pid, _id? }` (`_id` only on docker units = the unit_id for actions)
- State vocab: docker `run|heal|unhealth|exit0|exit2|restart|dead|pause|stop`; plain `active|down`. (`unknown` is NODE health only, never a unit state.)

Mutations (System-Manager gated, audited):
- `host_unit_action(host, unit_id, action)` -> `{ok,host,unit,action}`; actions `start|stop|restart|kill`; docker-only.
- `get_host_log(host, unit_id, tail=200)` -> `string[]`; docker-only.
- `add_managed_host(host_name, server_type, ssh_host, ssh_user, ssh_port, proxy_port)` -> `{name,status}`.
- `test_connection(host)` -> `{ssh_ok, docker_ok, containers}`.

Call pattern: `createResource({ url:'press.api.infra_board.<fn>' })`; reads use `auto:true`; mutations `.submit({...params})`.

## File structure (create under `apps/press/dashboard/src/pages/infrastructure/`)

| File | Responsibility |
|---|---|
| `infra-derive.js` | PURE view-model functions (no Vue): partition nav, node status/dot, loadState, isDown, uDot, state label+theme, issues(), overloaded(), summary counts. **Unit-tested.** |
| `infra-api.js` | frappe-ui `createResource` wrappers: `useInfraTree()` (poll), `unitAction()`, `unitLog()`, `testConnection()`, `addHost()`. |
| `InfraDashboard.vue` | Page shell: nav toggle (Servers/Infrastructure), topbar (breadcrumb + List/Cards + freshness), level router (list -> server/host detail -> unit table), overlays host. |
| `ServerList.vue` | List page for a nav: summary cards, [infra] needs-attention, alerts, filter/search/sort toolbar, table OR cards. |
| `HostDetail.vue` | Managed-host detail: stacks (docker) or watch-only systemd table (plain) + reach callouts. (Press server detail v1 = a thin read-only bench list + "Open server page" link.) |
| `UnitTable.vue` | Group -> units table: state badge, meta, hover row-actions (Restart/Stop/Logs), busy state. |
| `UnitDrawer.vue` | Right drawer: Logs / Inspect / Stats tabs, action bar; Logs via `get_host_log`. |
| `AddHostWizard.vue` | 3-step dialog: form -> test_connection -> add_managed_host. |
| `SummaryCards.vue`, `NeedsAttention.vue`, `MeterBar.vue`, `StatusBadge.vue` | Presentational atoms (translate prototype). |
| `infra-derive.test.js` | vitest tests for `infra-derive.js`. |

Plus: register route in `dashboard/src/router.js`; add nav item in `dashboard/src/components/NavigationItems.vue`.

Translate the look from the prototype `/home/eslam/docs/prototypes/press-infrastructure.html` (it is the visual spec) using Tailwind utilities; keep the de-slop standard (no emoji, geometric dots, monospace for ids/ports/metrics, hairline borders, 6px radius, restrained palette).

---

## Task 0: Scaffold the route + nav + stub page

**Files:**
- Create: `dashboard/src/pages/infrastructure/InfraDashboard.vue`
- Modify: `dashboard/src/router.js` (add route before `...generateRoutes()`)
- Modify: `dashboard/src/components/NavigationItems.vue` (add Infrastructure nav item)

- [ ] **Step 1: Stub page** - `InfraDashboard.vue`:
```vue
<template>
  <div class="flex h-full flex-col">
    <div class="sticky top-0 z-10 shrink-0">
      <Header>
        <Breadcrumbs :items="[{ label: 'Infrastructure', route: { name: 'Infrastructure' } }]" />
      </Header>
    </div>
    <div class="p-5">
      <div v-if="tree.loading">Loading...</div>
      <pre v-else class="text-xs">{{ (tree.data?.servers || []).map(s => s.name) }}</pre>
    </div>
  </div>
</template>
<script setup>
import { createResource } from 'frappe-ui';
const tree = createResource({ url: 'press.api.infra_board.get_infra_tree', auto: true });
</script>
```
- [ ] **Step 2: Route** - in `router.js`, add before `...generateRoutes()`:
```js
{ path: '/infrastructure', name: 'Infrastructure', component: () => import('./pages/infrastructure/InfraDashboard.vue') },
```
(Name must NOT start with 'Server' to avoid the guard's server-auto-enable.)
- [ ] **Step 3: Nav item** - in `NavigationItems.vue`, add to the items array (mimic the existing 'Servers' entry shape), pointing `route: '/infrastructure'`, with a lucide server/grid icon, label 'Infrastructure'.
- [ ] **Step 4: Build + verify** - `cd dashboard && yarn build` (expect a clean build; new `index-<hash>.js` in `../press/public/dashboard/assets/` and updated `../press/www/dashboard.html`). Load `/dashboard/infrastructure` in the browser - expect the page renders + lists server names from the live tree.
- [ ] **Step 5: Commit** - `git add dashboard/src/pages/infrastructure/InfraDashboard.vue dashboard/src/router.js dashboard/src/components/NavigationItems.vue && git commit -m "feat(infra-ui): scaffold /infrastructure route + nav + stub page wired to get_infra_tree"`

---

## Task 1: `infra-derive.js` - pure view-model logic (TDD)

**Files:**
- Create: `dashboard/src/pages/infrastructure/infra-derive.js`
- Test: `dashboard/src/pages/infrastructure/infra-derive.test.js`

First confirm the runner: `ls dashboard/vitest.config.* dashboard/package.json | xargs grep -l vitest` - if vitest is not present, add it as a devDependency + a `"test:unit":"vitest run"` script (frappe-ui ships vitest-compatible). Tests run with `cd dashboard && yarn vitest run infra-derive`.

- [ ] **Step 1: Write the failing tests** (`infra-derive.test.js`):
```js
import { describe, it, expect } from 'vitest';
import * as d from './infra-derive';

const pressNode = { name: 'press-f1', benches: [{ name: 'b1', health: 'down', services_down: 1, services_up: 5 }], host: { ssh: { ok: true }, memory: { used_pct: 50 } }, health: 'down' };
const dockerNode = { name: 'acc-1', kind: 'managed', server_type: 'docker', units: [{ name: 'x', kind: 'container', state: 'stop', _id: 'a'.repeat(64) }, { name: 'y', kind: 'container', state: 'run', _id: 'b'.repeat(64) }], metrics: { cpu: 95, mem: 40, disk: 30, req: 0 }, overload: 'crit', health: 'down' };
const plainNode = { name: 'box-1', kind: 'managed', server_type: 'plain', units: [{ name: 'sshd.service', kind: 'systemd', state: 'active' }], metrics: { cpu: 10, mem: 20, disk: 88, req: 0 }, overload: 'high', health: 'up' };

describe('partition', () => {
  it('splits servers vs managed by kind', () => {
    const { servers, infra } = d.partition([pressNode, dockerNode, plainNode]);
    expect(servers.map(s => s.name)).toEqual(['press-f1']);
    expect(infra.map(s => s.name)).toEqual(['acc-1', 'box-1']);
  });
});
describe('nodeDot', () => {
  it('down node -> down', () => expect(d.nodeDot(dockerNode)).toBe('down'));
  it('unreachable -> warn', () => expect(d.nodeDot({ ...plainNode, health: 'unknown' })).toBe('warn'));
  it('healthy -> up', () => expect(d.nodeDot({ ...plainNode, health: 'up', overload: null })).toBe('up'));
});
describe('loadState', () => {
  it('crit at >=90', () => expect(d.loadState(dockerNode)).toEqual({ lvl: 'crit', which: 'CPU', val: 95 }));
  it('high at 80-89', () => expect(d.loadState(plainNode)).toEqual({ lvl: 'high', which: 'Disk', val: 88 }));
  it('null below 80 / press node (no metrics)', () => expect(d.loadState(pressNode)).toBeNull());
});
describe('unit helpers', () => {
  it('isDown covers stop/exit2/down', () => { expect(d.isDown('stop')).toBe(true); expect(d.isDown('exit2')).toBe(true); expect(d.isDown('down')).toBe(true); expect(d.isDown('run')).toBe(false); });
  it('uDot maps run/heal/active->up, exit0->unk, else down', () => { expect(d.uDot('run')).toBe('up'); expect(d.uDot('active')).toBe('up'); expect(d.uDot('exit0')).toBe('unk'); expect(d.uDot('stop')).toBe('down'); });
  it('stateLabel + theme', () => { expect(d.stateLabel('exit2')).toBe('exited (non-zero)'); expect(d.stateTheme('run')).toBe('green'); expect(d.stateTheme('stop')).toBe('red'); expect(d.stateTheme('exit0')).toBe('gray'); });
  it('controllable only for docker units with _id', () => { expect(d.controllable({ kind: 'container', _id: 'a'.repeat(64) })).toBe(true); expect(d.controllable({ kind: 'systemd' })).toBe(false); });
});
describe('triage', () => {
  it('issues() walks managed nodes for down units', () => {
    const iss = d.issues([dockerNode, plainNode]);
    expect(iss).toEqual([{ server: 'acc-1', unit: 'x', state: 'stop' }]);
  });
  it('overloaded() returns crit nodes', () => expect(d.overloaded([dockerNode, plainNode]).map(s => s.name)).toEqual(['acc-1']));
  it('summary counts', () => {
    const s = d.summary([dockerNode, plainNode]);
    expect(s).toMatchObject({ hosts: 2, unitsDown: 1, overloaded: 1, unreachable: 0 });
  });
});
```
- [ ] **Step 2: Run -> FAIL** - `cd dashboard && yarn vitest run infra-derive` (expect module-not-found / undefined exports).
- [ ] **Step 3: Implement** (`infra-derive.js`):
```js
// Pure view-model helpers for the infra dashboard. No Vue imports - unit-tested.
const DOWN_STATES = new Set(['stop', 'exit2', 'down']);
const UP_STATES = new Set(['run', 'heal', 'active']);
const STATE_LABEL = { run: 'running', heal: 'healthy', unhealth: 'unhealthy', active: 'active', stop: 'stopped', down: 'down', exit0: 'exited (0)', exit2: 'exited (non-zero)', restart: 'restarting', dead: 'dead', pause: 'paused' };
const STATE_THEME = { run: 'green', heal: 'green', active: 'green', unhealth: 'orange', stop: 'red', down: 'red', exit2: 'red', dead: 'red', restart: 'orange', pause: 'gray', exit0: 'gray' };

export const isManaged = (n) => n.kind === 'managed';
export function partition(nodes = []) {
  return { servers: nodes.filter((n) => !isManaged(n)), infra: nodes.filter(isManaged) };
}
export function nodeDot(n) {
  if (n.health === 'unknown') return 'warn';
  if (n.health === 'down') return 'down';
  const l = loadState(n);
  if (l?.lvl === 'high') return 'warn';
  return 'up';
}
export function loadState(n) {
  const m = n.metrics;
  if (!m) return null; // press nodes have no metrics
  const pairs = [['CPU', m.cpu], ['Mem', m.mem], ['Disk', m.disk]];
  let hit = null;
  for (const [which, val] of pairs) {
    if (val >= 90) return { lvl: 'crit', which, val };
    if (val >= 80 && !hit) hit = { lvl: 'high', which, val };
  }
  return hit;
}
export const isDown = (s) => DOWN_STATES.has(s);
export const uDot = (s) => (UP_STATES.has(s) ? 'up' : s === 'exit0' ? 'unk' : 'down');
export const stateLabel = (s) => STATE_LABEL[s] || s;
export const stateTheme = (s) => STATE_THEME[s] || 'gray';
export const controllable = (u) => u.kind === 'container' && !!u._id;
export function issues(infraNodes = []) {
  const out = [];
  for (const n of infraNodes) for (const u of n.units || []) if (isDown(u.state)) out.push({ server: n.name, unit: u.name, state: u.state });
  return out;
}
export const overloaded = (infraNodes = []) => infraNodes.filter((n) => loadState(n)?.lvl === 'crit');
export function summary(infraNodes = []) {
  return {
    hosts: infraNodes.length,
    stacks: infraNodes.reduce((a, n) => a + (n.server_type === 'docker' ? (n.units || []).length : 0), 0),
    unitsDown: issues(infraNodes).length,
    overloaded: overloaded(infraNodes).length,
    unreachable: infraNodes.filter((n) => n.health === 'unknown').length,
  };
}
```
- [ ] **Step 4: Run -> PASS.** - `yarn vitest run infra-derive` (all green).
- [ ] **Step 5: Commit** - `git add dashboard/src/pages/infrastructure/infra-derive.* && git commit -m "feat(infra-ui): infra-derive pure view-model (status/load/triage) + vitest"`

---

## Task 2: `infra-api.js` - resource wrappers

**Files:** Create `dashboard/src/pages/infrastructure/infra-api.js`

- [ ] **Step 1: Implement** (mimics `utils/backupApi.js` promise pattern):
```js
import { createResource } from 'frappe-ui';

export function useInfraTree() {
  return createResource({ url: 'press.api.infra_board.get_infra_tree', auto: true });
}
function call(url, params) {
  return new Promise((resolve, reject) => {
    const r = createResource({ url, onSuccess: resolve, onError: reject });
    r.submit(params);
  });
}
export const unitAction = (host, unit_id, action) => call('press.api.infra_board.host_unit_action', { host, unit_id, action });
export const unitLog = (host, unit_id, tail = 200) => call('press.api.infra_board.get_host_log', { host, unit_id, tail });
export const testConnection = (host) => call('press.api.infra_board.test_connection', { host });
export const addHost = (p) => call('press.api.infra_board.add_managed_host', p);
```
- [ ] **Step 2: Build** - `yarn build` (clean compile).
- [ ] **Step 3: Commit** - `git add dashboard/src/pages/infrastructure/infra-api.js && git commit -m "feat(infra-ui): infra-api resource wrappers (tree/action/log/test/add)"`

---

## Task 3: Presentational atoms (MeterBar, StatusBadge, SummaryCards)

**Files:** Create `MeterBar.vue`, `StatusBadge.vue`, `SummaryCards.vue` under `pages/infrastructure/`.

Translate the prototype's meter bar / status badge / summary cards to Tailwind. No new logic (use `infra-derive`). Examples:
- [ ] `MeterBar.vue` - props `{ value:Number }`; renders `<span class="font-mono text-xs">{{value}}%</span>` + a 46px track `<div class="h-1 w-12 rounded bg-gray-100"><div :class="barColor" :style="{width: value+'%'}" /></div>`; `barColor` = `bg-gray-400` <75, `bg-amber-500` 75-89, `bg-red-500` >=90.
- [ ] `StatusBadge.vue` - props `{ state }`; `<Badge :label="stateLabel(state)" :theme="stateTheme(state)" />` (frappe-ui Badge, themes green/orange/red/gray).
- [ ] `SummaryCards.vue` - props `{ cards:[{label,value,bad}] }`; a flex row of `<div class="rounded-lg border px-4 py-3"><div class="text-2xl font-semibold" :class="card.bad && card.value ? 'text-red-600':''">{{card.value}}</div><div class="text-xs text-gray-500">{{card.label}}</div></div>`.
- [ ] Build, commit: `git commit -m "feat(infra-ui): MeterBar + StatusBadge + SummaryCards atoms"`

---

## Task 4: `ServerList.vue` - the list page (table/cards/filters)

**Files:** Create `ServerList.vue`. Props `{ nav:'servers'|'infra', nodes:Array }`. Emits `drill(nodeName)`.

- [ ] Render (top->bottom, translating prototype `renderServerList`/`renderInfraList`): `<SummaryCards>` (built from `infra-derive.summary` for infra; servers/benches/req/down/overloaded for servers); for infra `<NeedsAttention>` (Task 8); tools bar = title+count, status segment (All/Healthy/Issues) using frappe-ui `Button` group or a simple segmented control, [infra] type segment (All/Docker/Plain), a search `<FormControl type="text">`, and [infra] a solid `<Button>Add host</Button>` (emits `add`); body = a table (default) with sortable headers + rows (status dot via a tiny `<Dot>` span, name+ip mono, req/min, `<MeterBar>` x3, status cell) OR a cards grid toggled by the topbar.
- [ ] Filtering/search/sort/pagination are CLIENT-side over `nodes` (the tree is already fully loaded + cached). PER=15, "Load more" button.
- [ ] Row/card click -> `emit('drill', node.name)`.
- [ ] Build + browser-verify the list renders for both navs. Commit: `git commit -m "feat(infra-ui): ServerList (table/cards, filters, search, sort, paginate)"`

---

## Task 5: `InfraDashboard.vue` shell - nav toggle + topbar + level routing

**Files:** Modify `InfraDashboard.vue` (replace the Task-0 stub).

- [ ] State: `tree = useInfraTree()`; `nav = ref('infra')`; `path = reactive({ server:null, group:null })`; `view = ref('list')` (list/cards); a 15s `setInterval(() => tree.reload(), 15000)` started `onMounted`, cleared `onUnmounted`; a freshness label updated each poll.
- [ ] Topbar: a Servers/Infrastructure segmented toggle (setNav resets path+filters); breadcrumb from `path`; List/Cards toggle (hidden when `path.group`); freshness dot+text.
- [ ] Computed `nodes = computed(() => partition(tree.data?.servers || [])[nav.value === 'infra' ? 'infra' : 'servers'])`.
- [ ] Level router (v-if on `path`): no server -> `<ServerList :nav :nodes @drill="..." @add="openWizard" />`; server set, no group -> `<HostDetail>` (Task 6) for infra, or a read-only bench list + "Open server page" link for servers; group set -> `<UnitTable>` (Task 6).
- [ ] Build + verify: toggle navs, drill server->group, breadcrumb back. Commit: `git commit -m "feat(infra-ui): dashboard shell - nav toggle, breadcrumb, 15s poll, level routing"`

---

## Task 6: `HostDetail.vue` + `UnitTable.vue` - managed-host control plane

**Files:** Create `HostDetail.vue`, `UnitTable.vue`.

- [ ] `HostDetail.vue` props `{ node }`. For `server_type==='docker'`: a table of units (`node.units`) grouped as the "stacks/containers" view; reach callout if `health==='unknown'`. For `server_type==='plain'`: the units table in watch-only mode + the callout "Plain host - watch-only in v1 (systemd status, no control)". Emits `openUnit(unit)`.
- [ ] `UnitTable.vue` props `{ host, units }`. Each row: `uDot(state)` dot, name, `sub` (image, mono), `<StatusBadge :state>`, uptime, restarts; hover-revealed row actions for **controllable** units only (`infra-derive.controllable(unit)`): Restart (icon), Stop (icon, disabled if `isDown`), Logs (icon -> `emit('openUnit', unit)`). Non-controllable (systemd) rows show no action buttons.
- [ ] Action handler: `onAction(unit, action)` -> set `busy[unit._id]=true` -> optimistic state nudge -> `await unitAction(host, unit._id, action)` -> toast success ("X restarted - logged") -> `tree.reload()` (emit up) -> clear busy; on error -> toast the thrown message, clear busy. Destructive verbs (stop/kill) go through a confirm `<Dialog>` first.
- [ ] Build + browser-verify against a REAL managed host (use the Task-10 smoke harness to register one) OR mock. Commit: `git commit -m "feat(infra-ui): HostDetail + UnitTable with host_unit_action control (restart/stop/kill, optimistic+reload)"`

---

## Task 7: `UnitDrawer.vue` - Logs / Inspect / Stats

**Files:** Create `UnitDrawer.vue`. Use frappe-ui `<Dialog :options="{size:'2xl'}">` (or a right-drawer) as the container.

- [ ] Props `{ host, unit, open }`. Tabs: **Logs** (default) = on open, `await unitLog(host, unit._id, 200)` -> render lines in a `<div class="font-mono text-xs">` viewer (reuse the look of the existing LogViewer if importable); a Refresh button re-fetches. **Inspect** = a kv grid from the unit dict (Name, Image=`sub`, State, Uptime, Restarts, "Read via: Docker API (socket-proxy)"). **Stats** = placeholder "live stats - phase 2" (metrics are 0 in v1 per the backend; do NOT fake them - show "not collected in v1").
- [ ] Action bar in the drawer mirrors UnitTable (Restart/Start/Stop/Kill) for docker units.
- [ ] Build + verify logs load for a real docker unit. Commit: `git commit -m "feat(infra-ui): UnitDrawer - logs (get_host_log) + inspect; stats deferred honestly"`

---

## Task 8: `NeedsAttention.vue` + Alerts panel

**Files:** Create `NeedsAttention.vue`.

- [ ] Props `{ nodes }`. Header: dot (down if `issues().length||overloaded().length` else up) + "N down, M overloaded" or "all clear". List up-to-4: down-unit rows (unit, `server`, View + primary Restart) + overloaded-host rows (name, "overloaded - CPU X%", View). Restart -> same `unitAction` path (one-click remediation). Uses `infra-derive.issues/overloaded`.
- [ ] Alerts panel: attempt `createResource({ url:'frappe_theme_switcher.watch_tower.api.get_active_alerts', auto:true })` guarded by a `try`/onError -> if it errors or is absent, do NOT render the panel (no fake data). Render rows (severity dot, message, source+age, Acknowledge) only when data is present.
- [ ] Build + verify. Commit: `git commit -m "feat(infra-ui): NeedsAttention triage panel + best-effort Watch Tower alerts"`

---

## Task 9: `AddHostWizard.vue` - onboarding

**Files:** Create `AddHostWizard.vue`. frappe-ui `<Dialog>` 3-step.

- [ ] Step 1 form (`<FormControl>`): Host name, Type (select docker/plain), SSH host, SSH user (default 'sanad'), SSH port (22), Proxy port (2375). "Next: test".
- [ ] Step 2: on enter, `await addHost(form)` (creates the Pending host) then `await testConnection(form.host_name)`; show a spinner callout "Signing a short-TTL SSH cert and probing...", then the kv result (SSH ok, Docker API ok + N containers). On failure show the error + a Back button (the host stays Pending/Unreachable - honest).
- [ ] Step 3 success: green dot, "<host> is now managed, appears under Infrastructure within ~15s". Done -> close + `tree.reload()`.
- [ ] Build + verify against the smoke harness. Commit: `git commit -m "feat(infra-ui): AddHostWizard - add_managed_host + test_connection onboarding"`

---

## Task 10: Polish - confirm dialogs, toasts, optimistic+reload, empty/loading states

**Files:** touch the components above.

- [ ] Confirm `<Dialog>` for stop/kill + group restarts (kill warns "SIGKILL may lose in-flight work").
- [ ] Toasts via frappe-ui `toast` (vue-sonner) - spinner during action, success after, error on throw.
- [ ] Skeleton/loading states matching arriving tables (the prototype lacked these); empty states ("No hosts match '<search>'").
- [ ] Confirm the 15s poll + reload-after-action keeps the board fresh; verify a restart reflects within one tick.
- [ ] Build + verify. Commit: `git commit -m "feat(infra-ui): confirms + toasts + optimistic-reload + skeleton/empty states"`

---

## Task 11: Playwright human-flow test (rule #9)

**Files:** Create `tests/infra-dashboard.cjs` (Playwright, video:'on' + trace:'on' + visible cursor), published per the canonical path.

- [ ] Spin a disposable docker test-host (reuse the Task-10 smoke harness: alpine sshd + socat + CA + a victim container) and register it via `add_managed_host`.
- [ ] The test mirrors the human, step-by-step, NO API shortcuts for clickable steps: log in -> open `/dashboard/infrastructure` -> see the managed host row (screenshot) -> click it -> see its containers (screenshot) -> open a container's Logs drawer (screenshot of real lines) -> click Restart -> confirm -> see the success toast (screenshot) -> verify the `Infra Action Log` got a restart row.
- [ ] Output video + trace + REPORT.md + index.html under `~/docs/tests/press/infrastructure-dashboard/` -> live at `https://sanad-preview.sanadeoi.mvpstorm.com/tests/press/infrastructure-dashboard/`.
- [ ] Tear down the disposable host. Commit: `git commit -m "test(infra-ui): Playwright human-flow - open dashboard, drill, logs, restart, audit"`

---

## Task 12: Build, deploy, verify live

- [ ] `cd dashboard && yarn install` (if deps changed for vitest) then `yarn build`; confirm new hashed assets in `press/public/dashboard/assets/` + `press/www/dashboard.html` rewritten.
- [ ] Hard-refresh `/dashboard/infrastructure` on the live dashboard; click through Servers + Infrastructure, drill, restart a real unit, read logs.
- [ ] Record the result in DEVLOG/handover. Commit any built assets per the repo's convention (check whether `press/public/dashboard/` is committed or CI-built; if CI-built, do NOT commit the bundle - just the source). Final commit: `git commit -m "build(infra-ui): dashboard build for /infrastructure"` (source only if assets are CI-built).

---

## Self-review (author)

- **Spec coverage:** two navs (T5), three-level tree (T4/T6), summary cards (T3/T4), needs-attention + alerts (T8), filters/search/sort/paginate (T4), meter bars + status badges (T3), row actions + drawer logs/inspect/stats (T6/T7), add-host wizard (T9), confirms/toasts/optimistic (T10), reachability + plain watch-only callouts (T6), freshness/poll (T5). Press-bench control + live Stats + Watch-Tower alerts are explicitly deferred/honest, matching the proven backend.
- **No placeholders:** derive + api + route + nav + tests have full code; presentational tasks give the exact frappe-ui primitives + the prototype section to translate + the Tailwind classes (the prototype IS the markup spec - not re-pasted).
- **Type consistency:** `node.kind`, `unit._id`, `state` vocab, `metrics{cpu,mem,disk,req}`, `health` values, the `host_unit_action(host,unit_id,action)` / `get_host_log(host,unit_id,tail)` signatures are used identically across tasks and match the frozen backend contract.

## Resume here (2026-06-06)
- Last completed: plan written (this file).
- Next up: Task 0 (scaffold route + nav + stub), then 1..12 in order.
- Execution: subagent-driven; push after each task (bundle->worktree, never from press-ctrl) + /code-review after each.
- Decisions: light-mode only; managed-host control only (benches read-only v1); one polled get_infra_tree; derive logic TDD'd, Vue verified by build+Playwright.
