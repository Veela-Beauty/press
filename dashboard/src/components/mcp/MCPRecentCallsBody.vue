<template>
	<div>
		<div class="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-3">
			<div class="flex items-baseline gap-3">
				<div class="text-xs text-gray-500">
					<span v-if="totalCalls">{{ pageStart }}–{{ pageEnd }} of {{ totalCalls }}</span>
					<span v-else>—</span>
				</div>
			</div>
			<div class="flex items-center gap-2">
				<select
					v-model.number="pageSize"
					class="rounded border border-gray-300 bg-white px-2 py-1 text-xs"
					@change="onPageSizeChange"
				>
					<option v-for="s in [10, 25, 50, 100]" :key="s" :value="s">{{ s }}/page</option>
				</select>
				<Button size="sm" @click="loadCalls(false)">Refresh</Button>
			</div>
		</div>
		<div class="overflow-x-auto">
			<table class="w-full text-left text-sm">
				<thead class="bg-gray-50 text-xs uppercase text-gray-600">
					<tr>
						<th class="p-3">Time</th>
						<th class="p-3">Tool</th>
						<th class="p-3">Status</th>
						<th class="p-3">Duration</th>
						<th class="p-3">Error</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="c in calls" :key="c.name" class="border-t border-gray-100">
						<td class="p-3 text-xs text-gray-600">{{ formatDate(c.creation) }}</td>
						<td class="p-3" :title="c.tool">
							<div class="font-medium">{{ toolLabel(c.tool) }}</div>
							<div v-if="toolLabel(c.tool) !== c.tool" class="font-mono text-[10px] text-gray-400 leading-tight">
								{{ c.tool }}
							</div>
						</td>
						<td class="p-3">
							<span :class="callStatusClass(c.status)">{{ c.status }}</span>
						</td>
						<td class="p-3 text-xs text-gray-600">{{ c.duration_ms }}ms</td>
						<td class="p-3 text-xs text-red-700">{{ c.error_message || '' }}</td>
					</tr>
					<tr v-if="!calls.length">
						<td colspan="5" class="p-6 text-center text-sm text-gray-500">No MCP calls yet.</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-if="totalCalls > pageSize" class="flex items-center justify-between gap-2 border-t border-gray-200 p-3">
			<div class="text-xs text-gray-500">Page {{ currentPage }} of {{ totalPages }}</div>
			<div class="flex gap-1">
				<Button size="sm" :disabled="currentPage === 1" @click="goToPage(1)">First</Button>
				<Button size="sm" :disabled="currentPage === 1" @click="goToPage(currentPage - 1)">Prev</Button>
				<Button size="sm" :disabled="currentPage === totalPages" @click="goToPage(currentPage + 1)">Next</Button>
				<Button size="sm" :disabled="currentPage === totalPages" @click="goToPage(totalPages)">Last</Button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { Button, call, toast } from 'frappe-ui';
import { toolLabel } from './_tool_catalog.js';

const calls = ref([]);
const totalCalls = ref(0);
const currentPage = ref(1);
const pageSize = ref(25);
const latestCallTs = ref(null);
let pollHandle = null;

const totalPages = computed(() => Math.max(1, Math.ceil(totalCalls.value / pageSize.value)));
const pageStart = computed(() => (totalCalls.value === 0 ? 0 : (currentPage.value - 1) * pageSize.value + 1));
const pageEnd = computed(() => Math.min(currentPage.value * pageSize.value, totalCalls.value));

async function loadCalls(incremental = false) {
	try {
		const args = {
			limit: pageSize.value,
			offset: (currentPage.value - 1) * pageSize.value,
		};
		if (incremental && currentPage.value === 1 && latestCallTs.value) {
			args.since_iso = latestCallTs.value;
		}
		const result = await call('press.mcp_server.dashboard.list_my_calls', args);
		const rows = result?.rows || [];
		const isPolling = !!args.since_iso;
		if (!isPolling) {
			calls.value = rows;
		} else if (rows.length) {
			calls.value = [...rows, ...calls.value].slice(0, pageSize.value);
			totalCalls.value += rows.length;
		}
		if (typeof result?.total === 'number' && !isPolling) {
			totalCalls.value = result.total;
		}
		if (result?.latest) {
			latestCallTs.value = result.latest;
		}
	} catch (e) {
		toast.error('Failed to load calls: ' + (e?.message || e));
	}
}

function pollCalls() {
	loadCalls(true);
}

function goToPage(p) {
	const target = Math.max(1, Math.min(totalPages.value, p));
	if (target === currentPage.value) return;
	currentPage.value = target;
	loadCalls(false);
}

function onPageSizeChange() {
	currentPage.value = 1;
	loadCalls(false);
}

function formatDate(d) {
	if (!d) return '';
	try { return new Date(d).toLocaleString(); } catch { return d; }
}

function callStatusClass(s) {
	if (s === 'Success') return 'inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800';
	if (s === 'PermissionError') return 'inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-800';
	if (s === 'ValidationError') return 'inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800';
	return 'inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700';
}

onMounted(() => {
	loadCalls(false);
	pollHandle = setInterval(pollCalls, 10000);
});

onUnmounted(() => {
	if (pollHandle) clearInterval(pollHandle);
});
</script>
