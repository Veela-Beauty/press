<template>
  <div class="rounded-lg border border-gray-200 p-4">
    <div class="flex items-center gap-2">
      <span class="inline-block h-[7px] w-[7px] shrink-0 rounded-full" :class="rows.length ? 'bg-amber-500' : 'bg-green-500'" />
      <h2 class="text-sm font-semibold text-gray-900">{{ rows.length ? 'Needs attention' : 'All clear' }}</h2>
      <span class="text-xs text-gray-500">{{ rows.length ? `· ${rows.length}` : 'Nothing needs attention.' }}</span>
    </div>
    <div v-if="rows.length" class="mt-3 flex flex-col gap-2">
      <div v-for="(r, i) in shown" :key="i" class="flex items-center gap-2">
        <span class="inline-block h-[7px] w-[7px] shrink-0 rounded-full" :class="r.kind === 'host_down' ? 'bg-red-500' : 'bg-amber-500'" />
        <span class="font-mono text-sm text-gray-900">{{ r.host }}</span>
        <span class="text-xs text-gray-400">{{ r.detail }}</span>
        <div class="flex-1" />
        <Button variant="subtle" @click="$emit('view', r.host)">Open</Button>
      </div>
      <div v-if="rows.length > 4" class="text-xs text-gray-400">+{{ rows.length - 4 }} more</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { Button } from 'frappe-ui';
import { attention } from './tele-derive';
const props = defineProps({ hosts: { type: Array, default: () => [] } });
defineEmits(['view']);
const rows = computed(() => attention(props.hosts));
const shown = computed(() => rows.value.slice(0, 4));
</script>
