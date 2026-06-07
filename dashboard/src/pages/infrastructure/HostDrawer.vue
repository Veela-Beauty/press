<template>
  <Dialog
    :modelValue="!!node"
    :options="{ size: '4xl' }"
    @update:modelValue="(v) => { if (!v) $emit('close'); }"
  >
    <template #body-content>
      <div v-if="node" class="space-y-4">
        <!-- Header: name + type badge + live metrics -->
        <div class="flex flex-wrap items-center gap-3 border-b border-gray-100 pb-3">
          <span class="h-2 w-2 shrink-0 rounded-full" :class="dotClass(nodeDot(node))" />
          <span class="font-mono font-medium text-gray-900">{{ node.name }}</span>
          <span class="rounded-full px-2 py-0.5 text-[11px] font-semibold" :class="isManaged(node) ? 'bg-blue-50 text-blue-700' : 'bg-gray-100 text-gray-600'">
            {{ isManaged(node) ? 'Managed' : 'Press' }}
          </span>
          <div class="flex-1" />
          <div class="flex items-center gap-4 text-xs text-gray-500">
            <span class="flex items-center gap-1">CPU <MeterBar v-if="cpuPct(node) != null" :value="cpuPct(node)" /><span v-else>n/a</span></span>
            <span class="flex items-center gap-1">Mem <MeterBar v-if="memPct(node) != null" :value="memPct(node)" /><span v-else>n/a</span></span>
            <span class="flex items-center gap-1">Disk <MeterBar v-if="diskPct(node) != null" :value="diskPct(node)" /><span v-else>n/a</span></span>
          </div>
        </div>

        <!-- Body: HostDetail is already type-aware (managed control vs Press read-only) -->
        <HostDetail :node="node" @openUnit="onOpenUnit" @reload="$emit('reload')" />
      </div>
    </template>
  </Dialog>

  <!-- Nested unit drawer (managed unit logs / control) -->
  <UnitDrawer
    :host="node?.name"
    :unit="unit"
    @close="unit = null"
    @reload="$emit('reload')"
  />
</template>

<script setup>
import { ref } from 'vue';
import { Dialog } from 'frappe-ui';
import HostDetail from './HostDetail.vue';
import UnitDrawer from './UnitDrawer.vue';
import MeterBar from './MeterBar.vue';
import { isManaged, nodeDot, cpuPct, memPct, diskPct } from './infra-derive';

defineProps({ node: { type: Object, default: null } });
defineEmits(['close', 'reload']);

const unit = ref(null);
function onOpenUnit(u) { unit.value = u; }

const DOT_CLASS = { up: 'bg-green-500', warn: 'bg-amber-500', down: 'bg-red-500', unk: 'bg-gray-400' };
function dotClass(dot) { return DOT_CLASS[dot] || 'bg-gray-400'; }
</script>
