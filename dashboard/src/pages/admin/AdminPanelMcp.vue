<template>
	<div class="mx-auto max-w-7xl space-y-6 p-6">
		<div>
			<h1 class="text-2xl font-semibold">MCP Tokens (Global)</h1>
			<p class="text-sm text-gray-600">System Admin view of all MCP tokens across all teams.</p>
		</div>

		<div class="flex flex-wrap items-end gap-3 rounded border border-gray-200 bg-white p-4">
			<FormControl
				label="Team"
				v-model="filters.team"
				class="min-w-[180px]"
			/>
			<FormControl
				label="User"
				v-model="filters.user"
				class="min-w-[200px]"
			/>
			<FormControl
				label="Status"
				type="select"
				:options="[
					{ label: 'Any', value: '' },
					{ label: 'Active', value: 'active' },
					{ label: 'Expired', value: 'expired' },
					{ label: 'Revoked', value: 'revoked' },
				]"
				v-model="filters.status"
				class="min-w-[140px]"
			/>
			<FormControl
				label="Label contains"
				v-model="filters.label_substring"
				class="min-w-[200px]"
			/>
			<Button @click="loadTokens">Apply</Button>
			<Button variant="solid" :disabled="!selected.length" @click="onBulkRevoke">
				Revoke selected ({{ selected.length }})
			</Button>
		</div>

		<section class="rounded border border-gray-200 bg-white">
			<div class="overflow-x-auto">
				<table class="w-full text-left text-sm">
					<thead class="bg-gray-50 text-xs uppercase text-gray-600">
						<tr>
							<th class="p-3">
								<input type="checkbox" :checked="allSelected" @change="toggleAll" />
							</th>
							<th class="p-3">Label</th>
							<th class="p-3">User</th>
							<th class="p-3">Team</th>
							<th class="p-3">Scope</th>
							<th class="p-3">Resources</th>
							<th class="p-3">Issued</th>
							<th class="p-3">Expires</th>
							<th class="p-3">Last Used</th>
							<th class="p-3">Status</th>
							<th class="p-3">Risky</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="t in tokens" :key="t.name" class="border-t border-gray-100">
							<td class="p-3">
								<input
									type="checkbox"
									:value="t.name"
									v-model="selected"
									:disabled="t.status !== 'active'"
								/>
							</td>
							<td class="p-3 font-medium">{{ t.label }}</td>
							<td class="p-3 text-xs">{{ t.user }}</td>
							<td class="p-3 text-xs">{{ t.team || '—' }}</td>
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
							<td class="p-3 text-xs">
								<span v-if="t.risky_tools_enabled && t.approval_status === 'approved'" class="rounded bg-purple-100 px-2 py-0.5 text-purple-800">risky / approved</span>
								<span v-else-if="t.approval_status === 'pending'" class="rounded bg-amber-100 px-2 py-0.5 text-amber-800">pending</span>
								<span v-else class="text-gray-400">—</span>
								<div v-if="t.approval_status === 'pending'" class="mt-1 flex gap-1">
									<Button size="sm" @click="onApprove(t)">Approve</Button>
									<Button size="sm" theme="red" @click="onReject(t)">Reject</Button>
								</div>
							</td>
						</tr>
						<tr v-if="!tokens.length">
							<td colspan="11" class="p-6 text-center text-sm text-gray-500">No tokens match.</td>
						</tr>
					</tbody>
				</table>
			</div>
		</section>
	</div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { Button, FormControl, call, toast, confirmDialog } from 'frappe-ui';
import { formatScope } from '../../components/mcp/_tool_catalog.js';

const tokens = ref([]);
const selected = ref([]);
const filters = reactive({
	team: '',
	user: '',
	status: '',
	label_substring: '',
});

const allSelected = computed(() => {
	const active = tokens.value.filter((t) => t.status === 'active');
	return active.length > 0 && active.every((t) => selected.value.includes(t.name));
});

function toggleAll() {
	const active = tokens.value.filter((t) => t.status === 'active').map((t) => t.name);
	selected.value = allSelected.value ? [] : active;
}

async function loadTokens() {
	try {
		const cleaned = Object.fromEntries(
			Object.entries(filters).filter(([, v]) => v),
		);
		tokens.value = await call('press.mcp_server.admin.list_all_tokens', {
			filters: cleaned,
		});
	} catch (e) {
		toast.error('Load failed: ' + (e?.messages?.[0] || e?.message || e));
	}
}

function onBulkRevoke() {
	if (!selected.value.length) return;
	confirmDialog({
		title: `Revoke ${selected.value.length} tokens?`,
		message: 'This action is logged. Provide a reason.',
		fields: [{ label: 'Reason', fieldname: 'reason' }],
		primaryAction: { label: 'Revoke', variant: 'solid' },
		onSuccess({ hide, values }) {
			if (!values.reason) {
				toast.error('Reason is required');
				return;
			}
			toast.promise(
				call('press.mcp_server.admin.bulk_revoke', {
					token_names: selected.value,
					reason: values.reason,
				}).then((r) => {
					hide();
					selected.value = [];
					loadTokens();
					return r;
				}),
				{
					loading: 'Revoking...',
					success: (r) => `Revoked ${r.count} tokens`,
					error: (e) => `Revoke failed: ${e?.messages?.[0] || e?.message || e}`,
				},
			);
		},
	});
}

async function onApprove(token) {
	try {
		await call('press.mcp_server.admin.approve_risky_token', { token_name: token.name });
		toast.success('Token approved');
		await loadTokens();
	} catch (e) {
		toast.error('Approve failed: ' + (e?.messages?.[0] || e?.message || e));
	}
}

function onReject(token) {
	confirmDialog({
		title: 'Reject risky token?',
		message: 'This will revoke the token immediately.',
		fields: [{ label: 'Reason', fieldname: 'reason' }],
		primaryAction: { label: 'Reject', variant: 'solid', theme: 'red' },
		onSuccess({ hide, values }) {
			if (!values.reason) {
				toast.error('Reason is required');
				return;
			}
			toast.promise(
				call('press.mcp_server.admin.reject_risky_token', {
					token_name: token.name,
					reason: values.reason,
				}).then(() => {
					hide();
					loadTokens();
				}),
				{ loading: 'Rejecting...', success: 'Token rejected', error: (e) => 'Reject failed: ' + (e?.messages?.[0] || e?.message || e) },
			);
		},
	});
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

onMounted(loadTokens);
</script>
