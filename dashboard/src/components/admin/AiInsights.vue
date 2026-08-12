<template>
	<div class="space-y-4">
		<div class="flex items-center justify-between">
			<h3 class="text-base font-semibold">Insights — Adoption</h3>
			<select v-model="period" class="rounded border border-gray-200 px-2 py-1 text-xs">
				<option value="month">Last 30 days</option>
				<option value="week">Last 7 days</option>
			</select>
		</div>

		<!-- Adoption KPIs -->
		<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Seat utilization</p>
				<p class="mt-1 text-2xl font-bold">{{ a.seat_utilization_pct }}%</p>
				<p class="text-xs text-gray-400">{{ a.active_seats }} / {{ a.licensed_seats }} active</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Depth / active user</p>
				<p class="mt-1 text-2xl font-bold">{{ fmt(a.depth_per_active) }}</p>
				<p class="text-xs text-gray-400">requests per active user</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Tool-backed rate</p>
				<p class="mt-1 text-2xl font-bold">{{ fmt(a.tool_backed_rate) }}×</p>
				<p class="text-xs text-gray-400">tool calls per request</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Stickiness</p>
				<p class="mt-1 text-2xl font-bold">{{ fmt(a.stickiness) }}</p>
				<p class="text-xs text-gray-400">DAU ÷ WAU</p>
			</div>
		</div>

		<div class="grid gap-3 lg:grid-cols-2">
			<!-- WAU by depth tier -->
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<h4 class="mb-3 text-xs font-semibold uppercase text-gray-500">Weekly active users by depth</h4>
				<div v-if="!wau.length" class="py-6 text-center text-xs text-gray-400">No weekly activity yet.</div>
				<div v-for="w in wau" :key="w.week" class="mb-2.5">
					<div class="mb-1 flex justify-between text-xs text-gray-500"><span>{{ w.week }}</span><span>{{ w.light + w.regular + w.power }} users</span></div>
					<div class="flex h-2.5 overflow-hidden rounded bg-gray-100">
						<div class="h-full bg-indigo-900" :style="{ width: seg(w.power) }"></div>
						<div class="h-full bg-indigo-400" :style="{ width: seg(w.regular) }"></div>
						<div class="h-full bg-indigo-200" :style="{ width: seg(w.light) }"></div>
					</div>
				</div>
				<div class="mt-3 flex gap-4 text-[11px] text-gray-500">
					<span><i class="mr-1 inline-block h-2 w-2 rounded-sm bg-indigo-900"></i>Power 10+</span>
					<span><i class="mr-1 inline-block h-2 w-2 rounded-sm bg-indigo-400"></i>Regular 3–9</span>
					<span><i class="mr-1 inline-block h-2 w-2 rounded-sm bg-indigo-200"></i>Light 1–2</span>
				</div>
			</div>

			<!-- Top DocTypes -->
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<h4 class="mb-3 text-xs font-semibold uppercase text-gray-500">DocTypes used</h4>
				<div v-if="!doctypes.length" class="py-6 text-center text-xs text-gray-400">No DocType activity yet.</div>
				<div v-for="d in doctypes" :key="d.name" class="mb-2">
					<div class="flex items-center justify-between text-xs"><span class="text-gray-700">{{ d.name }}</span><span class="text-gray-500">{{ d.count }}</span></div>
					<div class="mt-1 h-1.5 rounded-full bg-gray-100"><div class="h-full rounded-full bg-gray-800" :style="{ width: bar(d.count, doctypes) }"></div></div>
				</div>
			</div>
		</div>

		<!-- Per-user adoption -->
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<h4 class="mb-3 text-xs font-semibold uppercase text-gray-500">Per-user adoption</h4>
			<table class="w-full text-xs">
				<thead>
					<tr class="border-b border-gray-100 text-left text-gray-500">
						<th class="py-2">User</th><th class="text-right">Requests</th><th class="text-right">Tool calls</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="u in perUser" :key="u.user" class="border-b border-gray-50">
						<td class="py-2 font-mono text-gray-700">{{ u.user }}</td>
						<td class="text-right">{{ u.requests }}</td>
						<td class="text-right text-gray-500">{{ u.tools_used }}</td>
					</tr>
					<tr v-if="loading"><td colspan="3" class="py-6 text-center text-gray-400">Loading…</td></tr>
					<tr v-if="!loading && !perUser.length"><td colspan="3" class="py-6 text-center text-gray-400">No usage recorded yet.</td></tr>
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
			a: { seat_utilization_pct: 0, active_seats: 0, licensed_seats: 0, depth_per_active: 0, tool_backed_rate: 0, stickiness: 0 },
			wau: [],
			doctypes: [],
			perUser: [],
		};
	},
	mounted() { this.load(); },
	watch: { period() { this.load(); } },
	methods: {
		async load() {
			this.loading = true;
			this.wau = []; this.doctypes = []; this.perUser = [];
			try {
				const d = await call('sanad_ai_control_center.insights.get_insights', { period: this.period });
				this.a = d.adoption || this.a;
				this.wau = d.wau_series || [];
				this.doctypes = d.top_doctypes || [];
				this.perUser = d.per_user || [];
			} catch (e) { /* control-center unreachable */ }
			this.loading = false;
		},
		fmt(n) { return Number(n || 0).toLocaleString('en-US', { maximumFractionDigits: 2 }); },
		seg(n) { const max = Math.max(...this.wau.map((w) => w.light + w.regular + w.power), 1); return (n / max) * 100 + '%'; },
		bar(count, list) { const max = Math.max(...list.map((x) => x.count), 1); return Math.max(3, Math.round((count / max) * 100)) + '%'; },
	},
};
</script>
