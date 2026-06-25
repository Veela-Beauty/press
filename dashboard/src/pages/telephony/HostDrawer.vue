<template>
  <Dialog
    :modelValue="!!host"
    :options="{ size: '4xl', title: host ? host.name : '' }"
    @update:modelValue="(v) => { if (!v) $emit('close'); }"
  >
    <template #body-content>
      <div v-if="host" class="space-y-4">
        <!-- Header -->
        <div class="flex flex-wrap items-center gap-3 border-b border-gray-100 pb-3">
          <span class="h-2 w-2 shrink-0 rounded-full" :class="dotClass(hostDot(host))" />
          <span class="font-mono font-medium text-gray-900">{{ host.name }}</span>
          <span class="font-mono text-xs text-gray-400">{{ host.ip }}</span>
          <div class="flex-1" />
          <span class="flex items-center gap-1.5 text-xs" :class="listenerInfo(host).dot === 'up' ? 'text-green-700' : 'text-red-700'">
            <span class="h-[7px] w-[7px] rounded-full" :class="dotClass(listenerInfo(host).dot)" />
            listener {{ listenerInfo(host).text }}
          </span>
        </div>

        <!-- Action bar -->
        <div class="flex flex-wrap items-center gap-2 border-b border-gray-100 pb-3">
          <Button :loading="acting === 'reregister'" @click="run('reregister')">Re-register trunk</Button>
          <Button :loading="acting === 'restart'" @click="askStopRestart('restart')">Restart</Button>
          <Button :loading="acting === 'firewall_test'" @click="run('firewall_test')">Firewall test</Button>
          <Button theme="red" :loading="acting === 'stop'" @click="askStopRestart('stop')">Stop</Button>
          <div class="flex-1" />
          <Button theme="red" variant="subtle" @click="decom = true">Decommission</Button>
        </div>

        <!-- Action result line -->
        <div v-if="actResult" class="rounded-md p-2.5 text-sm" :class="actResult.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'">
          {{ actResult.detail }}
        </div>

        <!-- Tab strip -->
        <div class="flex gap-1 border-b border-gray-100">
          <button
            v-for="t in TABS"
            :key="t.id"
            class="px-3 py-1.5 text-sm transition-colors"
            :class="tab === t.id ? 'border-b-2 border-gray-900 font-medium text-gray-900' : 'text-gray-500 hover:text-gray-700'"
            @click="tab = t.id"
          >{{ t.label }}</button>
        </div>

        <HostDetail :host="host" :tab="tab" @reload="$emit('reload')" />
      </div>
    </template>
  </Dialog>

  <ConfirmDialog
    :open="confirm.open"
    :title="confirm.title"
    :body="confirm.body"
    :confirm-label="confirm.label"
    :danger="confirm.danger"
    :show-drain="confirm.showDrain"
    @confirm="onConfirm"
    @drain="onDrain"
    @cancel="confirm.open = false"
  />

  <DecommissionDialog
    :open="decom"
    :host-name="host?.name || ''"
    :instances="host?.instances || []"
    @close="decom = false"
    @done="$emit('reload')"
  />
</template>

<script setup>
import { ref, reactive, watch } from 'vue';
import { Dialog, Button } from 'frappe-ui';
import { toast } from 'vue-sonner';
import HostDetail from './HostDetail.vue';
import ConfirmDialog from './ConfirmDialog.vue';
import DecommissionDialog from './DecommissionDialog.vue';
import { hostDot, listenerInfo } from './tele-derive';
import { hostAction } from './tele-api';

const props = defineProps({ host: { type: Object, default: null } });
const emit = defineEmits(['close', 'reload']);

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'logs', label: 'Listener log' },
  { id: 'config', label: 'Config & secrets' },
];
const tab = ref('overview');
const acting = ref('');
const actResult = ref(null);
const decom = ref(false);

watch(() => props.host, (h) => {
  if (h) {
    tab.value = h._initialTab || 'overview';
    actResult.value = null;
  }
});

const DOT_CLASS = { up: 'bg-green-500', warn: 'bg-amber-500', down: 'bg-red-500', unk: 'bg-gray-400' };
const dotClass = (d) => DOT_CLASS[d] || 'bg-gray-400';

const confirm = reactive({ open: false, action: '', title: '', body: '', label: '', danger: false, showDrain: false });

// Stop/Restart guard active calls; reregister/firewall_test run immediately.
function askStopRestart(action) {
  if ((props.host?.active_calls || 0) > 0) {
    confirm.action = action;
    confirm.title = `${cap(action)} ${props.host.name}?`;
    confirm.body = `<b>${props.host.name}</b> has <b>${props.host.active_calls} active call(s)</b>. ${cap(action)}ing Asterisk now will drop them.`;
    confirm.label = cap(action);
    confirm.danger = action === 'stop';
    confirm.showDrain = true;
    confirm.open = true;
  } else {
    run(action);
  }
}
function onConfirm() { confirm.open = false; run(confirm.action); }
function onDrain() { confirm.open = false; toast.success('Scheduled - will run once calls drain'); }
function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

async function run(action) {
  acting.value = action;
  actResult.value = null;
  try {
    const res = await hostAction(props.host.name, action);
    actResult.value = { ok: res.ok !== false, detail: res.detail || `${action} done` };
    emit('reload');
  } catch (e) {
    actResult.value = { ok: false, detail: e?.messages?.join(', ') || e?.message || `${action} failed` };
  } finally {
    acting.value = '';
  }
}
</script>
