# Unified Infrastructure View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the in-page `Servers | Infrastructure` toggle with one flat list of all servers (Press + managed) carrying a Type badge + filter, where a row click opens a type-aware detail drawer.

**Architecture:** Dashboard-only Vue 3 refactor. The backend already returns one merged tree (`get_infra_tree().servers`, `kind: 'managed' | undefined`). Shared pure helpers in `infra-derive.js` (vitest) normalise metrics across both kinds. `ServerList.vue` collapses its two per-`nav` templates into one. A new thin `HostDrawer.vue` wraps the already-type-aware `HostDetail.vue` in a frappe-ui `Dialog`. `InfraDashboard.vue` drops the toggle and the breadcrumb drill, switching to a single `detailNode` drawer state. Native `/servers/*` pages and the left-nav stay untouched.

**Tech Stack:** Vue 3 (`<script setup>`), frappe-ui (`Dialog`, `Button`, `FormControl`, `MeterBar`), vitest, vue-router.

Spec: `docs/infra-board/2026-06-07-unified-infrastructure-view-design.md`.

---

## File Structure

| File | Responsibility after this change |
|---|---|
| `dashboard/src/pages/infrastructure/infra-derive.js` | + `cpuPct/memPct/diskPct(node)` (read host vs metrics by kind) and `downServers(nodes)` (Press nodes that are down/unreachable). |
| `dashboard/src/pages/infrastructure/infra-derive.test.js` | + tests for the four new helpers. |
| `dashboard/src/pages/infrastructure/ServerList.vue` | One list of both kinds: Type badge column, All/Press/Managed filter, conditional Runtime (docker/plain) filter, accessor-based metrics + sort. Emits `open`. |
| `dashboard/src/pages/infrastructure/HostDrawer.vue` | NEW. `Dialog` slide-over: shared metrics header + the existing `HostDetail` body (managed control vs Press read-only) + a nested `UnitDrawer` for managed unit logs. |
| `dashboard/src/pages/infrastructure/NeedsAttention.vue` | Also lists down Press servers (via `downServers`). |
| `dashboard/src/pages/infrastructure/InfraDashboard.vue` | Remove toggle + drill; `navNodes`->`allNodes`; `detailNode` drawer; Gate-0 banner keyed on managed presence. |

`HostDetail.vue`, `UnitTable.vue`, `UnitDrawer.vue`, `MeterBar.vue`, `SummaryCards.vue`, `infra-api.js`, and all backend code are unchanged.

Run all commands from `/tmp/press-fix/dashboard`. Compile check per task: `yarn vite build --outDir /tmp/x --emptyOutDir` (throwaway, no deploy). Unit tests: `yarn vitest run src/pages/infrastructure/infra-derive.test.js`. Commit author for every commit: `Sanad Agent <agent@sanadeoi.com>`.

---

## Task 1: Shared metric accessors + down-servers helper (infra-derive.js)

**Files:**
- Modify: `dashboard/src/pages/infrastructure/infra-derive.js`
- Test: `dashboard/src/pages/infrastructure/infra-derive.test.js`

- [ ] **Step 1: Write the failing tests** - append to `infra-derive.test.js`:

```javascript
describe('metric accessors (kind-aware)', () => {
  it('managed reads node.metrics.{cpu,mem,disk}', () => {
    expect(d.cpuPct(dockerNode)).toBe(95);
    expect(d.memPct(dockerNode)).toBe(40);
    expect(d.diskPct(plainNode)).toBe(88);
  });
  it('press reads node.host.{cpu,memory,disk}.used_pct', () => {
    const press = { name: 'p1', host: { cpu: { used_pct: 12 }, memory: { used_pct: 50 }, disk: { used_pct: 61 } } };
    expect(d.cpuPct(press)).toBe(12);
    expect(d.memPct(press)).toBe(50);
    expect(d.diskPct(press)).toBe(61);
  });
  it('returns null when the metric is missing', () => {
    expect(d.cpuPct({ name: 'x', kind: 'managed', metrics: {} })).toBeNull();
    expect(d.cpuPct({ name: 'y' })).toBeNull();
    expect(d.memPct(pressNode)).toBe(50);   // pressNode has host.memory only
    expect(d.cpuPct(pressNode)).toBeNull();  // no host.cpu in the sample
  });
});
describe('downServers', () => {
  it('returns only Press (non-managed) nodes that are down or unreachable', () => {
    const up = { name: 'p-up', health: 'up' };
    const dn = { name: 'p-dn', health: 'down' };
    const un = { name: 'p-un', health: 'unknown' };
    const res = d.downServers([up, dn, un, dockerNode]); // dockerNode is managed+down -> excluded
    expect(res.map(n => n.name)).toEqual(['p-dn', 'p-un']);
  });
});
```

- [ ] **Step 2: Run the tests, verify they fail**

Run: `yarn vitest run src/pages/infrastructure/infra-derive.test.js`
Expected: FAIL - `d.cpuPct is not a function`.

- [ ] **Step 3: Implement the helpers** - in `infra-derive.js`, add after the `isManaged` line (line 7):

```javascript
const num = (v) => (typeof v === 'number' ? v : null);
export const cpuPct  = (n) => (isManaged(n) ? num(n.metrics?.cpu)  : num(n.host?.cpu?.used_pct));
export const memPct  = (n) => (isManaged(n) ? num(n.metrics?.mem)  : num(n.host?.memory?.used_pct));
export const diskPct = (n) => (isManaged(n) ? num(n.metrics?.disk) : num(n.host?.disk?.used_pct));
export const downServers = (nodes = []) =>
  nodes.filter((n) => !isManaged(n) && (n.health === 'down' || n.health === 'unknown'));
```

- [ ] **Step 4: Run the tests, verify they pass**

Run: `yarn vitest run src/pages/infrastructure/infra-derive.test.js`
Expected: PASS (all describe blocks green).

- [ ] **Step 5: Commit**

```bash
cd /tmp/press-fix
git add dashboard/src/pages/infrastructure/infra-derive.js dashboard/src/pages/infrastructure/infra-derive.test.js
git -c user.name="Sanad Agent" -c user.email="agent@sanadeoi.com" \
  commit -m "feat(infra): kind-aware metric accessors + downServers helper"
```

---

## Task 2: One merged list with Type badge + filter (ServerList.vue)

**Files:**
- Modify: `dashboard/src/pages/infrastructure/ServerList.vue` (full rewrite of template + script; same file)

This collapses the two per-`nav` `<template>` blocks (list rows + cards) into one, drops the `nav` prop, adds the Type badge + All/Press/Managed filter, makes the docker/plain segment conditional ("Runtime"), and routes all metrics/sort through the Task-1 accessors. Row click emits `open` (a drawer, not a drill).

- [ ] **Step 1: Replace the `<template>` block** with:

```html
<template>
  <div class="flex flex-col gap-4">
    <SummaryCards :cards="summaryCards" />

    <div class="flex flex-wrap items-center gap-2">
      <h2 class="text-sm font-semibold text-gray-900">
        Infrastructure
        <span class="ml-1 font-normal text-gray-400">({{ filtered.length }})</span>
      </h2>

      <!-- Type: Press / Managed -->
      <div class="flex items-center rounded-md bg-gray-100 p-0.5">
        <button
          v-for="k in kindOptions"
          :key="k.value"
          class="rounded px-2 py-0.5 text-xs transition-colors"
          :class="kindSeg === k.value ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
          @click="kindSeg = k.value; page = 1"
        >{{ k.label }}</button>
      </div>

      <!-- Status -->
      <div class="flex items-center rounded-md bg-gray-100 p-0.5">
        <button
          v-for="s in statusOptions"
          :key="s.value"
          class="rounded px-2 py-0.5 text-xs transition-colors"
          :class="statusSeg === s.value ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
          @click="statusSeg = s.value; page = 1"
        >{{ s.label }}</button>
      </div>

      <!-- Runtime (docker/plain) - only meaningful when managed hosts are in view -->
      <div v-if="kindSeg !== 'press'" class="flex items-center rounded-md bg-gray-100 p-0.5">
        <button
          v-for="t in typeOptions"
          :key="t.value"
          class="rounded px-2 py-0.5 text-xs transition-colors"
          :class="typeSeg === t.value ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
          @click="typeSeg = t.value; page = 1"
        >{{ t.label }}</button>
      </div>

      <FormControl type="text" placeholder="Search..." v-model="q" class="w-44 text-sm" @input="page = 1" />
      <div class="flex-1" />
      <Button variant="solid" @click="$emit('add')">Add host</Button>
    </div>

    <div v-if="filtered.length === 0" class="py-12 text-center text-sm text-gray-400">
      No servers match your filter.
    </div>

    <!-- List view -->
    <template v-else-if="view === 'list'">
      <div class="overflow-x-auto rounded-lg border border-gray-200">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-200 bg-gray-50">
              <th class="w-4 px-3 py-2"></th>
              <th class="cursor-pointer select-none py-2 pr-3 text-left font-medium text-gray-600 hover:text-gray-900" @click="toggleSort('name')">Name {{ sortCaret('name') }}</th>
              <th class="px-3 py-2 text-left font-medium text-gray-600">Type</th>
              <th class="cursor-pointer select-none px-3 py-2 text-left font-medium text-gray-600 hover:text-gray-900" @click="toggleSort('cpu')">CPU {{ sortCaret('cpu') }}</th>
              <th class="cursor-pointer select-none px-3 py-2 text-left font-medium text-gray-600 hover:text-gray-900" @click="toggleSort('mem')">Mem {{ sortCaret('mem') }}</th>
              <th class="cursor-pointer select-none px-3 py-2 text-left font-medium text-gray-600 hover:text-gray-900" @click="toggleSort('disk')">Disk {{ sortCaret('disk') }}</th>
              <th class="px-3 py-2 text-left font-medium text-gray-600">Status</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="node in paged" :key="node.name" class="cursor-pointer hover:bg-gray-50" @click="$emit('open', node.name)">
              <td class="px-3 py-2.5"><span class="inline-block h-[7px] w-[7px] rounded-full" :class="dotClass(nodeDot(node))" /></td>
              <td class="py-2.5 pr-3 font-mono font-medium text-gray-900">{{ node.name }}</td>
              <td class="px-3 py-2.5">
                <span class="rounded-full px-2 py-0.5 text-[11px] font-semibold" :class="isManaged(node) ? 'bg-blue-50 text-blue-700' : 'bg-gray-100 text-gray-600'">
                  {{ isManaged(node) ? 'Managed' : 'Press' }}
                </span>
              </td>
              <td class="px-3 py-2.5"><MeterBar v-if="cpuPct(node) != null" :value="cpuPct(node)" /><span v-else class="text-gray-400" :title="HOST_STATS_NOTE">n/a</span></td>
              <td class="px-3 py-2.5"><MeterBar v-if="memPct(node) != null" :value="memPct(node)" /><span v-else class="text-gray-400" :title="HOST_STATS_NOTE">n/a</span></td>
              <td class="px-3 py-2.5"><MeterBar v-if="diskPct(node) != null" :value="diskPct(node)" /><span v-else class="text-gray-400" :title="HOST_STATS_NOTE">n/a</span></td>
              <td class="px-3 py-2.5">
                <span class="flex items-center gap-1.5">
                  <span class="inline-block h-[7px] w-[7px] shrink-0 rounded-full" :class="dotClass(statusInfo(node).dot)" />
                  <span class="text-xs" :class="textClass(statusInfo(node).dot)">{{ statusInfo(node).text }}</span>
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="more" class="flex justify-center pt-1"><Button variant="subtle" @click="page++">Load {{ remaining }} more</Button></div>
    </template>

    <!-- Cards view -->
    <template v-else>
      <div class="grid gap-3" style="grid-template-columns: repeat(auto-fill, minmax(330px, 1fr))">
        <div v-for="node in paged" :key="node.name" class="cursor-pointer rounded-lg border border-gray-200 p-4 hover:bg-gray-50" tabindex="0" @click="$emit('open', node.name)" @keyup.enter="$emit('open', node.name)">
          <div class="mb-3 flex items-center gap-2">
            <span class="inline-block h-[7px] w-[7px] shrink-0 rounded-full" :class="dotClass(nodeDot(node))" />
            <span class="flex-1 truncate font-mono text-sm font-medium text-gray-900">{{ node.name }}</span>
            <span class="rounded-full px-2 py-0.5 text-[11px] font-semibold" :class="isManaged(node) ? 'bg-blue-50 text-blue-700' : 'bg-gray-100 text-gray-600'">{{ isManaged(node) ? 'Managed' : 'Press' }}</span>
          </div>
          <div class="flex flex-col gap-1.5">
            <div class="flex items-center justify-between text-xs text-gray-500"><span>CPU</span><MeterBar v-if="cpuPct(node) != null" :value="cpuPct(node)" /><span v-else class="text-gray-400" :title="HOST_STATS_NOTE">n/a</span></div>
            <div class="flex items-center justify-between text-xs text-gray-500"><span>Mem</span><MeterBar v-if="memPct(node) != null" :value="memPct(node)" /><span v-else class="text-gray-400" :title="HOST_STATS_NOTE">n/a</span></div>
            <div class="flex items-center justify-between text-xs text-gray-500"><span>Disk</span><MeterBar v-if="diskPct(node) != null" :value="diskPct(node)" /><span v-else class="text-gray-400" :title="HOST_STATS_NOTE">n/a</span></div>
          </div>
          <div class="mt-3 border-t border-gray-100 pt-2">
            <span class="flex items-center gap-1.5">
              <span class="inline-block h-[7px] w-[7px] shrink-0 rounded-full" :class="dotClass(statusInfo(node).dot)" />
              <span class="text-xs" :class="textClass(statusInfo(node).dot)">{{ statusInfo(node).text }}</span>
            </span>
          </div>
        </div>
      </div>
      <div v-if="more" class="flex justify-center pt-1"><Button variant="subtle" @click="page++">Load {{ remaining }} more</Button></div>
    </template>
  </div>
</template>
```

- [ ] **Step 2: Replace the `<script setup>` block** with:

```html
<script setup>
import { ref, computed } from 'vue';
import { Button, FormControl } from 'frappe-ui';
import { nodeDot, loadState, summary, isManaged, issues, downServers, cpuPct, memPct, diskPct } from './infra-derive';
import MeterBar from './MeterBar.vue';
import SummaryCards from './SummaryCards.vue';

const props = defineProps({
  nodes: { type: Array,  default: () => [] },
  view:  { type: String, default: 'list' }, // 'list' | 'cards'
});
defineEmits(['open', 'add']);

const HOST_STATS_NOTE = 'Host stats unavailable: the sidecar could not read the host /proc (re-run it with the host /proc + root mounts).';

const q         = ref('');
const kindSeg   = ref('all');   // 'all' | 'press' | 'managed'
const statusSeg = ref('all');
const typeSeg   = ref('all');   // docker/plain runtime, managed only
const sortKey   = ref('name');
const sortDir   = ref('asc');
const page      = ref(1);
const PER       = 15;

const kindOptions   = [{ label: 'All', value: 'all' }, { label: 'Press', value: 'press' }, { label: 'Managed', value: 'managed' }];
const statusOptions = [{ label: 'All', value: 'all' }, { label: 'Healthy', value: 'healthy' }, { label: 'Issues', value: 'issues' }];
const typeOptions   = [{ label: 'All', value: 'all' }, { label: 'Docker', value: 'docker' }, { label: 'Plain', value: 'plain' }];

const summaryCards = computed(() => {
  const managed = props.nodes.filter(isManaged);
  const press   = props.nodes.filter((n) => !isManaged(n));
  return [
    { label: 'Press servers', value: press.length },
    { label: 'Managed hosts', value: managed.length },
    { label: 'Units down',    value: summary(managed).unitsDown,                         bad: true },
    { label: 'Unreachable',   value: props.nodes.filter((n) => n.health === 'unknown').length, bad: true },
  ];
});

const filtered = computed(() => {
  let rows = props.nodes;
  if (kindSeg.value === 'press')   rows = rows.filter((n) => !isManaged(n));
  else if (kindSeg.value === 'managed') rows = rows.filter(isManaged);

  if (statusSeg.value === 'healthy') rows = rows.filter((n) => nodeDot(n) === 'up');
  else if (statusSeg.value === 'issues') rows = rows.filter((n) => nodeDot(n) !== 'up');

  if (kindSeg.value !== 'press' && typeSeg.value !== 'all') {
    rows = rows.filter((n) => n.server_type === typeSeg.value);
  }

  if (q.value.trim()) {
    const lq = q.value.trim().toLowerCase();
    rows = rows.filter((n) => n.name.toLowerCase().includes(lq));
  }

  return [...rows].sort((a, b) => {
    let av, bv;
    switch (sortKey.value) {
      case 'cpu':  av = cpuPct(a)  ?? -1; bv = cpuPct(b)  ?? -1; break;
      case 'mem':  av = memPct(a)  ?? -1; bv = memPct(b)  ?? -1; break;
      case 'disk': av = diskPct(a) ?? -1; bv = diskPct(b) ?? -1; break;
      default:     av = a.name;           bv = b.name;           break;
    }
    const cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return sortDir.value === 'asc' ? cmp : -cmp;
  });
});

const paged     = computed(() => filtered.value.slice(0, page.value * PER));
const more      = computed(() => paged.value.length < filtered.value.length);
const remaining = computed(() => Math.min(PER, filtered.value.length - paged.value.length));

function toggleSort(col) {
  if (sortKey.value === col) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc';
  else { sortKey.value = col; sortDir.value = 'asc'; }
}
function sortCaret(col) {
  if (sortKey.value !== col) return '';
  return sortDir.value === 'asc' ? '^' : 'v';
}

const DOT_CLASS  = { up: 'bg-green-500', warn: 'bg-amber-500', down: 'bg-red-500', unk: 'bg-gray-400' };
const TEXT_CLASS = { up: 'text-green-700', warn: 'text-amber-700', down: 'text-red-700', unk: 'text-gray-500' };
function dotClass(dot)  { return DOT_CLASS[dot]  || 'bg-gray-400'; }
function textClass(dot) { return TEXT_CLASS[dot] || 'text-gray-500'; }

function statusInfo(node) {
  if (node.health === 'unknown') return { text: 'unreachable', dot: 'unk' };
  const l = loadState(node);
  if (l?.lvl === 'crit') return { text: `overloaded ${l.which} ${l.val}%`, dot: 'down' };
  if (node.health === 'down') {
    const downCount = isManaged(node)
      ? issues([node]).length
      : (node.benches || []).filter((b) => b.health !== 'up').length;
    return { text: `${downCount} down`, dot: 'down' };
  }
  if (l?.lvl === 'high') return { text: `high load ${l.which} ${l.val}%`, dot: 'warn' };
  return { text: 'healthy', dot: 'up' };
}
</script>
```

(`downServers` is imported for parity with the dashboard usage; it is not referenced inside this file, so if the linter flags an unused import, drop it from this import line. The compile check in Step 3 will reveal it.)

- [ ] **Step 3: Compile check**

Run: `yarn vite build --outDir /tmp/x --emptyOutDir`
Expected: "built in ..." with no error. If "downServers is defined but never used" warning appears, remove `downServers` from the import in Step 2 and rebuild.

- [ ] **Step 4: Commit**

```bash
cd /tmp/press-fix
git add dashboard/src/pages/infrastructure/ServerList.vue
git -c user.name="Sanad Agent" -c user.email="agent@sanadeoi.com" \
  commit -m "feat(infra): one merged server list with Type badge + Press/Managed filter"
```

---

## Task 3: Type-aware detail drawer (HostDrawer.vue)

**Files:**
- Create: `dashboard/src/pages/infrastructure/HostDrawer.vue`

A `Dialog` slide-over (same pattern as `UnitDrawer.vue`) with a shared metrics header and the already-type-aware `HostDetail` body. For managed hosts, `HostDetail` renders `UnitTable` and emits `openUnit`, which this drawer feeds into a nested `UnitDrawer` (logs/control). For Press servers, `HostDetail` renders the read-only bench list with its built-in "Open server page" button.

- [ ] **Step 1: Create the file** with:

```html
<template>
  <Dialog
    :modelValue="!!node"
    :options="{ size: '4xl' }"
    @update:modelValue="(v) => { if (!v) $emit('close'); }"
  >
    <template #body-content>
      <div v-if="node" class="space-y-4">
        <!-- Header: name + type badge + live metrics -->
        <div class="flex flex-wrap items-center gap-3 border-b border-gray-100 pb-3">
          <span class="h-2 w-2 shrink-0 rounded-full" :class="dotClass(nodeDot(node))" />
          <span class="font-mono font-medium text-gray-900">{{ node.name }}</span>
          <span class="rounded-full px-2 py-0.5 text-[11px] font-semibold" :class="isManaged(node) ? 'bg-blue-50 text-blue-700' : 'bg-gray-100 text-gray-600'">
            {{ isManaged(node) ? 'Managed' : 'Press' }}
          </span>
          <div class="flex-1" />
          <div class="flex items-center gap-4 text-xs text-gray-500">
            <span class="flex items-center gap-1">CPU <MeterBar v-if="cpuPct(node) != null" :value="cpuPct(node)" /><span v-else>n/a</span></span>
            <span class="flex items-center gap-1">Mem <MeterBar v-if="memPct(node) != null" :value="memPct(node)" /><span v-else>n/a</span></span>
            <span class="flex items-center gap-1">Disk <MeterBar v-if="diskPct(node) != null" :value="diskPct(node)" /><span v-else>n/a</span></span>
          </div>
        </div>

        <!-- Body: HostDetail is already type-aware (managed control vs Press read-only) -->
        <HostDetail :node="node" @openUnit="onOpenUnit" @reload="$emit('reload')" />
      </div>
    </template>
  </Dialog>

  <!-- Nested unit drawer (managed unit logs / control) -->
  <UnitDrawer
    :host="node?.name"
    :unit="unit"
    @close="unit = null"
    @reload="$emit('reload')"
  />
</template>

<script setup>
import { ref } from 'vue';
import { Dialog } from 'frappe-ui';
import HostDetail from './HostDetail.vue';
import UnitDrawer from './UnitDrawer.vue';
import MeterBar from './MeterBar.vue';
import { isManaged, nodeDot, cpuPct, memPct, diskPct } from './infra-derive';

defineProps({ node: { type: Object, default: null } });
defineEmits(['close', 'reload']);

const unit = ref(null);
function onOpenUnit(u) { unit.value = u; }

const DOT_CLASS = { up: 'bg-green-500', warn: 'bg-amber-500', down: 'bg-red-500', unk: 'bg-gray-400' };
function dotClass(dot) { return DOT_CLASS[dot] || 'bg-gray-400'; }
</script>
```

- [ ] **Step 2: Temporarily import it so the compiler reaches it** - in `InfraDashboard.vue`, add `import HostDrawer from './HostDrawer.vue';` near the other imports (it is wired for real in Task 5; this is only so Step 3 type-checks the new file).

- [ ] **Step 3: Compile check**

Run: `yarn vite build --outDir /tmp/x --emptyOutDir`
Expected: "built in ..." with no error.

- [ ] **Step 4: Commit**

```bash
cd /tmp/press-fix
git add dashboard/src/pages/infrastructure/HostDrawer.vue dashboard/src/pages/infrastructure/InfraDashboard.vue
git -c user.name="Sanad Agent" -c user.email="agent@sanadeoi.com" \
  commit -m "feat(infra): HostDrawer slide-over wrapping the type-aware HostDetail"
```

---

## Task 4: Surface down Press servers in NeedsAttention.vue

**Files:**
- Modify: `dashboard/src/pages/infrastructure/NeedsAttention.vue`

- [ ] **Step 1: Add the down-servers rows to the template** - immediately after the overloaded-host `v-for` block (the `<div v-for="o in shownOver" ...>...</div>`, before the overflow footer `<div v-if="total > 4" ...>`), insert:

```html
      <!-- Down Press-server rows -->
      <div
        v-for="s in shownServers"
        :key="`srv-${s.name}`"
        class="flex items-center gap-2"
      >
        <span class="inline-block h-[7px] w-[7px] shrink-0 rounded-full bg-red-500" />
        <span class="font-mono text-sm text-gray-900">{{ s.name }}</span>
        <span class="text-xs text-gray-400">server {{ s.health === 'unknown' ? 'unreachable' : 'down' }}</span>
        <div class="flex-1" />
        <Button variant="subtle" @click="$emit('view', s.name)">View</Button>
      </div>
```

- [ ] **Step 2: Update the script** - replace the `<script setup>` body (lines after the imports) so `downServers` feeds the totals. Change the import line and the computed block to:

```html
<script setup>
import { computed } from 'vue';
import { Button } from 'frappe-ui';
import { issues, overloaded, downServers, loadState, stateLabel } from './infra-derive';

const props = defineProps({
  nodes: { type: Array, default: () => [] },
});
defineEmits(['view']);

const down    = computed(() => issues(props.nodes));
const over    = computed(() => overloaded(props.nodes));
const servers = computed(() => downServers(props.nodes));
const total   = computed(() => down.value.length + over.value.length + servers.value.length);
const hasIssues = computed(() => total.value > 0);

// Down units first, then overloaded hosts, then down servers; max 4 combined.
const shownDown    = computed(() => down.value.slice(0, 4));
const shownOver    = computed(() => over.value.slice(0, Math.max(0, 4 - shownDown.value.length)));
const shownServers = computed(() => servers.value.slice(0, Math.max(0, 4 - shownDown.value.length - shownOver.value.length)));
</script>
```

- [ ] **Step 3: Update the header count line** - in the template header, change the summary span text from `` `${down.length} down, ${over.length} overloaded` `` to include servers:

Replace:
```html
        {{ hasIssues
          ? `${down.length} down, ${over.length} overloaded`
          : 'Nothing needs attention.' }}
```
with:
```html
        {{ hasIssues
          ? `${down.length + servers.length} down, ${over.length} overloaded`
          : 'Nothing needs attention.' }}
```

- [ ] **Step 4: Compile check**

Run: `yarn vite build --outDir /tmp/x --emptyOutDir`
Expected: "built in ..." with no error.

- [ ] **Step 5: Commit**

```bash
cd /tmp/press-fix
git add dashboard/src/pages/infrastructure/NeedsAttention.vue
git -c user.name="Sanad Agent" -c user.email="agent@sanadeoi.com" \
  commit -m "feat(infra): NeedsAttention also lists down Press servers"
```

---

## Task 5: Remove the toggle + drill; wire the drawer (InfraDashboard.vue)

**Files:**
- Modify: `dashboard/src/pages/infrastructure/InfraDashboard.vue`

- [ ] **Step 1: Replace the LEVEL-1/2/3 body** - replace the whole block from `<template v-if="!path.server">` (line ~50) through the close of the drill levels (the `</template>` that ends the `v-else` group block, line ~115, just before `<!-- Unit drawer (Task 7) -->`) with the single-level body:

```html
        <!-- Gate-0 preflight banner: only relevant while managed hosts exist -->
        <div
          v-if="hasManaged && gate0.data && !gate0.data.ready"
          class="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3.5 text-sm"
        >
          <div class="flex items-start gap-2">
            <span class="mt-1 h-2 w-2 shrink-0 rounded-full bg-amber-500" />
            <div>
              <p class="font-medium text-amber-900">Gate 0 is not provisioned, so managed hosts cannot connect yet.</p>
              <ul class="mt-1.5 space-y-1 text-amber-800">
                <li v-for="c in gate0.data.checks.filter((x) => !x.ok)" :key="c.name">
                  <span class="font-medium">{{ c.name }}:</span> {{ c.hint }}
                </li>
              </ul>
            </div>
          </div>
        </div>

        <NeedsAttention :nodes="allNodes" class="mb-4" @view="onOpen" />
        <ServerList
          :nodes="allNodes"
          :view="view"
          @open="onOpen"
          @add="onAdd"
        />
```

Then replace the `<!-- Unit drawer (Task 7) -->` `<UnitDrawer .../>` block (lines ~117-123) with the host drawer:

```html
    <!-- Host detail drawer (type-aware: managed control vs Press read-only) -->
    <HostDrawer
      :node="detailNode"
      @close="detailNode = null"
      @reload="tree.reload()"
    />
```

- [ ] **Step 2: Update the script imports** - replace the import lines for `partition`, `HostDetail`, and `UnitDrawer` so the file imports `HostDrawer` instead and no longer pulls `partition`/`HostDetail`/`UnitDrawer` directly:

```javascript
import { useInfraTree, useGate0Status } from './infra-api';
import { isManaged } from './infra-derive';
import ServerList from './ServerList.vue';
import NeedsAttention from './NeedsAttention.vue';
import HostDrawer from './HostDrawer.vue';
import AddHostWizard from './AddHostWizard.vue';
```

- [ ] **Step 3: Replace the UI-state + derived + navigation script** - replace the block from `const nav = ref('infra');` through the end of the navigation helpers and the leftover `drawerUnit`/`onOpenUnit`/`openGroup`/`go` functions with:

```javascript
// --- UI state ---
const view       = ref('list');   // 'list' | 'cards'
const fresh      = ref('just now');
const detailNode = ref(null);      // the node shown in the drawer, or null

// --- 15-second polling ---
let timer = null;
onMounted(() => {
  timer = setInterval(() => { tree.reload(); fresh.value = 'just now'; }, 15000);
});
onUnmounted(() => clearInterval(timer));

// --- Derived nodes ---
const allNodes   = computed(() => tree.data?.servers || []);
const hasManaged = computed(() => allNodes.value.some(isManaged));

// --- Breadcrumbs ---
const crumbs = computed(() => [{ label: 'Infrastructure', route: { name: 'Infrastructure' } }]);

// --- Open a node in the drawer ---
function onOpen(name) {
  detailNode.value = allNodes.value.find((n) => n.name === name) || null;
}

// --- Add-host wizard ---
const wizardOpen = ref(false);
function onAdd() { wizardOpen.value = true; }
```

Note: `reactive` is no longer used (the `path` object is gone). If `reactive` is now an unused import from `vue`, drop it from the `import { ref, reactive, computed, onMounted, onUnmounted } from 'vue';` line so it reads `import { ref, computed, onMounted, onUnmounted } from 'vue';`.

- [ ] **Step 4: Check the header for stale `path`/`nav` references** - the header markup (lines ~1-48) drives the List/Cards toggle and breadcrumbs. Confirm nothing there still reads `path.server`, `path.group`, `nav`, or `setNav`. The List/Cards toggle is gated by `v-if="!path.group"` (line ~10); change that gate to always show by removing the `v-if="!path.group"` from that `<div>` (the toggle should always be available now that there are no drill levels).

Run: `grep -nE "path\.|nav|setNav|drill|openGroup|drawerUnit|onOpenUnit|HostDetail|UnitDrawer|partition" dashboard/src/pages/infrastructure/InfraDashboard.vue`
Expected: no matches (every reference removed). If any remain, remove them.

- [ ] **Step 5: Compile check**

Run: `yarn vite build --outDir /tmp/x --emptyOutDir`
Expected: "built in ..." with no error.

- [ ] **Step 6: Run the infra unit tests (regression)**

Run: `yarn vitest run src/pages/infrastructure/infra-derive.test.js`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd /tmp/press-fix
git add dashboard/src/pages/infrastructure/InfraDashboard.vue
git -c user.name="Sanad Agent" -c user.email="agent@sanadeoi.com" \
  commit -m "feat(infra): unify Infrastructure into one list + drawer, drop the Servers toggle"
```

---

## Task 6: Deploy + live verification

**Files:** none (deploy only).

- [ ] **Step 1: Push the source branch**

```bash
cd /tmp/press-fix
git push origin HEAD:cloudflare-dns
```
Expected: `<old>..<new>  HEAD -> cloudflare-dns`.

- [ ] **Step 2: Bundle the new commits and copy to press-ctrl**

```bash
cd /tmp/press-fix
BASE=a96b8dd49197   # the spec commit already on press-ctrl; use the actual current press-ctrl HEAD if different
git branch -f infra-unify HEAD
git bundle create /tmp/infra-unify.bundle ${BASE}..infra-unify
scp /tmp/infra-unify.bundle press-ctrl:/tmp/infra-unify.bundle
```
Expected: bundle verifies; scp completes.

- [ ] **Step 3: Merge + build on press-ctrl (as frappe)**

```bash
ssh press-ctrl "chmod 644 /tmp/infra-unify.bundle; sudo -u frappe bash -lc '
  set -e
  cd /home/frappe/frappe-bench/apps/press
  git fetch /tmp/infra-unify.bundle infra-unify
  git merge --ff-only FETCH_HEAD
  cd dashboard && yarn build
  ls -la ../press/public/dashboard/index.html
'"
```
Expected: "Done in ..."; `index.html` freshly timestamped, `frappe frappe` owned. (No `bench restart` - dashboard is static assets.)

- [ ] **Step 4: Confirm the new code shipped + the toggle is gone**

```bash
ssh press-ctrl "sudo -u frappe bash -lc \"grep -rl 'Managed' /home/frappe/frappe-bench/apps/press/press/public/dashboard/assets/InfraDashboard-*.js >/dev/null && echo HAS_BADGE; grep -rl \\\"setNav\\\" /home/frappe/frappe-bench/apps/press/press/public/dashboard/assets/InfraDashboard-*.js && echo TOGGLE_REMAINS || echo TOGGLE_GONE\""
curl -s -o /dev/null -w 'infrastructure: HTTP %{http_code}\n' https://autodeploypanel.mvpstorm.com/dashboard/infrastructure
```
Expected: `HAS_BADGE`, `TOGGLE_GONE`, `HTTP 200`.

- [ ] **Step 5: Live browser check** (Playwright MCP; clear the stale lock first if needed: `pkill -9 -f mcp-chrome; rm -f ~/.cache/ms-playwright/mcp-chrome-*/Singleton*`)

  1. Navigate to `https://autodeploypanel.mvpstorm.com/dashboard/infrastructure`.
  2. Assert: one list with both Press and managed rows; a `Type` badge column; an `All / Press / Managed` filter; NO `Servers | Infrastructure` toggle.
  3. Click a `Managed` row -> drawer opens with the unit table (start/stop/restart/kill).
  4. Click a `Press` row -> drawer opens read-only with an "Open server page" button.
  5. Screenshot to `/home/eslam/data/screenshots/press-infrastructure/2026-06-07-unified-view.png`.

- [ ] **Step 6: Update docs (docs-keeper)** - mark the spec DoD boxes, add a CHANGELOG-SANAD-FORK entry ("Unified Infrastructure view: one list + type-aware drawer, removed the in-page Servers toggle"), update the project memory `press-infra-control-panel-2026-06-07.md`, and relay the doc commits to press-ctrl.

---

## Self-Review

**Spec coverage:** (1) one flat list + Type badge + filter -> Task 2. (2) shared metric accessors -> Task 1. (3) type-aware drawer on click, managed control vs Press read-only + deep-link -> Task 3 (reusing HostDetail's existing branch + goServer). (4) NeedsAttention spans both kinds -> Tasks 1 + 4. (5) Gate-0 banner kept, keyed on managed presence -> Task 5. (6) native Servers nav + backend untouched -> no task changes them. (7) deploy + live verify -> Task 6. All spec sections map to a task.

**Placeholder scan:** no TBD/TODO; every code step shows complete code; the only checkboxes are DoD/steps. Clear.

**Type consistency:** `cpuPct/memPct/diskPct/downServers` defined in Task 1 are imported/used with the same names in Tasks 2, 3, 4. The row-open event is named `open` in both ServerList (emit, Task 2) and InfraDashboard (`@open="onOpen"`, Task 5). The drawer prop is `node` in HostDrawer (Task 3) and bound `:node="detailNode"` in InfraDashboard (Task 5). `hasManaged`/`allNodes`/`detailNode` defined and used consistently in Task 5. Consistent.

---

## Status: SHIPPED 2026-06-07

All 6 tasks complete, built green on press-ctrl (BUILD_EXIT=0), verified live at
`/dashboard/infrastructure`, final code review PASS_WITH_WARNINGS (2 cheap findings fixed,
rest noted as nice-to-have). Commits (on cloudflare-dns):
- `7ef95a4d` derive accessors + downServers (18/18 vitest)
- `702199fd` ServerList merged list + Type badge + filter
- `79995470` HostDrawer slide-over
- `39fd1ba3` NeedsAttention down Press servers
- `9160b0b8` InfraDashboard unify (toggle removed, drawer wired)
- `144cd9b8` dialog title fix
- `9b02be62` code-review fixes (host fallback, dead import)

Verified live: one list of 5 nodes with Type badges, All/Press/Managed + Status + Runtime
filters, down Press servers in Needs-attention, managed row -> unit control drawer, Press row
-> read-only drawer with "Open server page". Native Servers nav untouched.
