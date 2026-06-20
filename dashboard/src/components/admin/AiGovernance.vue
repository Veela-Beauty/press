<template>
	<div class="space-y-4">
		<!-- KPI row — 4 cards (matches prototype) -->
		<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Spend MTD</p>
				<p class="mt-1 text-2xl font-bold">${{ fmtMoney(kpi.spend_mtd) }}</p>
				<p class="text-xs text-gray-400">
					{{ budgetPct }}% of ${{ fmtMoney(kpi.budget_mtd) }} budget
				</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Active seats</p>
				<p class="mt-1 text-2xl font-bold">
					{{ kpi.active_seats || 0 }}
					<span class="text-sm font-normal text-gray-400">/ {{ kpi.total_seats || 0 }}</span>
				</p>
				<p class="text-xs text-gray-400">{{ kpi.seats_note || 'live seat usage' }}</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Subscriptions</p>
				<p class="mt-1 text-2xl font-bold">{{ kpi.subscriptions || subscriptions.length }}</p>
				<p class="text-xs text-gray-400">{{ kpi.subscriptions_note || 'active plans' }}</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Open incidents</p>
				<p class="mt-1 text-2xl font-bold" :class="kpi.open_incidents > 0 ? 'text-orange-600' : ''">
					{{ kpi.open_incidents || 0 }}
				</p>
				<p class="text-xs text-gray-400">{{ kpi.incidents_note || 'seats paused on budget' }}</p>
			</div>
		</div>

		<!-- Seats table -->
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-sm font-semibold">
					<i class="fa fa-user-circle mr-1 text-blue-600"></i>
					Seats
				</h3>
				<Button size="sm" variant="solid" @click="$emit('edit-rules')">Edit Policy</Button>
			</div>
			<table class="w-full text-xs">
				<thead>
					<tr class="border-b border-gray-100 text-left text-gray-500">
						<th class="py-2">User</th>
						<th>Subscription</th>
						<th>Tier</th>
						<th>Budget</th>
						<th>Spend</th>
						<th>Status</th>
						<th></th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="seat in seats" :key="seat.user" class="border-b border-gray-50">
						<td class="py-2 font-mono text-gray-700">{{ seat.user }}</td>
						<td>{{ seat.subscription }}</td>
						<td class="text-gray-500">{{ seat.tier }}</td>
						<td class="font-mono">${{ fmtMoney(seat.budget) }}</td>
						<td>
							<div class="font-mono">${{ fmtMoney(seat.spend) }}</div>
							<div class="mt-1 h-1.5 overflow-hidden rounded-full bg-gray-100">
								<div
									class="h-full rounded-full"
									:class="seatBarClass(seat)"
									:style="{ width: seatPct(seat) + '%' }"
								></div>
							</div>
						</td>
						<td>
							<span
								class="rounded-full px-2 py-0.5 text-[10px] font-medium"
								:class="statusBadgeClass(seat.status)"
							>
								{{ seat.status || 'Active' }}
							</span>
						</td>
						<td class="text-right">
							<Button size="sm" variant="outline">
								{{ (seat.status || '').toLowerCase() === 'paused' ? 'Resume' : 'Manage' }}
							</Button>
						</td>
					</tr>
					<tr v-if="seats.length === 0">
						<td colspan="7" class="py-6 text-center text-gray-400">No seats provisioned yet.</td>
					</tr>
				</tbody>
			</table>
		</div>

		<!-- Subscriptions + Providers (two-up) -->
		<div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
			<!-- Subscriptions table -->
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<h3 class="mb-3 text-sm font-semibold">
					<i class="fa fa-credit-card mr-1 text-blue-600"></i>
					Subscriptions
				</h3>
				<table class="w-full text-xs">
					<thead>
						<tr class="border-b border-gray-100 text-left text-gray-500">
							<th class="py-2">Client</th>
							<th>Plan</th>
							<th>Seats</th>
							<th>Spend / Budget</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="sub in subscriptions" :key="sub.client" class="border-b border-gray-50">
							<td class="py-2 font-semibold text-gray-800">{{ sub.client }}</td>
							<td>{{ sub.plan }}</td>
							<td>{{ sub.seats_used || 0 }}/{{ sub.seats_total || 0 }}</td>
							<td class="font-mono">${{ fmtMoney(sub.spend) }} / ${{ fmtMoney(sub.budget) }}</td>
						</tr>
						<tr v-if="subscriptions.length === 0">
							<td colspan="4" class="py-6 text-center text-gray-400">No subscriptions yet.</td>
						</tr>
					</tbody>
				</table>
			</div>

			<!-- Providers table -->
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<h3 class="mb-3 text-sm font-semibold">
					<i class="fa fa-plug mr-1 text-blue-600"></i>
					Providers
				</h3>
				<table class="w-full text-xs">
					<thead>
						<tr class="border-b border-gray-100 text-left text-gray-500">
							<th class="py-2">Provider</th>
							<th>Tier / model</th>
							<th>Region</th>
							<th>Cost MTD</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="(p, i) in providers" :key="i" class="border-b border-gray-50">
							<td class="py-2 text-gray-800">{{ p.provider }}</td>
							<td class="text-gray-500">{{ p.tier }}</td>
							<td>{{ p.region || '—' }}</td>
							<td>
								<span v-if="p.connected" class="font-mono">${{ fmtMoney(p.cost) }}</span>
								<Button v-else size="sm" variant="outline">Connect</Button>
							</td>
						</tr>
						<tr v-if="providers.length === 0">
							<td colspan="4" class="py-6 text-center text-gray-400">No providers configured.</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</div>
</template>

<script>
import { Button, call } from 'frappe-ui';

export default {
	name: 'AiGovernance',
	components: { Button },
	emits: ['edit-rules'],
	data() {
		return {
			kpi: {},
			seats: [],
			subscriptions: [],
			providers: [],
		};
	},
	computed: {
		budgetPct() {
			if (!this.kpi.budget_mtd || !this.kpi.spend_mtd) return 0;
			return Math.round((this.kpi.spend_mtd / this.kpi.budget_mtd) * 100);
		},
	},
	mounted() {
		this.load();
	},
	methods: {
		async load() {
			// Live gateway control-plane data (same site). Soft-fail: if the
			// sanad_ai_control_center app isn't reachable, keep the empty state.
			try {
				const g = await call('sanad_ai_control_center.api.get_governance_overview');
				this.kpi = g.kpi || {};
				this.seats = g.seats || [];
				this.subscriptions = g.subscriptions || [];
			} catch (e) {
				// control-center unreachable — leave KPIs/seats/subscriptions empty
			}
			try {
				const a = await call('sanad_ai_control_center.api.get_accounts_overview');
				this.providers = this.mapProviders(a);
			} catch (e) {
				// control-center unreachable — leave providers empty
			}
		},
		// get_accounts_overview shape: { groups: [{ model, accounts: [{ provider, region, cost, connected }] }] }
		// Flatten each group's accounts into provider rows, carrying the group's model/tier.
		mapProviders(data) {
			const groups = (data && data.groups) || [];
			const rows = [];
			groups.forEach((grp) => {
				const accounts = grp.accounts || [];
				if (accounts.length === 0) {
					rows.push({
						provider: grp.model || '—',
						tier: grp.tier || grp.model || '—',
						region: grp.region || '—',
						cost: grp.cost || 0,
						connected: false,
					});
					return;
				}
				accounts.forEach((acc) => {
					rows.push({
						provider: acc.provider || acc.name || grp.model || '—',
						tier: acc.tier || grp.tier || grp.model || '—',
						region: acc.region || '—',
						cost: acc.cost != null ? acc.cost : 0,
						connected: acc.connected != null ? acc.connected : true,
					});
				});
			});
			return rows;
		},
		fmtMoney(n) {
			const v = Number(n);
			if (!v) return '0.00';
			return v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
		},
		seatPct(seat) {
			if (!seat.budget || !seat.spend) return 0;
			return Math.min(100, Math.round((seat.spend / seat.budget) * 100));
		},
		seatBarClass(seat) {
			const pct = this.seatPct(seat);
			if (pct >= 100) return 'bg-red-500';
			if (pct >= 90) return 'bg-orange-500';
			return 'bg-gray-800';
		},
		statusBadgeClass(status) {
			const s = (status || 'active').toLowerCase();
			if (s === 'paused') return 'bg-orange-100 text-orange-700';
			if (s === 'revoked') return 'bg-red-100 text-red-700';
			return 'bg-green-100 text-green-700';
		},
	},
};
</script>
