<template>
	<div :class="STAT_CARD_BASE">
		<div :class="STAT_LABEL">{{ label }}</div>
		<div :class="numberClass">
			<slot name="number">{{ number }}</slot>
		</div>
		<div v-if="$slots.sub || subline" :class="STAT_SUBLINE">
			<slot name="sub">{{ subline }}</slot>
		</div>
	</div>
</template>

<script setup>
import { computed } from 'vue';
import {
	STAT_CARD_BASE,
	STAT_LABEL,
	STAT_SUBLINE,
	statNumberClass,
} from './statCardClasses.js';

const props = defineProps({
	// Small UPPERCASE label above the number (e.g. "TEAMS").
	label: { type: String, required: true },
	// The metric value. Use slot="number" if you need to format it (e.g. €890).
	number: { type: [String, Number], default: '' },
	// Optional sub-line beneath the number. Pass a string OR use slot="sub".
	subline: { type: String, default: '' },
	// Color of the NUMBER (not the card). Valid: default / good / warn / bad / info / muted.
	color: {
		type: String,
		default: 'default',
		validator: (v) => ['default', 'good', 'warn', 'bad', 'info', 'muted'].includes(v),
	},
});

const numberClass = computed(() => statNumberClass(props.color));
</script>
