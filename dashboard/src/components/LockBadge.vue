<template>
	<div v-if="lockInfo && lockInfo.status !== 'free'" class="inline-flex items-center gap-1">
		<FeatherIcon
			:name="iconName"
			class="h-3 w-3"
			:class="iconColor"
		/>
		<span class="text-xs" :class="textColor">{{ label }}</span>
	</div>
</template>

<script setup>
import { computed } from 'vue';
import { FeatherIcon } from 'frappe-ui';

const props = defineProps({
	lockInfo: { type: Object, default: null },
});

const iconName = computed(() => {
	if (!props.lockInfo) return 'unlock';
	return props.lockInfo.status === 'blocked_by_parent' ? 'shield' : 'lock';
});

const iconColor = computed(() => {
	return props.lockInfo?.status === 'blocked_by_parent'
		? 'text-orange-600'
		: 'text-amber-600';
});

const textColor = computed(() => iconColor.value);

const label = computed(() => {
	if (!props.lockInfo) return '';
	if (props.lockInfo.status === 'blocked_by_parent') {
		return `Bench locked: ${props.lockInfo.parent_lock?.holder || 'unknown'}`;
	}
	return `Locked: ${props.lockInfo.holder} (${props.lockInfo.reason || 'no reason'})`;
});
</script>
