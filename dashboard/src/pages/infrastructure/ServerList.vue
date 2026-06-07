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

<script setup>
import { ref, computed } from 'vue';
import { Button, FormControl } from 'frappe-ui';
import { nodeDot, loadState, summary, isManaged, issues, cpuPct, memPct, diskPct } from './infra-derive';
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
