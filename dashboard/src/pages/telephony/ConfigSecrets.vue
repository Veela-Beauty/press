<template>
  <div class="space-y-4">
    <div>
      <h3 class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-500">Rendered config (pulled from ERPNext)</h3>
      <dl class="grid grid-cols-2 gap-x-6 gap-y-1.5 rounded-md border border-gray-200 p-3 text-sm">
        <dt class="text-gray-500">Last reload</dt>
        <dd class="font-mono text-gray-900">{{ host.last_reload || '—' }}</dd>
        <dt class="text-gray-500">Firewall</dt>
        <dd class="text-gray-900">{{ host.firewall || 'SIP/RTP to trunk IPs only' }}</dd>
      </dl>
    </div>

    <div>
      <h3 class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-500">Credentials</h3>
      <div class="divide-y divide-gray-100 rounded-md border border-gray-200">
        <div v-for="s in host.secrets || []" :key="s.id" class="flex items-center gap-3 px-3 py-2.5 text-sm">
          <span class="w-36 text-gray-500">{{ s.label }}</span>
          <span class="flex-1 font-mono text-gray-700">{{ s.masked }}</span>
          <span class="text-xs text-gray-400">rotated {{ s.rotated_ago }}</span>
          <Button size="sm" :loading="busy === s.id" @click="confirmRotate(s)">Rotate</Button>
        </div>
        <p v-if="!(host.secrets || []).length" class="px-3 py-3 text-sm text-gray-400">No managed secrets.</p>
      </div>
      <p class="mt-2 rounded-md bg-amber-50 p-2.5 text-xs text-amber-800">
        Stored in the host .env today; rotating regenerates the secret and reloads the container.
        Trunk passwords are never shown here - they live only in ERPNext.
      </p>
    </div>

    <Dialog
      v-model="confirm.open"
      :options="{
        title: confirm.title,
        actions: [
          { label: 'Rotate', variant: 'solid', onClick: doRotate },
          { label: 'Cancel', onClick: () => (confirm.open = false) },
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
import { ref, reactive } from 'vue';
import { Dialog, Button } from 'frappe-ui';
import { toast } from 'vue-sonner';
import { rotateSecret } from './tele-api';

const props = defineProps({ host: { type: Object, required: true } });
const emit = defineEmits(['reload']);

const busy = ref('');
const confirm = reactive({ open: false, title: '', body: '', secret: null });

function confirmRotate(s) {
  confirm.secret = s;
  confirm.title = `Rotate ${s.label}?`;
  confirm.body = `This regenerates the secret, rewrites the host .env, and reloads the container (the listener reconnects).`;
  confirm.open = true;
}

async function doRotate() {
  confirm.open = false;
  const s = confirm.secret;
  if (!s) return;
  busy.value = s.id;
  try {
    await rotateSecret(props.host.name, s.id);
    toast.success(`${s.label} rotated - listener reconnected`);
    emit('reload');
  } catch (e) {
    toast.error(e?.messages?.join(', ') || e?.message || 'Rotate failed');
  } finally {
    busy.value = '';
    confirm.secret = null;
  }
}
</script>
