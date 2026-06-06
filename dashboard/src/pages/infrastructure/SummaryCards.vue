<template>
  <div class="flex flex-wrap gap-3">
    <div v-for="c in cards" :key="c.label" class="min-w-[120px] rounded-lg border px-4 py-3">
      <div class="text-2xl font-semibold tabular-nums" :class="c.bad && c.value ? 'text-red-600' : 'text-gray-900'">{{ c.value }}</div>
      <div class="mt-0.5 text-xs text-gray-500">{{ c.label }}</div>
    </div>
  </div>
</template>
<script setup>
defineProps({ cards: { type: Array, default: () => [] } }); // [{ label, value, bad }]
</script>
