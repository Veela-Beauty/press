<template>
  <Dialog
    :modelValue="open"
    @update:modelValue="(v) => { if (!v) $emit('cancel'); }"
    :options="{ title }"
  >
    <template #body-content>
      <p class="text-sm text-gray-700" v-html="body" />
    </template>
    <template #actions>
      <div class="flex items-center justify-end gap-2">
        <Button @click="$emit('cancel')">Cancel</Button>
        <Button v-if="showDrain" @click="$emit('drain')">Wait for calls to drain</Button>
        <Button variant="solid" :theme="danger ? 'red' : 'gray'" @click="$emit('confirm')">{{ confirmLabel }}</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { Dialog, Button } from 'frappe-ui';
defineProps({
  open: Boolean,
  title: { type: String, default: 'Confirm' },
  body: { type: String, default: '' },
  confirmLabel: { type: String, default: 'Continue' },
  danger: { type: Boolean, default: false },
  showDrain: { type: Boolean, default: false },
});
defineEmits(['confirm', 'cancel', 'drain']);
</script>
