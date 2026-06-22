<template>
	<div class="space-y-4">
		<div>
			<h2 class="text-lg font-semibold">Subscriptions</h2>
			<p class="text-xs text-gray-500">Per-client AI plans and seat allotment.</p>
		</div>
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<table class="w-full text-xs">
				<thead>
					<tr class="border-b border-gray-100 text-left text-gray-500">
						<th class="py-2">Client</th><th>Plan</th><th>Seats</th><th>Spend / Budget</th><th>Status</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="sub in subscriptions" :key="sub.client" class="border-b border-gray-50">
						<td class="py-2 font-semibold text-gray-800">{{ sub.client }}</td>
						<td>{{ sub.plan }}</td>
						<td>{{ sub.seats || 0 }}<span v-if="sub.seats_allowed">/{{ sub.seats_allowed }}</span></td>
						<td class="font-mono">${{ fmt(sub.spend) }} / ${{ fmt(sub.budget) }}</td>
						<td><span class="rounded-full px-2 py-0.5 text-[10px] font-medium" :class="badge(sub.status)">{{ sub.status || 'active' }}</span></td>
					</tr>
					<tr v-if="loading"><td colspan="5" class="py-6 text-center text-gray-400">Loading…</td></tr>
					<tr v-if="!loading && subscriptions.length === 0"><td colspan="5" class="py-6 text-center text-gray-400">No subscriptions yet.</td></tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

<script>
import { call } from 'frappe-ui';

export default {
	name: 'AiSubscriptions',
	data() { return { subscriptions: [], loading: false }; },
	mounted() { this.load(); },
	methods: {
		async load() {
			this.loading = true;
			try {
				const g = await call('sanad_ai_control_center.api.get_governance_overview');
				this.subscriptions = g.subscriptions || [];
			} catch (e) { /* control-center unreachable */ }
			this.loading = false;
		},
		fmt(n) { const v = Number(n); return v ? v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'; },
		badge(st) { const s = (st || 'active').toLowerCase(); return s === 'trial' ? 'bg-orange-100 text-orange-700' : s === 'past_due' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'; },
	},
};
</script>
