<template>
  <div class="flex flex-col gap-4">
    <!-- Summary cards -->
    <SummaryCards :cards="summaryCards" />

    <!-- Tools bar -->
    <div class="flex flex-wrap items-center gap-2">
      <h2 class="text-sm font-semibold text-gray-900">
        {{ nav === 'infra' ? 'Infrastructure' : 'Servers' }}
        <span class="ml-1 font-normal text-gray-400">({{ filtered.length }})</span>
      </h2>

      <!-- Status segment -->
      <div class="flex items-center rounded-md bg-gray-100 p-0.5">
        <button
          v-for="s in statusOptions"
          :key="s.value"
          class="rounded px-2 py-0.5 text-xs transition-colors"
          :class="statusSeg === s.value ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
          @click="statusSeg = s.value; page = 1"
        >{{ s.label }}</button>
      </div>

      <!-- Type segment (infra only) -->
      <div v-if="nav === 'infra'" class="flex items-center rounded-md bg-gray-100 p-0.5">
        <button
          v-for="t in typeOptions"
          :key="t.value"
          class="rounded px-2 py-0.5 text-xs transition-colors"
          :class="typeSeg === t.value ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
          @click="typeSeg = t.value; page = 1"
        >{{ t.label }}</button>
      </div>

      <!-- Search -->
      <FormControl
        type="text"
        placeholder="Search..."
        v-model="q"
        class="w-44 text-sm"
        @input="page = 1"
      />

      <div class="flex-1" />

      <!-- Add host button (infra only) -->
      <Button v-if="nav === 'infra'" variant="solid" @click="$emit('add')">Add host</Button>
    </div>

    <!-- Empty state -->
    <div v-if="filtered.length === 0" class="py-12 text-center text-sm text-gray-400">
      No {{ nav === 'infra' ? 'hosts' : 'servers' }} match your filter.
    </div>

    <!-- List view: table -->
    <template v-else-if="view === 'list'">
      <div class="overflow-x-auto rounded-lg border border-gray-200">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-200 bg-gray-50">
              <!-- Server nav columns -->
              <template v-if="nav === 'servers'">
                <th class="w-4 px-3 py-2"></th>
                <th
                  class="cursor-pointer select-none py-2 pr-3 text-left font-medium text-gray-600 hover:text-gray-900"
                  @click="toggleSort('name')"
                >Server {{ sortCaret('name') }}</th>
                <th
                  class="cursor-pointer select-none px-3 py-2 text-left font-medium text-gray-600 hover:text-gray-900"
                  @click="toggleSort('cpu')"
                >CPU {{ sortCaret('cpu') }}</th>
                <th
                  class="cursor-pointer select-none px-3 py-2 text-left font-medium text-gray-600 hover:text-gray-900"
                  @click="toggleSort('mem')"
                >Mem {{ sortCaret('mem') }}</th>
                <th
                  class="cursor-pointer select-none px-3 py-2 text-left font-medium text-gray-600 hover:text-gray-900"
                  @click="toggleSort('disk')"
                >Disk {{ sortCaret('disk') }}</th>
                <th
                  class="cursor-pointer select-none px-3 py-2 text-left font-medium text-gray-600 hover:text-gray-900"
                  @click="toggleSort('benches')"
                >Benches {{ sortCaret('benches') }}</th>
                <th class="px-3 py-2 text-left font-medium text-gray-600">Status</th>
              </template>

              <!-- Infra nav columns -->
              <template v-else>
                <th class="w-4 px-3 py-2"></th>
                <th
                  class="cursor-pointer select-none py-2 pr-3 text-left font-medium text-gray-600 hover:text-gray-900"
                  @click="toggleSort('name')"
                >Host {{ sortCaret('name') }}</th>
                <th class="px-3 py-2 text-left font-medium text-gray-600">Type</th>
                <th
                  class="cursor-pointer select-none px-3 py-2 text-left font-medium text-gray-600 hover:text-gray-900"
                  @click="toggleSort('cpu')"
                >CPU {{ sortCaret('cpu') }}</th>
                <th
                  class="cursor-pointer select-none px-3 py-2 text-left font-medium text-gray-600 hover:text-gray-900"
                  @click="toggleSort('mem')"
                >Mem {{ sortCaret('mem') }}</th>
                <th
                  class="cursor-pointer select-none px-3 py-2 text-left font-medium text-gray-600 hover:text-gray-900"
                  @click="toggleSort('disk')"
                >Disk {{ sortCaret('disk') }}</th>
                <th class="px-3 py-2 text-left font-medium text-gray-600">Status</th>
              </template>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr
              v-for="node in paged"
              :key="node.name"
              class="cursor-pointer hover:bg-gray-50"
              @click="$emit('drill', node.name)"
            >
              <!-- Server nav row -->
              <template v-if="nav === 'servers'">
                <td class="px-3 py-2.5">
                  <span class="inline-block h-[7px] w-[7px] rounded-full" :class="dotClass(nodeDot(node))" />
                </td>
                <td class="py-2.5 pr-3 font-mono font-medium text-gray-900">{{ node.name }}</td>
                <td class="px-3 py-2.5">
                  <MeterBar v-if="node.host?.cpu?.used_pct != null" :value="node.host.cpu.used_pct" />
                  <span v-else class="text-gray-400">-</span>
                </td>
                <td class="px-3 py-2.5">
                  <MeterBar v-if="node.host?.memory?.used_pct != null" :value="node.host.memory.used_pct" />
                  <span v-else class="text-gray-400">-</span>
                </td>
                <td class="px-3 py-2.5">
                  <MeterBar v-if="node.host?.disk?.used_pct != null" :value="node.host.disk.used_pct" />
                  <span v-else class="text-gray-400">-</span>
                </td>
                <td class="px-3 py-2.5 tabular-nums text-gray-700">{{ (node.benches || []).length }}</td>
                <td class="px-3 py-2.5">
                  <span class="flex items-center gap-1.5">
                    <span class="inline-block h-[7px] w-[7px] shrink-0 rounded-full" :class="dotClass(statusInfo(node).dot)" />
                    <span class="text-xs" :class="textClass(statusInfo(node).dot)">{{ statusInfo(node).text }}</span>
                  </span>
                </td>
              </template>

              <!-- Infra nav row -->
              <template v-else>
                <td class="px-3 py-2.5">
                  <span class="inline-block h-[7px] w-[7px] rounded-full" :class="dotClass(nodeDot(node))" />
                </td>
                <td class="py-2.5 pr-3 font-mono font-medium text-gray-900">{{ node.name }}</td>
                <td class="px-3 py-2.5 text-gray-500">{{ node.server_type }}</td>
                <td class="px-3 py-2.5">
                  <MeterBar v-if="node.metrics?.cpu != null" :value="node.metrics.cpu" />
                  <span v-else class="text-gray-400" :title="HOST_STATS_NOTE">n/a</span>
                </td>
                <td class="px-3 py-2.5">
                  <MeterBar v-if="node.metrics?.mem != null" :value="node.metrics.mem" />
                  <span v-else class="text-gray-400" :title="HOST_STATS_NOTE">n/a</span>
                </td>
                <td class="px-3 py-2.5">
                  <MeterBar v-if="node.metrics?.disk != null" :value="node.metrics.disk" />
                  <span v-else class="text-gray-400" :title="HOST_STATS_NOTE">n/a</span>
                </td>
                <td class="px-3 py-2.5">
                  <span class="flex items-center gap-1.5">
                    <span class="inline-block h-[7px] w-[7px] shrink-0 rounded-full" :class="dotClass(statusInfo(node).dot)" />
                    <span class="text-xs" :class="textClass(statusInfo(node).dot)">{{ statusInfo(node).text }}</span>
                  </span>
                </td>
              </template>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="more" class="flex justify-center pt-1">
        <Button variant="subtle" @click="page++">Load {{ remaining }} more</Button>
      </div>
    </template>

    <!-- Cards view -->
    <template v-else>
      <div class="grid gap-3" style="grid-template-columns: repeat(auto-fill, minmax(330px, 1fr))">
        <div
          v-for="node in paged"
          :key="node.name"
          class="cursor-pointer rounded-lg border border-gray-200 p-4 hover:bg-gray-50"
          tabindex="0"
          @click="$emit('drill', node.name)"
          @keyup.enter="$emit('drill', node.name)"
        >
          <div class="mb-3 flex items-center gap-2">
            <span class="inline-block h-[7px] w-[7px] shrink-0 rounded-full" :class="dotClass(nodeDot(node))" />
            <span class="flex-1 truncate font-mono text-sm font-medium text-gray-900">{{ node.name }}</span>
            <span v-if="nav === 'infra'" class="text-xs text-gray-400">{{ node.server_type }}</span>
          </div>

          <!-- Server card metrics -->
          <template v-if="nav === 'servers'">
            <div class="flex flex-col gap-1.5">
              <div class="flex items-center justify-between text-xs text-gray-500">
                <span>CPU</span>
                <MeterBar v-if="node.host?.cpu?.used_pct != null" :value="node.host.cpu.used_pct" />
                <span v-else class="text-gray-400">-</span>
              </div>
              <div class="flex items-center justify-between text-xs text-gray-500">
                <span>Mem</span>
                <MeterBar v-if="node.host?.memory?.used_pct != null" :value="node.host.memory.used_pct" />
                <span v-else class="text-gray-400">-</span>
              </div>
              <div class="flex items-center justify-between text-xs text-gray-500">
                <span>Disk</span>
                <MeterBar v-if="node.host?.disk?.used_pct != null" :value="node.host.disk.used_pct" />
                <span v-else class="text-gray-400">-</span>
              </div>
              <div class="flex items-center justify-between text-xs text-gray-500">
                <span>Benches</span>
                <span class="tabular-nums text-gray-700">{{ (node.benches || []).length }}</span>
              </div>
            </div>
          </template>

          <!-- Infra card metrics: live host CPU/Mem/Disk via the sidecar host-stats probe -->
          <template v-else>
            <div class="flex flex-col gap-1.5">
              <div class="flex items-center justify-between text-xs text-gray-500">
                <span>CPU</span>
                <MeterBar v-if="node.metrics?.cpu != null" :value="node.metrics.cpu" />
                <span v-else class="text-gray-400" :title="HOST_STATS_NOTE">n/a</span>
              </div>
              <div class="flex items-center justify-between text-xs text-gray-500">
                <span>Mem</span>
                <MeterBar v-if="node.metrics?.mem != null" :value="node.metrics.mem" />
                <span v-else class="text-gray-400" :title="HOST_STATS_NOTE">n/a</span>
              </div>
              <div class="flex items-center justify-between text-xs text-gray-500">
                <span>Disk</span>
                <MeterBar v-if="node.metrics?.disk != null" :value="node.metrics.disk" />
                <span v-else class="text-gray-400" :title="HOST_STATS_NOTE">n/a</span>
              </div>
            </div>
          </template>

          <div class="mt-3 border-t border-gray-100 pt-2">
            <span class="flex items-center gap-1.5">
              <span class="inline-block h-[7px] w-[7px] shrink-0 rounded-full" :class="dotClass(statusInfo(node).dot)" />
              <span class="text-xs" :class="textClass(statusInfo(node).dot)">{{ statusInfo(node).text }}</span>
            </span>
          </div>
        </div>
      </div>

      <div v-if="more" class="flex justify-center pt-1">
        <Button variant="subtle" @click="page++">Load {{ remaining }} more</Button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { Button, FormControl } from 'frappe-ui';
import { nodeDot, loadState, summary, isManaged, issues } from './infra-derive';
import MeterBar from './MeterBar.vue';
import SummaryCards from './SummaryCards.vue';

// ─── Props / emits ────────────────────────────────────────────────────────────
const props = defineProps({
  nav:   { type: String, default: 'servers' }, // 'servers' | 'infra'
  nodes: { type: Array,  default: () => [] },
  view:  { type: String, default: 'list' },    // 'list' | 'cards'
});
defineEmits(['drill', 'add']);

// Managed-host CPU/Mem/Disk come from the sidecar host-stats probe; "n/a" means
// the probe could not read them (sidecar missing the host /proc mount, or offline).
const HOST_STATS_NOTE = 'Host stats unavailable: the sidecar could not read the host /proc (re-run it with the host /proc + root mounts).';

// ─── Filter / sort state ──────────────────────────────────────────────────────
const q         = ref('');
const statusSeg = ref('all');
const typeSeg   = ref('all');
const sortKey   = ref('name');
const sortDir   = ref('asc');
const page      = ref(1);
const PER       = 15;

const statusOptions = [
  { label: 'All',     value: 'all'     },
  { label: 'Healthy', value: 'healthy' },
  { label: 'Issues',  value: 'issues'  },
];
const typeOptions = [
  { label: 'All',    value: 'all'    },
  { label: 'Docker', value: 'docker' },
  { label: 'Plain',  value: 'plain'  },
];

// ─── Summary cards ─────────────────────────────────────────────────────────────
const summaryCards = computed(() => {
  if (props.nav === 'infra') {
    const s = summary(props.nodes);
    return [
      { label: 'Hosts',       value: s.hosts },
      { label: 'Units down',  value: s.unitsDown,   bad: true },
      { label: 'Overloaded',  value: s.overloaded,  bad: true },
      { label: 'Unreachable', value: s.unreachable, bad: true },
    ];
  }
  const sumBenches  = props.nodes.reduce((a, n) => a + (n.benches || []).length, 0);
  const benchesDown = props.nodes.reduce(
    (a, n) => a + (n.benches || []).filter(b => b.health !== 'up').length, 0,
  );
  return [
    { label: 'Servers',      value: props.nodes.length },
    { label: 'Benches',      value: sumBenches },
    { label: 'Benches down', value: benchesDown, bad: true },
  ];
});

// ─── Filtered + sorted + paged rows ──────────────────────────────────────────
const filtered = computed(() => {
  let rows = props.nodes;

  if (statusSeg.value === 'healthy') rows = rows.filter(n => nodeDot(n) === 'up');
  else if (statusSeg.value === 'issues') rows = rows.filter(n => nodeDot(n) !== 'up');

  if (props.nav === 'infra' && typeSeg.value !== 'all') {
    rows = rows.filter(n => n.server_type === typeSeg.value);
  }

  if (q.value.trim()) {
    const lq = q.value.trim().toLowerCase();
    rows = rows.filter(n => n.name.toLowerCase().includes(lq));
  }

  return [...rows].sort((a, b) => {
    let av, bv;
    switch (sortKey.value) {
      case 'mem':
        av = props.nav === 'servers' ? (a.host?.memory?.used_pct ?? -1) : (a.metrics?.mem ?? -1);
        bv = props.nav === 'servers' ? (b.host?.memory?.used_pct ?? -1) : (b.metrics?.mem ?? -1);
        break;
      case 'cpu':
        av = props.nav === 'servers' ? (a.host?.cpu?.used_pct ?? -1) : (a.metrics?.cpu ?? -1);
        bv = props.nav === 'servers' ? (b.host?.cpu?.used_pct ?? -1) : (b.metrics?.cpu ?? -1);
        break;
      case 'disk':
        av = props.nav === 'servers' ? (a.host?.disk?.used_pct ?? -1) : (a.metrics?.disk ?? -1);
        bv = props.nav === 'servers' ? (b.host?.disk?.used_pct ?? -1) : (b.metrics?.disk ?? -1);
        break;
      case 'benches': av = (a.benches || []).length; bv = (b.benches || []).length; break;
      default:        av = a.name; bv = b.name; break;
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

// ─── Sort caret (text, not emoji) ────────────────────────────────────────────
function sortCaret(col) {
  if (sortKey.value !== col) return '';
  return sortDir.value === 'asc' ? '^' : 'v';
}

// ─── Dot / text helpers ───────────────────────────────────────────────────────
const DOT_CLASS = {
  up:   'bg-green-500',
  warn: 'bg-amber-500',
  down: 'bg-red-500',
  unk:  'bg-gray-400',
};
const TEXT_CLASS = {
  up:   'text-green-700',
  warn: 'text-amber-700',
  down: 'text-red-700',
  unk:  'text-gray-500',
};
function dotClass(dot)  { return DOT_CLASS[dot]  || 'bg-gray-400'; }
function textClass(dot) { return TEXT_CLASS[dot] || 'text-gray-500'; }

// ─── Status info ──────────────────────────────────────────────────────────────
function statusInfo(node) {
  if (node.health === 'unknown') return { text: 'unreachable', dot: 'unk' };
  const l = loadState(node);
  if (l?.lvl === 'crit') return { text: `overloaded ${l.which} ${l.val}%`, dot: 'down' };
  if (node.health === 'down') {
    const downCount = isManaged(node)
      ? issues([node]).length
      : (node.benches || []).filter(b => b.health !== 'up').length;
    return { text: `${downCount} down`, dot: 'down' };
  }
  if (l?.lvl === 'high') return { text: `high load ${l.which} ${l.val}%`, dot: 'warn' };
  return { text: 'healthy', dot: 'up' };
}
</script>
