<template>
  <Dialog
    :modelValue="open"
    @update:modelValue="(v) => { if (!v) $emit('close'); }"
    :options="{ title: `Decommission ${hostName}` }"
  >
    <template #body-content>
      <div class="space-y-3 text-sm text-gray-700">
        <p>This permanently tears the PBX host down:</p>
        <ul class="list-disc space-y-1 pl-5 text-gray-600">
          <li>Stop and remove oc-asterisk + oc-listener</li>
          <li>Close the firewall to the trunk IPs</li>
          <li>Revoke the listener API token</li>
          <li>Keep the recordings on the host</li>
        </ul>
        <!-- decommission_pbx is per host:instance; pick the instance when the host serves several -->
        <FormControl
          v-if="instances.length > 1"
          type="select"
          label="OC Channel Instance to decommission"
          :options="instanceOptions"
          v-model="instance"
        />
        <p v-else-if="instances.length === 1" class="text-xs text-gray-500">
          Instance <span class="font-mono">{{ instance }}</span> on this host will be torn down.
        </p>
        <FormControl
          type="text"
          label="Type the host name to confirm"
          v-model="typed"
          :placeholder="hostName"
        />
      </div>
    </template>
    <template #actions>
      <div class="flex items-center justify-end gap-2">
        <Button @click="$emit('close')">Cancel</Button>
        <Button variant="solid" theme="red" :disabled="!canGo" :loading="busy" @click="go">Decommission</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { Dialog, Button, FormControl } from 'frappe-ui';
import { toast } from 'vue-sonner';
import { decommissionPbx } from './tele-api';

const props = defineProps({
  open: Boolean,
  hostName: { type: String, default: '' },
  instances: { type: Array, default: () => [] }, // [{ instance, ... }]
});
const emit = defineEmits(['close', 'done']);
const typed = ref('');
const instance = ref('');
const busy = ref(false);

const instanceOptions = computed(() =>
  props.instances.map((i) => ({ label: i.instance, value: i.instance })),
);
const canGo = computed(() => typed.value.trim() === props.hostName && !!instance.value);

watch(() => props.open, (o) => {
  if (o) {
    typed.value = '';
    instance.value = props.instances[0]?.instance || '';
  }
});

async function go() {
  busy.value = true;
  try {
    await decommissionPbx(props.hostName, instance.value);
    toast.success(`Decommission started for ${props.hostName}`);
    emit('done');
    emit('close');
  } catch (e) {
    toast.error(e?.messages?.join(', ') || e?.message || 'Decommission failed');
  } finally {
    busy.value = false;
  }
}
</script>
