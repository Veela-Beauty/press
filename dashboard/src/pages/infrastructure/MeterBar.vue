<template>
  <div class="flex items-center gap-1.5">
    <span class="w-7 text-right font-mono text-xs tabular-nums text-gray-700">{{ value }}%</span>
    <div class="h-1 w-12 overflow-hidden rounded-full bg-gray-100">
      <div class="h-full rounded-full" :class="barClass" :style="{ width: Math.min(100, value) + '%' }" />
    </div>
  </div>
</template>
<script setup>
import { computed } from 'vue';
const props = defineProps({ value: { type: Number, default: 0 } });
const barClass = computed(() => (props.value >= 90 ? 'bg-red-500' : props.value >= 75 ? 'bg-amber-500' : 'bg-gray-400'));
</script>
