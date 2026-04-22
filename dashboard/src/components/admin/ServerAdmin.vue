<template>
	<div>
		<!-- Header -->
		<div class="mb-3 flex items-center justify-between">
			<div>
				<p class="text-sm font-semibold text-gray-700">Server Administration</p>
				<p class="text-xs text-gray-400">Edit cost overrides, admin notes, and decommission status. Decommissioned servers are excluded from cost rollups.</p>
			</div>
			<Button variant="subtle" size="sm" :loading="loading" @click="loadServers">
				<template #prefix><i class="fa fa-refresh"></i></template>
				Refresh
			</Button>
		</div>

		<!-- Summary cards -->
		<div class="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
			<div class="rounded-lg border border-gray-100 bg-gray-50 p-3">
				<p class="text-xs text-gray-500">Total Servers</p>
				<p class="text-lg font-bold">{{ servers.length }}</p>
			</div>
			<div class="rounded-lg border border-gray-100 bg-gray-50 p-3">
				<p class="text-xs text-gray-500">Active</p>
				<p class="text-lg font-bold">{{ activeCount }}</p>
			</div>
			<div class="rounded-lg border border-gray-100 bg-gray-50 p-3">
				<p class="text-xs text-gray-500">Decommissioned</p>
				<p class="text-lg font-bold text-orange-500">{{ decommissionedCount }}</p>
			</div>
			<div class="rounded-lg border border-gray-100 bg-gray-50 p-3">
				<p class="text-xs text-gray-500">Effective Cost / mo</p>
				<p class="text-lg font-bold">€{{ totalEffectiveCost }}</p>
			</div>
		</div>

		<!-- Table -->
		<div v-if="loading" class="py-8 text-center text-sm text-gray-400">Loading servers...</div>
		<div v-else-if="!servers.length" class="rounded-lg border border-gray-100 bg-white p-8 text-center text-sm text-gray-400">
			No servers found.
		</div>
		<div v-else class="overflow-x-auto rounded-lg border border-gray-100 bg-white">
			<table class="w-full text-sm">
				<thead class="border-b bg-gray-50 text-xs uppercase text-gray-500">
					<tr>
						<th class="px-3 py-2 text-left">Server</th>
						<th class="px-3 py-2 text-left">Kind</th>
						<th class="px-3 py-2 text-left">IP</th>
						<th class="px-3 py-2 text-left">Plan</th>
						<th class="px-3 py-2 text-right">Sites</th>
						<th class="px-3 py-2 text-right">Benches</th>
						<th class="px-3 py-2 text-right">RAM</th>
						<th class="px-3 py-2 text-right">CPU Load</th>
						<th class="px-3 py-2 text-right">Disk</th>
						<th class="px-3 py-2 text-right">Cost / mo</th>
						<th class="px-3 py-2 text-left">Notes</th>
						<th class="px-3 py-2 text-right">Actions</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="s in servers" :key="s.name" class="border-b border-gray-50"
						:class="s.is_decommissioned ? 'bg-orange-50/50 text-gray-400' : ''">
						<td class="px-3 py-2 font-medium">
							{{ s.name }}
							<span v-if="s.is_decommissioned" class="ml-1 rounded bg-orange-100 px-1.5 py-0.5 text-xs text-orange-700">DECOM</span>
						</td>
						<td class="px-3 py-2">
							<Badge :label="s.kind" :theme="{ app: 'blue', db: 'purple', proxy: 'green' }[s.kind] || 'gray'" />
						</td>
						<td class="px-3 py-2 font-mono text-xs">{{ s.ip || '—' }}</td>
						<td class="px-3 py-2">{{ s.plan || '—' }}</td>
						<td class="px-3 py-2 text-right">{{ s.sites }}</td>
						<td class="px-3 py-2 text-right">{{ s.benches }}</td>
						<td class="px-3 py-2 text-right">
							<template v-if="s.kind !== 'app'"><span class="text-gray-300">—</span></template>
							<template v-else-if="!stats[s.name]"><span class="text-gray-300">…</span></template>
							<template v-else-if="stats[s.name].error"><span class="text-xs text-red-400" :title="stats[s.name].error">err</span></template>
							<template v-else>
								<span :class="pctClass(stats[s.name].ram_pct)">{{ stats[s.name].ram_pct }}%</span>
								<span class="block text-xs text-gray-400">{{ mb2gb(stats[s.name].ram_used_mb) }}/{{ mb2gb(stats[s.name].ram_total_mb) }}G</span>
							</template>
						</td>
						<td class="px-3 py-2 text-right">
							<template v-if="s.kind !== 'app'"><span class="text-gray-300">—</span></template>
							<template v-else-if="!stats[s.name]"><span class="text-gray-300">…</span></template>
							<template v-else-if="stats[s.name].error"><span class="text-xs text-red-400">err</span></template>
							<template v-else>
								<span :class="pctClass(stats[s.name].load_pct)">{{ stats[s.name].load_pct }}%</span>
								<span class="block text-xs text-gray-400">{{ stats[s.name].load1 }} / {{ stats[s.name].cpus }}c</span>
							</template>
						</td>
						<td class="px-3 py-2 text-right">
							<template v-if="s.kind !== 'app'"><span class="text-gray-300">—</span></template>
							<template v-else-if="!stats[s.name]"><span class="text-gray-300">…</span></template>
							<template v-else-if="stats[s.name].error"><span class="text-xs text-red-400">err</span></template>
							<template v-else>
								<span :class="pctClass(stats[s.name].disk_pct)">{{ stats[s.name].disk_pct }}%</span>
								<span class="block text-xs text-gray-400">{{ stats[s.name].disk_used_gb }}/{{ stats[s.name].disk_size_gb }}G</span>
							</template>
						</td>
						<td class="px-3 py-2 text-right">
							<span :class="s.is_decommissioned ? 'line-through' : ''">€{{ s.effective_cost }}</span>
							<span v-if="s.monthly_cost_override > 0" class="ml-1 text-xs text-blue-500" title="Override active">★</span>
						</td>
						<td class="px-3 py-2 text-xs text-gray-500 max-w-[200px] truncate" :title="s.admin_notes">{{ s.admin_notes || '—' }}</td>
						<td class="px-3 py-2 text-right">
							<div class="flex justify-end gap-2">
								<Button size="sm" variant="subtle" @click="openEdit(s)" :disabled="s.kind !== 'app'">Edit</Button>
								<Button v-if="!s.is_decommissioned" size="sm" variant="subtle" theme="orange"
									@click="confirmDecommission(s, true)" :disabled="s.kind !== 'app'">Decommission</Button>
								<Button v-else size="sm" variant="subtle" theme="green"
									@click="confirmDecommission(s, false)">Reactivate</Button>
							</div>
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<!-- Edit Dialog -->
		<Dialog v-model="showEdit" :options="{ title: `Edit Server — ${editing?.name || ''}`, size: 'lg' }">
			<template #body-content>
				<div v-if="editing" class="space-y-4">
					<div>
						<label class="mb-1 block text-xs font-semibold uppercase text-gray-500">Monthly Cost Override (€)</label>
						<input type="number" v-model.number="editForm.monthly_cost_override" min="0" step="0.01"
							class="w-full rounded border border-gray-200 px-3 py-2 text-sm" />
						<p class="mt-1 text-xs text-gray-400">
							Baseline: €{{ editing.baseline_cost }}. Set 0 to use baseline.
						</p>
					</div>
					<div>
						<label class="mb-1 block text-xs font-semibold uppercase text-gray-500">Admin Notes</label>
						<textarea v-model="editForm.admin_notes" rows="3" placeholder="Contract end date, vendor ticket, ops context..."
							class="w-full rounded border border-gray-200 px-3 py-2 text-sm"></textarea>
					</div>
				</div>
			</template>
			<template #actions>
				<Button variant="subtle" @click="showEdit = false">Cancel</Button>
				<Button variant="solid" :loading="saving" @click="saveEdit">Save</Button>
			</template>
		</Dialog>

		<!-- Decommission confirm dialog -->
		<Dialog v-model="showDecom" :options="{ title: decomTarget?.is_decommissioned ? 'Reactivate Server' : 'Decommission Server' }">
			<template #body-content>
				<div v-if="decomTarget" class="space-y-2 text-sm">
					<p v-if="decomNewState">
						Mark <strong>{{ decomTarget.name }}</strong> as decommissioned.
					</p>
					<p v-else>
						Reactivate <strong>{{ decomTarget.name }}</strong>.
					</p>
					<ul class="list-disc pl-5 text-xs text-gray-500">
						<li v-if="decomNewState">Excluded from cost rollups on the Teams tab.</li>
						<li v-if="decomNewState">Visually muted (orange) in this list.</li>
						<li v-if="decomNewState && decomTarget.sites > 0" class="text-orange-600">⚠ Server still has {{ decomTarget.sites }} active sites — they continue to run, but cost attribution stops.</li>
						<li>This is a soft flag. No infrastructure changes are made — agent stays running.</li>
					</ul>
				</div>
			</template>
			<template #actions>
				<Button variant="subtle" @click="showDecom = false">Cancel</Button>
				<Button variant="solid" :theme="decomNewState ? 'orange' : 'green'" :loading="saving" @click="confirmDecomNow">
					{{ decomNewState ? 'Decommission' : 'Reactivate' }}
				</Button>
			</template>
		</Dialog>
	</div>
</template>

<script>
import { call } from 'frappe-ui';
import { toast } from 'vue-sonner';

const API = 'press.api.admin_panel';

export default {
	name: 'ServerAdmin',
	emits: ['updated'],
	data() {
		return {
			servers: [],
			stats: {}, // server.name → { ram_pct, load_pct, disk_pct, ... } | { error }
			loading: false,
			saving: false,
			showEdit: false,
			editing: null,
			editForm: { monthly_cost_override: 0, admin_notes: '' },
			showDecom: false,
			decomTarget: null,
			decomNewState: true,
		};
	},
	computed: {
		activeCount() { return this.servers.filter(s => !s.is_decommissioned).length; },
		decommissionedCount() { return this.servers.filter(s => s.is_decommissioned).length; },
		totalEffectiveCost() {
			return this.servers
				.filter(s => !s.is_decommissioned)
				.reduce((sum, s) => sum + (s.effective_cost || 0), 0)
				.toFixed(2);
		},
	},
	mounted() { this.loadServers(); },
	methods: {
		pctClass(pct) {
			if (pct == null) return 'text-gray-400';
			if (pct >= 85) return 'font-semibold text-red-600';
			if (pct >= 70) return 'font-semibold text-orange-500';
			return 'text-green-600';
		},
		mb2gb(mb) {
			if (!mb) return 0;
			return (mb / 1024).toFixed(1);
		},
		async loadServers() {
			this.loading = true;
			try {
				this.servers = await call(`${API}.get_servers_admin`);
				this.loadAllStats();
			} catch (e) {
				toast.error('Failed to load servers');
				this.servers = [];
			}
			this.loading = false;
		},
		async loadAllStats() {
			// Lazy-load stats per app server in parallel. Don't block the table.
			const appServers = this.servers.filter(s => s.kind === 'app' && !s.is_decommissioned);
			await Promise.all(appServers.map(s => this.loadOneStats(s.name)));
		},
		async loadOneStats(name) {
			try {
				this.stats[name] = await call(`${API}.get_server_stats`, { server: name });
			} catch (e) {
				this.stats[name] = { error: 'fetch_failed' };
			}
		},
		openEdit(s) {
			this.editing = s;
			this.editForm.monthly_cost_override = s.monthly_cost_override || 0;
			this.editForm.admin_notes = s.admin_notes || '';
			this.showEdit = true;
		},
		async saveEdit() {
			if (!this.editing) return;
			this.saving = true;
			try {
				await call(`${API}.update_server_admin`, {
					server: this.editing.name,
					monthly_cost_override: this.editForm.monthly_cost_override,
					admin_notes: this.editForm.admin_notes,
				});
				toast.success(`Updated ${this.editing.name}`);
				this.showEdit = false;
				await this.loadServers();
				this.$emit('updated');
			} catch (e) {
				toast.error('Failed to save');
			}
			this.saving = false;
		},
		confirmDecommission(s, newState) {
			this.decomTarget = s;
			this.decomNewState = newState;
			this.showDecom = true;
		},
		async confirmDecomNow() {
			if (!this.decomTarget) return;
			this.saving = true;
			try {
				await call(`${API}.set_server_decommissioned`, {
					server: this.decomTarget.name,
					decommissioned: this.decomNewState ? 1 : 0,
				});
				toast.success(this.decomNewState ? `Decommissioned ${this.decomTarget.name}` : `Reactivated ${this.decomTarget.name}`);
				this.showDecom = false;
				await this.loadServers();
				this.$emit('updated');
			} catch (e) {
				toast.error('Failed to update');
			}
			this.saving = false;
		},
	},
};
</script>
