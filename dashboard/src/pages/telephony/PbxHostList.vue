<template>
  <div class="flex flex-col gap-4">
    <SummaryCards :cards="cards" />

    <div class="flex flex-wrap items-center gap-2">
      <h2 class="text-sm font-semibold text-gray-900">
        PBX hosts <span class="ml-1 font-normal text-gray-400">({{ rows.length }})</span>
      </h2>
      <div class="flex items-center rounded-md bg-gray-100 p-0.5">
        <button
          v-for="s in segOptions"
          :key="s.value"
          class="rounded px-2 py-0.5 text-xs transition-colors"
          :class="seg === s.value ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
          @click="seg = s.value"
        >{{ s.label }}</button>
      </div>
      <FormControl type="text" placeholder="Search hosts..." v-model="q" class="w-44 text-sm" />
      <div class="flex-1" />
      <Button variant="solid" @click="$emit('provision')">Provision PBX</Button>
    </div>

    <div v-if="rows.length === 0" class="py-12 text-center text-sm text-gray-400">No PBX hosts match your filter.</div>

    <div v-else class="overflow-x-auto rounded-lg border border-gray-200">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-200 bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
            <th class="w-4 px-3 py-2"></th>
            <th class="px-3 py-2">Host</th>
            <th class="px-3 py-2">Container</th>
            <th class="px-3 py-2">Trunks</th>
            <th class="px-3 py-2">Listener</th>
            <th class="px-3 py-2">Calls</th>
            <th class="px-3 py-2">CPU</th>
            <th class="px-3 py-2">Uptime</th>
            <th class="w-24 px-3 py-2"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr
            v-for="h in rows"
            :key="h.name"
            class="group cursor-pointer hover:bg-gray-50 focus:bg-gray-50 focus:outline-none"
            tabindex="0"
            role="button"
            :aria-label="`Open ${h.name}`"
            @click="$emit('open', h.name)"
            @keyup.enter="$emit('open', h.name)"
          >
            <td class="px-3 py-2.5"><span class="inline-block h-[7px] w-[7px] rounded-full" :class="dotClass(hostDot(h))" /></td>
            <td class="px-3 py-2.5"><span class="font-mono font-medium text-gray-900">{{ h.name }}</span> <span class="ml-1 font-mono text-xs text-gray-400">{{ h.ip }}</span></td>
            <td class="px-3 py-2.5">
              <span class="flex items-center gap-1.5 text-xs text-gray-600">
                <span class="h-[7px] w-[7px] rounded-full" :class="h.container === 'running' ? 'bg-green-500' : 'bg-red-500'" />
                {{ h.container }}
              </span>
            </td>
            <td class="px-3 py-2.5"><Badge :label="trunkLabel(h)" :theme="regCounts(h).unreg ? 'orange' : 'green'" /></td>
            <td class="px-3 py-2.5">
              <span class="flex items-center gap-1.5 text-xs" :class="listenerInfo(h).dot === 'up' ? 'text-green-700' : 'text-red-700'">
                <span class="h-[7px] w-[7px] rounded-full" :class="dotClass(listenerInfo(h).dot)" />{{ listenerInfo(h).text }}
              </span>
            </td>
            <td class="px-3 py-2.5 font-mono text-gray-700">{{ h.active_calls }}</td>
            <td class="px-3 py-2.5"><MeterBar v-if="cpuPct(h) != null" :value="cpuPct(h)" /><span v-else class="text-gray-400">n/a</span></td>
            <td class="px-3 py-2.5 text-gray-500">{{ h.uptime }}</td>
            <td class="px-3 py-2.5">
              <div class="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus:opacity-100">
                <button class="rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-800" title="Listener log" @click.stop="$emit('open', h.name, 'logs')">Log</button>
                <button class="rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-800" title="Restart" @click.stop="$emit('restart', h.name)">Restart</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { Button, FormControl, Badge } from 'frappe-ui';
import SummaryCards from '../infrastructure/SummaryCards.vue';
import MeterBar from '../infrastructure/MeterBar.vue';
import { hostDot, listenerInfo, regCounts, cpuPct, summary, filterHosts } from './tele-derive';

const props = defineProps({ hosts: { type: Array, default: () => [] } });
defineEmits(['open', 'provision', 'restart']);

const seg = ref('all');
const q = ref('');
const segOptions = [{ label: 'All', value: 'all' }, { label: 'Registered', value: 'registered' }, { label: 'Issues', value: 'issues' }];

const rows = computed(() => filterHosts(props.hosts, seg.value, q.value));

const cards = computed(() => {
  const s = summary(props.hosts);
  return [
    { label: 'PBX hosts', value: s.hosts },
    { label: 'Trunks', value: s.trunks },
    { label: 'Registered', value: s.registered },
    { label: 'Trunk down', value: s.trunkDown, bad: true },
    { label: 'Active calls', value: s.activeCalls },
    { label: 'Listeners up', value: s.listenersUp },
  ];
});

const DOT_CLASS = { up: 'bg-green-500', warn: 'bg-amber-500', down: 'bg-red-500', unk: 'bg-gray-400' };
const dotClass = (d) => DOT_CLASS[d] || 'bg-gray-400';

function trunkLabel(h) {
  const r = regCounts(h);
  return r.unreg ? 'Unregistered' : `${r.registered} registered`;
}
</script>
