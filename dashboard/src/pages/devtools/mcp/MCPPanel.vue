<template>
	<div class="mx-auto max-w-6xl space-y-6 p-6">
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-2xl font-semibold">MCP Tokens & Activity</h1>
				<p class="text-sm text-gray-600">Manage MCP access tokens for AI agents and view recent calls.</p>
			</div>
			<Button variant="solid" @click="showIssueDialog = true">
				<template #prefix><FeatherIcon name="plus" class="h-4 w-4" /></template>
				Issue Token
			</Button>
		</div>

		<section class="rounded border border-gray-200 bg-white">
			<div class="border-b border-gray-200 p-4 text-base font-semibold">Active Tokens</div>
			<div class="overflow-x-auto">
				<table class="w-full text-left text-sm">
					<thead class="bg-gray-50 text-xs uppercase text-gray-600">
						<tr>
							<th class="p-3">Label</th>
							<th class="p-3">Scope</th>
							<th class="p-3">Resources</th>
							<th class="p-3">Issued</th>
							<th class="p-3">Expires</th>
							<th class="p-3">Last Used</th>
							<th class="p-3">Status</th>
							<th class="p-3"></th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="t in tokens" :key="t.name" class="border-t border-gray-100">
							<td class="p-3 font-medium">{{ t.label }}</td>
							<td class="p-3 text-xs text-gray-600" :title="(t.scope || []).join(', ') || 'all'">
								{{ formatScope(t.scope) }}
							</td>
							<td class="p-3 text-xs text-gray-600">
								<div v-if="t.allowed_release_groups?.length || t.allowed_sites?.length">
									<div v-if="t.allowed_release_groups?.length">
										<span class="font-medium">RGs:</span> {{ t.allowed_release_groups.join(', ') }}
									</div>
									<div v-if="t.allowed_sites?.length">
										<span class="font-medium">Sites:</span> {{ t.allowed_sites.join(', ') }}
									</div>
								</div>
								<span v-else class="text-gray-400">all (inherits user)</span>
							</td>
							<td class="p-3 text-xs text-gray-600">{{ formatDate(t.creation) }}</td>
							<td class="p-3 text-xs text-gray-600">{{ formatDate(t.expires_at) }}</td>
							<td class="p-3 text-xs text-gray-600">{{ formatDate(t.last_used_at) || '—' }}</td>
							<td class="p-3">
								<span :class="statusClass(t.status)">{{ t.status }}</span>
							</td>
							<td class="p-3">
								<Button v-if="t.status === 'active'" size="sm" @click="onRevoke(t)">Revoke</Button>
							</td>
						</tr>
						<tr v-if="!tokens.length">
							<td colspan="8" class="p-6 text-center text-sm text-gray-500">No tokens yet.</td>
						</tr>
					</tbody>
				</table>
			</div>
		</section>

		<section class="rounded border border-gray-200 bg-white">
			<div class="flex items-center justify-between border-b border-gray-200 p-4">
				<div class="flex items-baseline gap-3">
					<div class="text-base font-semibold">Recent Calls</div>
					<div class="text-xs text-gray-500">
						<span v-if="totalCalls">
							{{ pageStart }}–{{ pageEnd }} of {{ totalCalls }}
						</span>
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
		</section>

		<IssueTokenDialog v-model="showIssueDialog" @issued="loadTokens" />
	</div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { Button, FeatherIcon, call, toast } from 'frappe-ui';
import IssueTokenDialog from '../../../components/mcp/IssueTokenDialog.vue';
import { formatScope, toolLabel } from '../../../components/mcp/_tool_catalog.js';

const tokens = ref([]);
const calls = ref([]);
const totalCalls = ref(0);
const currentPage = ref(1);
const pageSize = ref(25);
const latestCallTs = ref(null);
const showIssueDialog = ref(false);
let pollHandle = null;

const totalPages = computed(() => Math.max(1, Math.ceil(totalCalls.value / pageSize.value)));
const pageStart = computed(() => totalCalls.value === 0 ? 0 : (currentPage.value - 1) * pageSize.value + 1);
const pageEnd = computed(() => Math.min(currentPage.value * pageSize.value, totalCalls.value));

async function loadTokens() {
	try {
		tokens.value = await call('press.mcp_server.dashboard.list_my_tokens');
	} catch (e) {
		toast.error('Failed to load tokens: ' + (e?.message || e));
	}
}

async function loadCalls(incremental = false) {
	try {
		const args = {
			limit: pageSize.value,
			offset: (currentPage.value - 1) * pageSize.value,
		};
		// Incremental polling only on page 1 (newest rows show there)
		if (incremental && currentPage.value === 1 && latestCallTs.value) {
			args.since_iso = latestCallTs.value;
		}
		const result = await call('press.mcp_server.dashboard.list_my_calls', args);
		const rows = result?.rows || [];
		const isPolling = !!args.since_iso;
		if (!isPolling) {
			calls.value = rows;
		} else if (rows.length) {
			// Prepend new rows; trim to pageSize so the page stays bounded
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

async function onRevoke(token) {
	try {
		await call('press.mcp_server.auth.revoke_token', { token_id: token.name });
		toast.success(`Revoked: ${token.label}`);
		await loadTokens();
	} catch (e) {
		toast.error('Revoke failed: ' + (e?.message || e));
	}
}

function formatDate(d) {
	if (!d) return '';
	try { return new Date(d).toLocaleString(); } catch { return d; }
}

function statusClass(s) {
	if (s === 'active') return 'inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800';
	if (s === 'expired') return 'inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700';
	return 'inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-800';
}

function callStatusClass(s) {
	if (s === 'Success') return 'inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800';
	if (s === 'PermissionError') return 'inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-800';
	if (s === 'ValidationError') return 'inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800';
	return 'inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700';
}

onMounted(() => {
	loadTokens();
	loadCalls(false);
	pollHandle = setInterval(pollCalls, 10000);
});

onUnmounted(() => {
	if (pollHandle) clearInterval(pollHandle);
});
</script>
