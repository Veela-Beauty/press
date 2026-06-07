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

---

## Resume here (2026-06-07) - Plan 2b status

DONE + PUSHED + DEPLOYED LIVE at `/dashboard/infrastructure` (bundle gitignored; redeploy with `cd dashboard && yarn build`):
- [x] T0 route + nav + stub (623ee9a)
- [x] T1 infra-derive.js + 14 vitest (f2e31d2)
- [x] T2 infra-api.js (cae7c68)
- [x] T3 atoms MeterBar/StatusBadge/SummaryCards (a7ce8dd)
- [x] T4 ServerList.vue (1abe34c)
- [x] T5 shell: nav-toggle + breadcrumb + 15s poll + routing (96a04b3)
- [x] T6 HostDetail + UnitTable - live restart/stop/kill (f572f4e)
- [x] T7 UnitDrawer - logs/inspect (73342f6a)
- [x] T8 NeedsAttention (67320d75)
- [x] T9 AddHostWizard (f0c137da)
- [x] T12 build + deploy live; + warm-cache fix (dd281471): get_infra_tree now under 1s via a scheduler pre-warm (cron every minute, CACHE_TTL 15->90s) - it had been ~12s, hanging the page on "Loading...".

REMAINING:
- [ ] T10 polish (skeleton loaders + consistency) - most polish already shipped in T4-T9
- [ ] T11 Playwright human-flow assert (rule #9). NOTE: a DRAFT narrated walkthrough was already published at `~/docs/tests/press/infrastructure-dashboard/player.html` (Arabic, status draft) + COMPARISON.md (prototype vs live).

LIVE BUGS found in hand-test (fix next - all root-caused):
- [ ] BUG1 toggle reposition - the Servers/Infrastructure toggle IS deployed but sits in the `<Header>` `#actions` (top-right), not inline like the prototype. Move it into the page body. Presentation only (InfraDashboard.vue ~lines 9-22).
- [ ] BUG2 server CPU/Disk metrics not showing - BACKEND gap: `host_probes()` collects only `memory` for Press servers (not cpu/disk), so ServerList can only show Mem for the servers nav. FIX: add cpu(load) + disk probes to host_probes in press/api/infra_board.py, then add the columns in ServerList.vue for the servers nav. (Mem renders from host.memory.used_pct - verify.)
- [ ] BUG3 Notifications page not like prototype - the de-slopped notifications redesign was PROTOTYPE-ONLY, never built (live = old objects/notification.js ObjectList). FIX: build Notifications.vue from `~/docs/prototypes/press-notifications.html` (severity chips, grouping, expandable msg, filters) wired to get_notifications/mark_as_read, replace the ObjectList route.

Decisions this session: light-mode only; managed hosts have FLAT units (no stack level); commit SOURCE ONLY per task (bundle gitignored, deploy = build from source); vitest needs a dedicated dashboard/vitest.config.js; cache pre-warm via scheduler keeps get_infra_tree instant.

---

## Update 2026-06-07b: 3 live bugs FIXED + verified live (Playwright)

All three hand-test bugs are fixed, deployed to autodeploypanel.mvpstorm.com, and verified live (logged in as eng.elgogary@gmail.com); screenshots captured.

- [x] BUG1 toggle moved inline (1c4013b6) - the Servers/Infrastructure toggle is now a prominent segmented control in the page body with a per-surface description; removed from the Header actions. Verified: toggle visible + switches surfaces (Infrastructure <-> Servers).
- [x] BUG2 server CPU + Disk (a8ad60db) - added a _cpu_disk SSH probe (1-min load average / cores for CPU%, root df for Disk%) to host_probes, cached 60s like memory; added CPU/Disk columns + card rows + sort to ServerList for the servers nav. Verified live: press-f1 15/43/61, u4 15/43/61, u5 22/77/49 (CPU/Mem/Disk %). Backend change required `bench restart` + a `warm_infra_tree` run to repopulate the cache.
- [x] BUG3 Notifications page (5cdd7cfa) - bespoke Notifications.vue (+ notifications-derive.js) replacing the bare ObjectList: derived severity (icon tint + chip), Today/Yesterday/Earlier grouping, summary chips, tab/type/severity filters, expandable messages, per-row Mark read + Review/View, Mark all as read. Route registered before generateRoutes() to shadow the generated one. Verified live: 98 unread / 0 attention / 11 errors chips, grouped feed, no ObjectList table.

Watch-out: BUG2 adds one SSH round-trip per server to the warm-cache cron (now memory + cpu_disk + ssh_ok = 3 per server). It is backgrounded + 60s-cached, but if the warm build ever exceeds ~60s, batch the three probes into one SSH call.

Deploy recipe used (press-ctrl cannot fetch github in non-interactive ssh, so commits relay IN via bundle): edit locally in a press_local worktree -> commit + push to github (the local clone can push) -> `git bundle create /tmp/x.bundle ^<base> HEAD` -> scp to press-ctrl -> `git fetch /tmp/x.bundle HEAD && git merge --ff-only FETCH_HEAD` -> `cd dashboard && yarn build`. Backend change also needs `bench restart` + `bench --site demo.mvpstorm.com execute press.api.infra_board.warm_infra_tree`.

---

## Update 2026-06-07c: /code-review pass (BIG) landed + re-verified

A full BIG /code-review of the 3 bug-fix changes (Architecture/Code/Tests/Performance) ran; verdict PASS_WITH_WARNINGS (0 critical). Approved fixes implemented, deployed, and re-verified live:

- Arch-1A + Code-4A + Tests-2A (ba0955b5): infra_board extracts a pure `_parse_cpu_disk` (defensive parse + logs raw output on bad lines) and drops the separate `_ssh_ok` SSH round-trip (reachability derives from the cpu/disk probe) - 3 SSH trips/server down to 2, watch_tower dep removed.
- Code-1A + Arch-2B (ba0955b5): notifications `timeAgo` reuses the dashboard dayjs (relativeTime, locale-correct); severity inference centralized into a documented INTERIM map (delete when a backend severity field lands).
- Code-2B + 3A (ba0955b5): Notifications mark-read/mark-all reload the list (authoritative read state, not an optimistic mutation); PAGE_LENGTH + MSG_EXPAND_CHARS extracted.
- Arch-3A (ba0955b5): objects/notification.js comments that its generated route is superseded.
- Tests-1A + 2A (ba0955b5): new notifications-derive.test.js (21 vitest) + `_parse_cpu_disk` tests; host_probes tests updated for the dropped `_ssh_ok`.
- Follow-up (12416b35): re-verification caught dayjs rendering "in 30 minutes" for just-created notifications (server/browser clock skew) - clamp future relative-times to "just now".

Verification: vitest 35 passed (14 infra-derive + 21 notifications-derive); `bench run-tests press.api.tests.test_infra_board` 13 passed; live re-check - servers CPU/Mem/Disk render with fresh values, notifications page renders with correct "just now" labels.

Deferred (note-only): Perf-2 notifications "load older" pagination -> T10; Arch-2B backend severity field -> when the Press Notification doctype is next touched.

---

## Update 2026-06-07d: Gate-0 long-term fix (silent-failure -> self-diagnosing) + 2nd /code-review

Triggered by trying to register press-ctrl's own Docker for a "full cycle on real data" demo and discovering **Gate 0 is entirely unprovisioned** (no SSH CA, no control-plane key, no socket-proxy; the smoke's CA was ephemeral and gone). The dashboard just showed "0 hosts / Unreachable" with no reason. Ran a BIG /code-review of the managed-host Gate-0 backend, then shipped the approved long-term fix:

- **classify_conn_error()** maps raw ssh/docker errors to actionable operator reasons (publickey -> "control-plane cert rejected: check Gate 0"; forward-fail -> "socket-proxy not reachable on :proxy_port"; not-provisioned -> "set SANAD_SSH_CA_PRIVATE_PATH"; timeout/refused/docker-api).
- **Persist + surface:** `Managed Host` gains a `last_error` field; `_attach_cert` captures the sign-failure reason, `_enumerate_managed`/`test_connection` persist it (write-if-changed), `get_infra_tree` carries it so the host card shows WHY it is dark.
- **gate0_status()** lightweight cached read-only preflight (control-plane key present + CA secret resolves+valid via `ssh-keygen -y`, never opens a tunnel) driving a **Gate-0 banner** in InfraDashboard that lists exactly what is missing. Verified live: banner shows "Generate it: ssh-keygen ... sanad-infra" + "Set SANAD_SSH_CA_PRIVATE_PATH ... and restart the bench".
- **i18n + actionable** adapter throws (ssh_docker).
- **Tests:** classify_conn_error, gate0_status, _attach_cert reason, _build_tree surfacing (python suite 13 -> 20, all pass).
- Follow-up `20a00cf0`: cache the gate0 CA *hint* (not just the ok flag) so polled calls keep the specific reason.

Commits: `c04bc3ef` (fix) + `20a00cf0` (hint-cache). press-ctrl + github at `20a00cf01`. Deploy: bench migrate (adds last_error) -> python run-tests -> yarn build -> bench restart.

The throwaway demo path (CA-free sshd+socat sidecar on 127.0.0.1:2222) PROVED the adapter/tunnel cycle works on real Docker, then was fully torn down (no Managed Host persisted, press-ctrl restored). To actually register a real host long-term, do the real Gate-0 provisioning (CA in Infisical via SANAD_SSH_CA_PRIVATE_PATH + control-plane key + a persistent socket-proxy/ssh-proxy) - the banner now tells you exactly that.

---

## Update 2026-06-07e: Gate 0 PROVISIONED on press-ctrl + first real host onboarded (live)

The managed-host control plane is now LIVE on prod. Onboarded the first real host (press-ctrl's own Docker) through the correct flow end-to-end:

**Part A - Gate 0 (one-time, control plane on press-ctrl):**
- SSH CA keypair: `/home/frappe/keys/sanad-infra-ca` (+ `.pub`), 0600 frappe.
- Control-plane key: `/home/frappe/.ssh/sanad-infra` (+ `.pub`), 0600 frappe. This is the key test_connection signs per host.
- Env wired: `SANAD_SSH_CA_PRIVATE_PATH=/home/frappe/keys/sanad-infra-ca` added to the bench supervisor.conf for 4 program blocks (frappe-web, frappe-schedule, short-worker, long-worker), applied via `supervisorctl reread && update`. get_infisical_secret reads this env. Backup at `config/supervisor.conf.bak-gate0`.
- Verified: gate0_status().ready == true, the dashboard Gate-0 banner disappeared.

**Part B/C - first host (press-controller-docker):**
- Persistent CA-trusting sidecar `sanad-infra-proxy` (alpine sshd + socat to /var/run/docker.sock, TrustedUserCAKeys = the CA pubkey, AllowTcpForwarding, frappe user unlocked), `--restart unless-stopped`, published `127.0.0.1:2222:22`. Build files at `/opt/sanad-infra/`.
- Registered via the Add-host wizard: ssh_host=127.0.0.1, ssh_user=frappe, ssh_port=2222, proxy_port=2375, type=docker. test_connection: SSH ok, Docker API ok, 8 containers -> status Active.
- Steady-state enumerate verified: health=up, last_error=None, 8 real containers (sanad-infra-proxy, log-kibana, log-elasticsearch, portainer-press, code-analysis, borgmatic, minio, registry). Shows live in the dashboard (1 Hosts).

**DURABILITY CAVEATS (must address for true long-term):**
1. **The supervisor env is fragile** - `bench setup supervisor` (run during some deploys) REGENERATES supervisor.conf and WIPES the SANAD_SSH_CA_PRIVATE_PATH lines. After any such run, re-add them + `supervisorctl reread && update`, or Gate 0 breaks (banner returns). A durable fix is a supervisor template override or a system-level `[supervisord] environment=`.
2. **CA private key is on disk only**, not yet in Infisical at `infra/ssh_ca_private`. A press-ctrl rebuild loses it (and every managed host's trust). Back it up to Infisical.
3. **The socket-proxy is socat (full Docker access)**, not the restricted `tecnativa/docker-socket-proxy` (EXEC/BUILD/VOLUMES=0). Harden before exposing more hosts. Auth is CA-cert-only + 8h TTL + localhost-bound, so the surface is gated, but the proxy itself is unrestricted.

**To onboard the NEXT host:** repeat Part B only (stand up a CA-trusting socket-proxy on that host that trusts `/home/frappe/keys/sanad-infra-ca.pub`, then Add-host wizard). Gate 0 (Part A) is already done.

---

## Update 2026-06-07f: 2nd host onboarded - daytona-sandbox-1 (remote, firewalled) + cert-cache gotcha

Onboarded sandbox-1 (the Daytona Docker host, 65.108.128.91, ~44 containers) as the 2nd managed host, one-by-one with safety verified before each risk (user: "make sure before go on risk").

**Recon (read-only) findings:** press-ctrl can REACH sandbox-1 (ping/:22/:9101 open) but cannot SSH-auth; THIS dev box has root SSH to it (ssh alias `sandbox-1` -> 65.108.128.91). Port 2222 already taken there -> used 22022.

**Safe approach (isolated sidecar + firewall, user-approved):** built the CA-trusting sidecar on sandbox-1 via dev-box root, on a dedicated docker network `sanad-infra-net` (172.31.255.0/29) with static IP 172.31.255.2, published `22022:22`, `--restart unless-stopped`, CA pubkey + docker.sock mounted. Build files at sandbox-1:/opt/sanad-infra/. Firewalled with a DOCKER-USER rule SCOPED TO THE SIDECAR IP so the 42 sandboxes are untouched: `iptables -I DOCKER-USER -p tcp -d 172.31.255.2 --dport 22 ! -s 89.167.116.92 -j DROP` (89.167.116.92 = press-ctrl). VERIFIED: dev-box -> :22022 BLOCKED, press-ctrl -> :22022 OPEN. CA-cert tunnel press-ctrl->sandbox-1 returned 44 containers. Registered (host_name daytona-sandbox-1, ssh 65.108.128.91:22022 user frappe proxy 2375) -> test_connection ssh/docker ok / 44 -> Active, health up, last_error None. Dashboard shows 2 Hosts.

**GOTCHA found (real robustness gap):** after onboarding, BOTH hosts suddenly showed "Control-plane cert rejected". Root cause: a manual verification ran `rm -f sanad-infra-cert.pub`, deleting the cert file that `_attach_cert`'s 6h Redis cache (`infra_board:cert:frappe`) still pointed at - and `_attach_cert` caches the cert PATH without checking the file still exists, so it served a dead path for every host sharing that ssh_user. Fix now: `frappe.cache().delete_value("infra_board:cert:frappe")` -> re-sign. **Code follow-up:** `_attach_cert` should `os.path.exists()` the cached cert (and re-sign if missing) before using it.

**Durability caveats (sandbox-1):** the DOCKER-USER iptables rule is NOT persisted across reboot (re-add it, or use iptables-persistent). Sidecar is `--restart unless-stopped` so it survives reboot, but the firewall rule must too or the port re-opens to the world (still CA-cert-only auth, but un-scoped).

**Next host:** repeat Part B only - stand up a CA-trusting socket-proxy on that host trusting `sanad-infra-ca.pub`, firewall it to press-ctrl (89.167.116.92), register. Gate 0 is done.

---

## Update 2026-06-07g: live host CPU/Mem/Disk for managed hosts (9780c72d)

Managed Docker hosts now show REAL host metrics (not 0% / not n/a). The docker adapter's `enumerate` runs a FIXED read-only `ssh_command` (new in docker_tunnel) that reads the host `/proc/loadavg` + `/proc/meminfo` + `df` which the sidecar mounts read-only (`-v /proc:/host/proc:ro -v /:/host/root:ro`); `parse_host_stats` -> cpu(load/cores)/mem/disk %. Degrades to None -> UI shows "n/a" if the probe fails. `_overload` made null-safe; ServerList renders the gauge when present else "n/a". Verified live: sandbox-1 7/15/57, press-ctrl 11/25/46 (%); python tests 23 pass (3 new parse_host_stats).

**Security notes:** (1) the sidecar now bind-mounts the host root READ-ONLY (a read exposure, but bounded by the existing docker-socket root-equivalence the sidecar already has). (2) `ssh_command` reintroduces shell exec to the host, a deliberate exception to plan-2a's "no shell" - mitigated by the command being FIXED with no host-controlled data (no injection). Harden later with the restricted tecnativa/docker-socket-proxy + a dedicated stats endpoint instead of shell.

**Durability:** if a sidecar is recreated, re-add the host mounts (`-v /proc:/host/proc:ro -v /:/host/root:ro`) or its metrics fall back to n/a. (Plus the earlier caveats: sandbox-1 firewall rule + the bench SANAD_SSH_CA_PRIVATE_PATH env are not reboot-persistent.)
