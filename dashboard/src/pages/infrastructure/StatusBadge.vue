<template>
  <Badge :label="label" :theme="theme" />
</template>
<script setup>
import { computed } from 'vue';
import { Badge } from 'frappe-ui';
import { stateLabel, stateTheme } from './infra-derive';
const props = defineProps({ state: { type: String, required: true } });
const label = computed(() => stateLabel(props.state));
const theme = computed(() => stateTheme(props.state));
</script>
