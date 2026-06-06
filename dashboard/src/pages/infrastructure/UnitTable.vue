<template>
  <div>
    <table v-if="units.length" class="w-full text-sm">
      <thead>
        <tr class="border-b border-gray-200 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
          <th class="pb-2 pr-3 w-4"></th>
          <th class="pb-2 pr-4">Name</th>
          <th class="pb-2 pr-4">Image / Sub</th>
          <th class="pb-2 pr-4">Status</th>
          <th class="pb-2 pr-4">Uptime</th>
          <th class="pb-2 pr-4">Restarts</th>
          <th class="pb-2">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="u in units"
          :key="u._id || u.name"
          class="group border-b border-gray-100 last:border-0 hover:bg-gray-50"
        >
          <!-- dot -->
          <td class="py-2.5 pr-3 align-middle">
            <span
              class="inline-block h-[7px] w-[7px] rounded-full"
              :class="{
                up: 'bg-green-500',
                unk: 'bg-gray-400',
                down: 'bg-red-500',
              }[uDot(u.state)]"
            />
          </td>

          <!-- name -->
          <td class="py-2.5 pr-4 align-middle font-medium text-gray-900">
            {{ u.name }}
          </td>

          <!-- image / sub -->
          <td class="py-2.5 pr-4 align-middle font-mono text-xs text-gray-500">
            {{ u.image || u.sub || '—' }}
          </td>

          <!-- status -->
          <td class="py-2.5 pr-4 align-middle">
            <span v-if="busy.has(u._id)" class="flex items-center gap-1.5 text-gray-500">
              <svg class="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
              <span class="text-xs">restarting…</span>
            </span>
            <StatusBadge v-else :state="u.state" />
          </td>

          <!-- uptime -->
          <td class="py-2.5 pr-4 align-middle text-gray-500">
            {{ u.uptime || '—' }}
          </td>

          <!-- restarts -->
          <td class="py-2.5 pr-4 align-middle text-gray-500">
            {{ u.restarts ?? '—' }}
          </td>

          <!-- actions -->
          <td class="py-2.5 align-middle">
            <div v-if="controllable(u)" class="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
              <!-- Restart -->
              <button
                class="rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-800 disabled:cursor-not-allowed disabled:opacity-40"
                title="Restart"
                :disabled="busy.has(u._id)"
                @click.stop="run(u, 'restart')"
              >
                <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="1 4 1 10 7 10" />
                  <path d="M3.51 15a9 9 0 1 0 .49-3.5" />
                </svg>
              </button>

              <!-- Stop -->
              <button
                class="rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-800 disabled:cursor-not-allowed disabled:opacity-40"
                title="Stop"
                :disabled="busy.has(u._id) || isDown(u.state)"
                @click.stop="run(u, 'stop')"
              >
                <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                </svg>
              </button>

              <!-- Logs -->
              <button
                class="rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-800"
                title="Logs"
                @click.stop="$emit('openUnit', u)"
              >
                <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <polyline points="10 9 9 9 8 9" />
                </svg>
              </button>
            </div>

            <!-- systemd: watch-only label -->
            <span v-else class="text-xs text-gray-400">watch-only</span>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- empty -->
    <p v-else class="py-4 text-sm text-gray-400">No units reported.</p>

    <!-- Confirm dialog for destructive actions -->
    <Dialog
      v-model="confirm.open"
      :options="{
        title: confirm.title,
        actions: [
          {
            label: confirm.action === 'stop' ? 'Stop' : 'Kill',
            variant: 'solid',
            theme: 'red',
            onClick: doConfirmed,
          },
          {
            label: 'Cancel',
            onClick: () => (confirm.open = false),
          },
        ],
      }"
    >
      <template #body-content>
        <p class="text-sm text-gray-700">{{ confirm.body }}</p>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { reactive } from 'vue';
// busy uses reactive object map (not Set) so Vue tracks .add/.delete via property mutation
import { Dialog } from 'frappe-ui';
import { toast } from 'vue-sonner';
import StatusBadge from './StatusBadge.vue';
import { uDot, controllable, isDown } from './infra-derive';
import { unitAction } from './infra-api';

const props = defineProps({
  host: { type: String, required: true },
  units: { type: Array, default: () => [] },
});

const emit = defineEmits(['openUnit', 'reload']);

// Track in-flight actions by unit _id (reactive object map: id -> true)
const busyMap = reactive({});
const busy = {
  has: (id) => !!busyMap[id],
  add: (id) => { busyMap[id] = true; },
  delete: (id) => { delete busyMap[id]; },
};

// Confirm dialog state
const confirm = reactive({
  open: false,
  title: '',
  body: '',
  action: '',
  unit: null,
});

function run(u, action) {
  if (action === 'stop' || action === 'kill') {
    confirm.unit = u;
    confirm.action = action;
    confirm.title = action === 'stop' ? `Stop ${u.name}?` : `Kill ${u.name}?`;
    confirm.body =
      action === 'stop'
        ? `"${u.name}" will be unavailable until restarted.`
        : `Sending SIGKILL to "${u.name}" may lose in-flight work.`;
    confirm.open = true;
  } else {
    proceed(u, action);
  }
}

async function doConfirmed() {
  confirm.open = false;
  if (confirm.unit) {
    await proceed(confirm.unit, confirm.action);
    confirm.unit = null;
  }
}

async function proceed(u, action) {
  busy.add(u._id);
  try {
    await unitAction(props.host, u._id, action);
    toast.success(`${u.name} ${action} — logged`);
    emit('reload');
  } catch (e) {
    toast.error(e.messages?.join(', ') || e.message || 'Action failed');
  } finally {
    busy.delete(u._id);
  }
}
</script>
