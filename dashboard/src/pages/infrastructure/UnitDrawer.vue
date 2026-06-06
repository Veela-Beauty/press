<template>
  <Dialog
    :modelValue="!!unit"
    :options="{ size: '3xl' }"
    @update:modelValue="(v) => { if (!v) $emit('close'); }"
  >
    <template #body-content>
      <div v-if="unit" class="space-y-4">

        <!-- Header -->
        <div class="flex items-center gap-3 border-b border-gray-100 pb-3">
          <span
            class="h-2 w-2 shrink-0 rounded-full"
            :class="dotClass(unit.state)"
          />
          <span class="font-medium text-gray-900">{{ unit.name }}</span>
          <StatusBadge :state="unit.state" />
          <span class="font-mono text-xs text-gray-500">{{ unit.sub }}</span>
        </div>

        <!-- Tab strip -->
        <div class="flex gap-1 border-b border-gray-100">
          <button
            v-for="t in TABS"
            :key="t.id"
            class="px-3 py-1.5 text-sm transition-colors"
            :class="tab === t.id
              ? 'border-b-2 border-gray-900 font-medium text-gray-900'
              : 'text-gray-500 hover:text-gray-700'"
            @click="tab = t.id"
          >{{ t.label }}</button>
        </div>

        <!-- Logs tab -->
        <div v-if="tab === 'logs'">
          <div v-if="!controllable(unit)" class="rounded-md bg-gray-50 p-4 text-sm text-gray-400">
            Logs are docker-only in v1 (this is a systemd unit).
          </div>
          <template v-else>
            <div class="mb-2 flex justify-end">
              <Button size="sm" :loading="loading" @click="fetchLogs">Refresh</Button>
            </div>
            <div class="h-80 overflow-auto rounded-md bg-gray-50 p-3 font-mono text-xs leading-relaxed">
              <span v-if="loading" class="text-gray-400">Loading logs...</span>
              <span v-else-if="logError" class="text-red-600">{{ logError }}</span>
              <template v-else-if="lines.length">
                <div v-for="(line, i) in lines" :key="i">{{ line }}</div>
              </template>
              <span v-else class="text-gray-400">No log output.</span>
            </div>
          </template>
        </div>

        <!-- Inspect tab -->
        <div v-else-if="tab === 'inspect'">
          <dl class="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <template v-for="row in inspectRows" :key="row.label">
              <dt class="text-gray-500">{{ row.label }}</dt>
              <dd class="font-mono text-gray-900 break-all">{{ row.value }}</dd>
            </template>
          </dl>
        </div>

        <!-- Stats tab -->
        <div v-else-if="tab === 'stats'">
          <div class="rounded-md border border-gray-100 bg-gray-50 p-4 text-sm text-gray-400">
            Live CPU/memory stats are not collected in v1.
          </div>
        </div>

        <!-- Footer: Restart (docker units only) -->
        <div
          v-if="controllable(unit)"
          class="flex justify-end border-t border-gray-100 pt-3"
        >
          <Button variant="solid" :loading="acting" @click="restart">Restart</Button>
        </div>

      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { Dialog, Button } from 'frappe-ui';
import { toast } from 'vue-sonner';
import StatusBadge from './StatusBadge.vue';
import { unitLog, unitAction } from './infra-api';
import { controllable, stateLabel } from './infra-derive';

// ─── Props / emits ────────────────────────────────────────────────────────────
const props = defineProps({
  host: { type: String, required: true },
  unit: { type: Object, default: null },
});
const emit = defineEmits(['close', 'reload']);

// ─── Tab state ────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'logs',    label: 'Logs'    },
  { id: 'inspect', label: 'Inspect' },
  { id: 'stats',   label: 'Stats'   },
];
const tab = ref('logs');

// ─── Logs state ───────────────────────────────────────────────────────────────
const lines    = ref([]);
const logError = ref('');
const loading  = ref(false);

async function fetchLogs() {
  if (!props.unit || !controllable(props.unit)) return;
  loading.value  = true;
  logError.value = '';
  try {
    lines.value = await unitLog(props.host, props.unit._id, 200);
  } catch (e) {
    logError.value = e?.message || String(e);
  } finally {
    loading.value = false;
  }
}

// Fetch logs whenever the drawer opens (unit becomes non-null)
watch(
  () => props.unit,
  (u) => {
    if (u) {
      tab.value      = 'logs';
      lines.value    = [];
      logError.value = '';
      fetchLogs();
    }
  },
);

// ─── Inspect rows ─────────────────────────────────────────────────────────────
const inspectRows = computed(() => {
  const u = props.unit;
  if (!u) return [];
  return [
    { label: 'Name',     value: u.name },
    { label: 'Image',    value: u.sub  },
    { label: 'State',    value: stateLabel(u.state) },
    { label: 'Uptime',   value: u.uptime   ?? '—' },
    { label: 'Restarts', value: String(u.restarts ?? '—') },
    { label: 'Ports',    value: u.ports    || '—' },
    { label: 'PID',      value: String(u.pid ?? '—') },
    { label: 'Read via', value: 'Docker API (socket-proxy over SSH cert)' },
  ];
});

// ─── State dot ────────────────────────────────────────────────────────────────
function dotClass(state) {
  if (['run', 'heal', 'active'].includes(state)) return 'bg-green-500';
  if (['stop', 'down', 'exit2', 'dead'].includes(state)) return 'bg-red-500';
  if (['restart', 'unhealth', 'pause'].includes(state)) return 'bg-orange-400';
  return 'bg-gray-400';
}

// ─── Actions ──────────────────────────────────────────────────────────────────
const acting = ref(false);

async function restart() {
  if (!props.unit) return;
  acting.value = true;
  try {
    await unitAction(props.host, props.unit._id, 'restart');
    toast.success(props.unit.name + ' restart - logged');
    emit('reload');
  } catch (e) {
    toast.error(e?.message || 'Restart failed');
  } finally {
    acting.value = false;
  }
}
</script>
