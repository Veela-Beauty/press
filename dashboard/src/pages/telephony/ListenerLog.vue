<template>
  <div>
    <div class="mb-2 flex justify-end">
      <Button size="sm" :loading="loading" @click="fetch">Refresh</Button>
    </div>
    <div class="h-80 overflow-auto rounded-md bg-gray-50 p-3 font-mono text-xs leading-relaxed">
      <span v-if="loading" class="text-gray-400">Loading log...</span>
      <span v-else-if="error" class="text-red-600">{{ error }}</span>
      <template v-else-if="lines.length">
        <div v-for="(l, idx) in lines" :key="idx" class="flex gap-2">
          <span class="text-gray-400">{{ l.ts }}</span>
          <span class="w-10 font-semibold" :class="levelClass(l.level)">{{ l.level }}</span>
          <span class="whitespace-pre-wrap text-gray-700">{{ l.msg }}</span>
        </div>
      </template>
      <span v-else class="text-gray-400">No log output.</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import { Button } from 'frappe-ui';
import { listenerLog } from './tele-api';

const props = defineProps({ host: { type: String, required: true }, active: { type: Boolean, default: false } });
const lines = ref([]);
const error = ref('');
const loading = ref(false);

async function fetch() {
  if (!props.host) return;
  loading.value = true;
  error.value = '';
  try {
    lines.value = await listenerLog(props.host, 200);
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || String(e);
  } finally {
    loading.value = false;
  }
}

const LEVEL = { ERR: 'text-red-600', WARN: 'text-amber-600', INFO: 'text-gray-400' };
const levelClass = (lvl) => LEVEL[lvl] || 'text-gray-400';

// Fetch when the tab becomes active (parent flips `active`) - avoids fetching all 3 tabs on open.
watch(() => props.active, (a) => { if (a) fetch(); }, { immediate: true });
</script>
