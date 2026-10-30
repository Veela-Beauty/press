<template>
  <!-- Rows shown under an expanded server in ServerList: a managed host's containers,
       or a Press server's benches. Rendered inside the server table's <tbody>. -->
  <template v-if="isManaged(node)">
    <tr v-if="node.health === 'unknown'" class="bg-gray-50/60">
      <td />
      <td colspan="6" class="py-2 pl-8 pr-3 text-xs text-amber-700">This host is unreachable: check the SSH cert / socket-proxy.</td>
    </tr>
    <tr v-if="node.server_type === 'plain'" class="bg-gray-50/60">
      <td />
      <td colspan="6" class="py-2 pl-8 pr-3 text-xs text-gray-500">Plain host: watch-only (systemd status, no control).</td>
    </tr>

    <template v-if="units.length">
      <tr class="bg-gray-50/60 text-[11px] uppercase tracking-wide text-gray-500">
        <td />
        <td class="py-1.5 pl-8 pr-3">{{ kindLabel }}</td>
        <td colspan="2" class="px-3 py-1.5">Image</td>
        <td class="px-3 py-1.5">Status</td>
        <td class="px-3 py-1.5">Uptime</td>
        <td class="px-3 py-1.5">Restarts &middot; Actions</td>
      </tr>
      <tr v-for="u in shown" :key="u._id || u.name" class="bg-gray-50/60">
        <td class="px-3 py-2">
          <span class="ml-[22px] inline-block h-[7px] w-[7px] rounded-full" :class="UNIT_DOT[uDot(u.state)]" />
        </td>
        <td class="py-2 pl-8 pr-3" :class="canStart(u.state) ? 'text-gray-500' : 'text-gray-900'">{{ u.name }}</td>
        <td colspan="2" class="max-w-xs truncate px-3 py-2 font-mono text-xs text-gray-500" :title="u.image || u.sub">{{ u.image || u.sub || '-' }}</td>
        <td class="px-3 py-2">
          <span v-if="busy[u._id]" class="text-xs text-gray-500">{{ busy[u._id] }}...</span>
          <StatusBadge v-else :state="u.state" />
        </td>
        <td class="whitespace-nowrap px-3 py-2 text-gray-600" :title="u.uptime">{{ shortUptime(u.uptime) }}</td>
        <td class="px-3 py-2">
          <div class="flex items-center gap-1">
            <span class="w-5 text-gray-400">{{ u.restarts ?? '-' }}</span>
            <template v-if="controllable(u)">
              <Button v-if="canStart(u.state)" size="sm" variant="ghost" theme="green" :disabled="!!busy[u._id]" @click.stop="run(u, 'start')">Start</Button>
              <template v-else>
                <Button size="sm" variant="ghost" :disabled="!!busy[u._id]" @click.stop="run(u, 'restart')">Restart</Button>
                <Button size="sm" variant="ghost" theme="red" :disabled="!!busy[u._id]" @click.stop="run(u, 'stop')">Stop</Button>
              </template>
            </template>
            <Button v-if="controllable(u)" size="sm" variant="ghost" @click.stop="$emit('openUnit', u)">Logs</Button>
          </div>
        </td>
      </tr>
      <tr v-if="units.length > PER && !showAll" class="bg-gray-50/60">
        <td colspan="7" class="py-2 text-center">
          <button class="text-sm text-blue-600 hover:underline" @click.stop="showAll = true">Show {{ units.length - PER }} more {{ kindLabel.toLowerCase() }}s</button>
        </td>
      </tr>
    </template>
    <tr v-else class="bg-gray-50/60">
      <td />
      <td colspan="6" class="py-2 pl-8 pr-3 text-sm text-gray-400">No {{ kindLabel.toLowerCase() }}s.</td>
    </tr>
  </template>

  <template v-else>
    <template v-if="benches.length">
      <tr class="bg-gray-50/60 text-[11px] uppercase tracking-wide text-gray-500">
        <td />
        <td class="py-1.5 pl-8 pr-3">Bench</td>
        <td colspan="2" class="px-3 py-1.5">Services</td>
        <td class="px-3 py-1.5">Sites</td>
        <td colspan="2" />
      </tr>
      <tr v-for="b in benches" :key="b.name" class="bg-gray-50/60">
        <td class="px-3 py-2">
          <span class="ml-[22px] inline-block h-[7px] w-[7px] rounded-full" :class="b.health === 'up' ? 'bg-green-500' : b.health === 'unknown' ? 'bg-gray-400' : 'bg-red-500'" />
        </td>
        <td class="py-2 pl-8 pr-3 font-mono text-sm text-gray-900">{{ b.name }}</td>
        <td colspan="2" class="px-3 py-2 text-gray-600">{{ b.services_up ?? 0 }} up / {{ b.services_down ?? 0 }} down</td>
        <td class="px-3 py-2 text-gray-600">{{ b.site_count ?? '-' }}</td>
        <td colspan="2" class="px-3 py-2">
          <button class="text-sm text-blue-600 hover:underline" @click.stop="router.push(`/servers/${node.name}`)">Open server page</button>
        </td>
      </tr>
    </template>
    <tr v-else class="bg-gray-50/60">
      <td />
      <td colspan="6" class="py-2 pl-8 pr-3 text-sm text-gray-400">No benches.</td>
    </tr>
  </template>
</template>

<script setup>
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import { Button } from 'frappe-ui';
import { toast } from 'vue-sonner';
import { confirmDialog } from '@/utils/components';
import StatusBadge from './StatusBadge.vue';
import { canStart, controllable, isManaged, shortUptime, uDot } from './infra-derive';
import { unitAction, unitBusy as busy } from './infra-api';

const props = defineProps({ node: { type: Object, required: true } });
const emit = defineEmits(['openUnit', 'reload']);
const router = useRouter();

const PER = 8;
const showAll = ref(false);
const units = computed(() => props.node.units || []);
const shown = computed(() => (showAll.value ? units.value : units.value.slice(0, PER)));
const benches = computed(() => props.node.benches || []);
const kindLabel = computed(() => (props.node.server_type === 'plain' ? 'Service' : 'Container'));

const UNIT_DOT = { up: 'bg-green-500', unk: 'bg-gray-400', down: 'bg-red-500' };
const BUSY_LABEL = { start: 'starting', stop: 'stopping', restart: 'restarting' };

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

function run(u, action) {
  if (action !== 'stop') return proceed(u, action);
  confirmDialog({
    title: `Stop ${u.name}?`,
    message: `<b>${esc(u.name)}</b> on ${esc(props.node.name)} will be unavailable until you start it again. The action is logged.`,
    primaryAction: {
      label: 'Stop',
      variant: 'solid',
      theme: 'red',
      onClick: ({ hide }) => {
        hide();
        proceed(u, 'stop');
      },
    },
  });
}

async function proceed(u, action) {
  busy[u._id] = BUSY_LABEL[action];
  try {
    await unitAction(props.node.name, u._id, action);
    toast.success(`${u.name}: ${action} done (logged)`);
    emit('reload');
  } catch (e) {
    toast.error(e.messages?.join(', ') || e.message || `${action} failed`);
  } finally {
    delete busy[u._id];
  }
}
</script>
