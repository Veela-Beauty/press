<template>
  <Dialog
    :modelValue="open"
    @update:modelValue="(v) => { if (!v && status?.state !== 'running') $emit('close'); }"
    :options="{ title: titleText }"
  >
    <template #body-content>
      <div v-if="status" class="space-y-4">
        <!-- Success -->
        <div v-if="status.state === 'done'" class="space-y-3 text-center">
          <div class="mx-auto grid h-14 w-14 place-items-center rounded-full bg-green-50 text-2xl text-green-600">&#10003;</div>
          <h3 class="text-base font-semibold text-gray-900">PBX online</h3>
          <p class="text-sm text-gray-500">{{ host }} is now serving the company. The container pulled the config and registered.</p>
        </div>

        <!-- Failure -->
        <div v-else-if="status.state === 'failed'" class="space-y-3">
          <div class="mx-auto grid h-14 w-14 place-items-center rounded-full bg-red-50 text-2xl text-red-600">&#33;</div>
          <h3 class="text-center text-base font-semibold text-gray-900">Provision did not complete</h3>
          <ul class="space-y-1.5">
            <li v-for="s in status.steps" :key="s.key" class="flex items-center gap-2 text-sm" :class="stepTextClass(s.state)">
              <span class="w-4 text-center">{{ stepIcon(s.state) }}</span>{{ s.label }}
            </li>
          </ul>
          <div v-if="status.failure" class="rounded-md border border-red-200 bg-red-50 p-2.5 text-sm text-red-700">
            {{ status.failure.detail }}
            <span v-if="rollbackable(status)"> Rolling back closes the firewall and revokes the minted token; nothing is left half-open.</span>
          </div>
        </div>

        <!-- Running -->
        <ul v-else class="space-y-1.5">
          <li v-for="s in status.steps" :key="s.key" class="flex items-center gap-2 text-sm" :class="stepTextClass(s.state)">
            <span class="w-4 text-center">
              <LoadingIndicator v-if="s.state === 'running'" class="inline h-3.5 w-3.5 text-blue-600" />
              <template v-else>{{ stepIcon(s.state) }}</template>
            </span>{{ s.label }}
          </li>
        </ul>
      </div>
    </template>

    <template v-if="status && status.state !== 'running'" #actions>
      <div class="flex items-center justify-end gap-2">
        <template v-if="status.state === 'done'">
          <Button @click="$emit('close')">Done</Button>
          <Button variant="solid" @click="$emit('open-host', host)">Open host</Button>
        </template>
        <template v-else>
          <Button @click="$emit('view-log', host)">View listener log</Button>
          <Button v-if="rollbackable(status)" theme="red" variant="subtle" @click="$emit('rollback')">Roll back</Button>
          <Button variant="solid" @click="$emit('retry')">Retry</Button>
        </template>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed } from 'vue';
import { Dialog, Button, LoadingIndicator } from 'frappe-ui';
import { rollbackable } from './tele-derive';

const props = defineProps({ open: Boolean, host: { type: String, default: '' }, status: { type: Object, default: null } });
defineEmits(['close', 'open-host', 'view-log', 'rollback', 'retry']);

const titleText = computed(() => {
  if (!props.status || props.status.state === 'running') return `Provisioning ${props.host}`;
  return '';
});

const ICON = { done: '✓', failed: '✗', skipped: '–', pending: '○', running: '' };
const TEXT = { done: 'text-gray-900', failed: 'text-red-600', skipped: 'text-gray-400', pending: 'text-gray-500', running: 'text-blue-700' };
const stepIcon = (s) => ICON[s] ?? '○';
const stepTextClass = (s) => TEXT[s] || 'text-gray-500';
</script>
