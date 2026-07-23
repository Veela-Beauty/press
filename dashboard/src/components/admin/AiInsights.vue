<template>
	<div class="space-y-4">
		<!-- KPI row -->
		<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Requests</p>
				<p class="mt-1 text-2xl font-bold">{{ fmtNum(summary.total_requests) }}</p>
				<p class="text-xs text-gray-400">{{ fmtNum(summary.total_tools) }} tool calls</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Cost</p>
				<p class="mt-1 text-2xl font-bold">${{ Number(summary.total_cost || 0).toFixed(2) }}</p>
				<p class="text-xs text-gray-400">gateway spend, {{ periodLabel }}</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Active users</p>
				<p class="mt-1 text-2xl font-bold">{{ fmtNum(summary.active_users) }}</p>
				<p class="text-xs text-gray-400">used the AI, {{ periodLabel }}</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Avg latency</p>
				<p class="mt-1 text-2xl font-bold">{{ fmtNum(summary.avg_latency_ms) }}<span class="text-sm font-normal text-gray-400"> ms</span></p>
				<p class="text-xs text-gray-400">request-weighted</p>
			</div>
		</div>

		<div class="flex items-center justify-between">
			<h3 class="text-sm font-semibold">What the AI is doing</h3>
			<select v-model="period" class="rounded border border-gray-200 px-2 py-1 text-xs">
				<option value="week">Last 7 days</option>
				<option value="month">Last 30 days</option>
			</select>
		</div>

		<!-- Top tools + doctypes -->
		<div class="grid gap-3 lg:grid-cols-2">
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<h4 class="mb-3 text-xs font-semibold uppercase text-gray-500">Tool calls</h4>
				<div v-if="!topTools.length" class="py-6 text-center text-xs text-gray-400">No tool activity yet.</div>
				<div v-for="t in topTools" :key="t.name" class="mb-2">
					<div class="flex items-center justify-between text-xs">
						<span class="font-mono text-gray-700">{{ t.name }}</span>
						<span class="text-gray-500">{{ fmtNum(t.count) }}</span>
					</div>
					<div class="mt-1 h-1.5 rounded-full bg-gray-100">
						<div class="h-full rounded-full bg-gray-800" :style="{ width: bar(t.count, topTools) + '%' }"></div>
					</div>
				</div>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<h4 class="mb-3 text-xs font-semibold uppercase text-gray-500">DocTypes used</h4>
				<div v-if="!topDoctypes.length" class="py-6 text-center text-xs text-gray-400">No DocType activity yet.</div>
				<div v-for="d in topDoctypes" :key="d.name" class="mb-2">
					<div class="flex items-center justify-between text-xs">
						<span class="text-gray-700">{{ d.name }}</span>
						<span class="text-gray-500">{{ fmtNum(d.count) }}</span>
					</div>
					<div class="mt-1 h-1.5 rounded-full bg-gray-100">
						<div class="h-full rounded-full bg-gray-800" :style="{ width: bar(d.count, topDoctypes) + '%' }"></div>
					</div>
				</div>
			</div>
		</div>

		<!-- Per-user adoption -->
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<h4 class="mb-3 text-xs font-semibold uppercase text-gray-500">Per-user adoption</h4>
			<table class="w-full text-xs">
				<thead>
					<tr class="border-b border-gray-100 text-left text-gray-500">
						<th class="py-2">User</th><th class="text-right">Requests</th><th class="text-right">Tool calls</th><th class="text-right">Cost</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="u in perUser" :key="u.user" class="border-b border-gray-50">
						<td class="py-2 font-mono text-gray-700">{{ u.user }}</td>
						<td class="text-right">{{ fmtNum(u.requests) }}</td>
						<td class="text-right text-gray-500">{{ fmtNum(u.tools_used) }}</td>
						<td class="text-right text-gray-500">${{ Number(u.cost_usd || 0).toFixed(2) }}</td>
					</tr>
					<tr v-if="loading"><td colspan="4" class="py-6 text-center text-gray-400">Loading…</td></tr>
					<tr v-if="!loading && !perUser.length"><td colspan="4" class="py-6 text-center text-gray-400">No usage recorded yet.</td></tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

<script>
import { call } from 'frappe-ui';

export default {
	name: 'AiInsights',
	data() {
		return {
			period: 'month',
			loading: false,
			summary: { total_requests: 0, total_tools: 0, total_cost: 0, active_users: 0, avg_latency_ms: 0 },
			topTools: [],
			topDoctypes: [],
			perUser: [],
		};
	},
	computed: {
		periodLabel() { return this.period === 'week' ? 'last 7 days' : 'last 30 days'; },
	},
	mounted() { this.load(); },
	watch: { period() { this.load(); } },
	methods: {
		async load() {
			// Live cross-client Insights from the control plane (same site).
			// Soft-fail: keep the empty state if the control-center app is unreachable.
			this.loading = true;
			this.topTools = [];
			this.topDoctypes = [];
			this.perUser = [];
			try {
				const d = await call('sanad_ai_control_center.insights.get_insights', { period: this.period });
				this.summary = d.summary || this.summary;
				this.topTools = d.top_tools || [];
				this.topDoctypes = d.top_doctypes || [];
				this.perUser = d.per_user || [];
			} catch (e) {
				// control-center unreachable — leave the empty state
			}
			this.loading = false;
		},
		fmtNum(n) { return Number(n || 0).toLocaleString('en-US'); },
		bar(count, list) {
			const max = Math.max(...list.map((x) => x.count), 1);
			return Math.max(3, Math.round((count / max) * 100));
		},
	},
};
</script>
