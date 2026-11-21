<!-- Previous · Page n of N · Next at the foot of a Watch Tower list (owner 2026-11-21). Hidden when one page holds it all. -->
<template>
	<div v-if="pages > 1" class="wt-pager">
		<button type="button" class="wt-btn" :disabled="page === 0 || busy" @click="$emit('go', page - 1)">Previous</button>
		<span>Page {{ page + 1 }} of {{ pages }}</span>
		<button type="button" class="wt-btn" :disabled="page >= pages - 1 || busy" @click="$emit('go', page + 1)">Next</button>
	</div>
</template>

<script setup>
import { computed } from 'vue';
import { PAGE_ROWS } from './paging';

const props = defineProps({
	page: { type: Number, required: true },
	total: { type: Number, required: true },
	busy: { type: Boolean, default: false },
	size: { type: Number, default: PAGE_ROWS }, // rows a page: 6 beside a chart, 20 on the Apps pages
});
defineEmits(['go']);
const pages = computed(() => Math.max(1, Math.ceil(props.total / props.size)));
</script>

<style scoped src="./watch-tower.css"></style>
<style scoped>
.wt-pager {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
	padding: 8px 16px;
	border-top: 1px solid #e9eaec;
	font-size: 12.5px;
	color: #525a64;
	font-variant-numeric: tabular-nums;
}
.wt-btn {
	padding: 4px 10px;
	font-size: 12.5px;
}
.wt-btn:disabled {
	opacity: 0.45;
	cursor: not-allowed;
	background: #fff;
}
</style>
