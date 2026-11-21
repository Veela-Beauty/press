<!-- Horizontal bars for a ranked list (prototype ACM-SP-03). `long`: the label sits on its own line (error titles). -->
<template>
	<div class="flex flex-col gap-2.5 px-4 py-3">
		<div v-if="!rows.length" class="py-6 text-center text-base text-gray-600">{{ empty }}</div>
		<div v-for="([label, n], i) in rows" :key="`${i}-${label}`" :class="long ? 'rl' : 'r'">
			<span class="lab" :title="label">{{ label }}</span>
			<div class="line">
				<span class="track"><span class="fill" :style="{ width: `${(100 * n) / max}%`, background: color }" /></span>
				<b>{{ n }}</b>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
	rows: { type: Array, required: true }, // [[label, count]]
	color: { type: String, required: true },
	long: { type: Boolean, default: false },
	empty: { type: String, default: 'Nothing here' },
});
const max = computed(() => Math.max(1, ...props.rows.map((r) => r[1])));
</script>

<style scoped>
.r {
	display: grid;
	grid-template-columns: 150px 1fr;
	align-items: center;
	gap: 10px;
	font-size: 13px;
}
.rl .lab {
	display: block;
	margin-bottom: 4px;
}
.lab {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	color: #525a64;
	font-size: 13px;
}
.line {
	display: grid;
	grid-template-columns: 1fr 32px;
	gap: 10px;
	align-items: center;
}
.track {
	height: 10px;
	background: #f0f1f2;
	border-radius: 3px;
	overflow: hidden;
	display: block;
}
.fill {
	display: block;
	height: 100%;
	border-radius: 3px;
}
b {
	text-align: right;
	font-variant-numeric: tabular-nums;
	font-weight: 600;
}
</style>
