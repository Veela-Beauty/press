<template>
	<div class="space-y-4">
		<div class="flex items-center justify-between">
			<div>
				<h2 class="text-lg font-semibold">AI Seats</h2>
				<p class="text-xs text-gray-500">Per-user managed AI seats — assign, adjust budget, revoke.</p>
			</div>
			<Button variant="solid" @click="openProvision">Provision seat</Button>
		</div>
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<table class="w-full text-xs">
				<thead>
					<tr class="border-b border-gray-100 text-left text-gray-500">
						<th class="py-2">Seat (user)</th><th>Subscription</th><th>Tier</th><th>Budget</th><th>Spend</th><th>Status</th><th></th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="seat in seats" :key="seat.user" class="border-b border-gray-50">
						<td class="py-2 font-mono text-gray-700">{{ seat.user }}</td>
						<td>{{ seat.subscription }}</td>
						<td class="text-gray-500">{{ seat.tier }}</td>
						<td class="font-mono">${{ fmt(seat.budget) }}</td>
						<td>
							<div class="font-mono">${{ fmt(seat.spend) }}</div>
							<div class="mt-1 h-1.5 overflow-hidden rounded-full bg-gray-100">
								<div class="h-full rounded-full" :class="barClass(seat)" :style="{ width: pct(seat) + '%' }"></div>
							</div>
						</td>
						<td><span class="rounded-full px-2 py-0.5 text-[10px] font-medium" :class="badge(seat.status)">{{ seat.status || 'Active' }}</span></td>
						<td class="text-right"><Button size="sm" variant="outline">{{ (seat.status || '').toLowerCase() === 'paused' ? 'Resume' : 'Manage' }}</Button></td>
					</tr>
					<tr v-if="loading"><td colspan="7" class="py-6 text-center text-gray-400">Loading…</td></tr>
					<tr v-if="!loading && seats.length === 0"><td colspan="7" class="py-6 text-center text-gray-400">No seats provisioned yet.</td></tr>
				</tbody>
			</table>
		</div>
		<Dialog :options="{ title: 'Provision seat', size: 'md' }" v-model="show">
			<template #body-content>
				<div class="space-y-3">
					<FormControl label="User" v-model="form.user" placeholder="user@client-site" />
					<FormControl label="Client site" v-model="form.client_site" placeholder="lipton.eg" />
					<FormControl type="number" label="Monthly budget (USD)" v-model="form.monthly_budget_usd" placeholder="20" />
					<FormControl label="Tier access" v-model="form.tier_access" placeholder="smart,fast" />
				</div>
			</template>
			<template #actions><Button variant="solid" :loading="saving" @click="submit">Provision seat</Button></template>
		</Dialog>
	</div>
</template>

<script>
import { Button, Dialog, FormControl, call } from 'frappe-ui';
import { toast } from 'vue-sonner';

export default {
	name: 'AiSeats',
	components: { Button, Dialog, FormControl },
	data() {
		return {
			seats: [], loading: false, show: false, saving: false,
			form: { user: '', client_site: '', monthly_budget_usd: 20, tier_access: 'smart,fast' },
		};
	},
	mounted() { this.load(); },
	methods: {
		async load() {
			this.loading = true;
			try {
				const g = await call('sanad_ai_control_center.api.get_governance_overview');
				this.seats = g.seats || [];
			} catch (e) { /* control-center unreachable */ }
			this.loading = false;
		},
		openProvision() {
			this.form = { user: '', client_site: '', monthly_budget_usd: 20, tier_access: 'smart,fast' };
			this.show = true;
		},
		async submit() {
			if (!this.form.user || !this.form.client_site) { toast.error('User and client site are required'); return; }
			this.saving = true;
			try {
				await call('sanad_ai_control_center.api.provision_seat', { ...this.form });
				toast.success('Seat provisioned');
				this.show = false;
				this.load();
			} catch (e) { toast.error(e.messages?.[0] || 'Could not provision seat'); }
			this.saving = false;
		},
		fmt(n) { const v = Number(n); return v ? v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'; },
		pct(s) { if (!s.budget || !s.spend) return 0; return Math.min(100, Math.round((s.spend / s.budget) * 100)); },
		barClass(s) { const p = this.pct(s); return p >= 100 ? 'bg-red-500' : p >= 90 ? 'bg-orange-500' : 'bg-gray-800'; },
		badge(st) { const s = (st || 'active').toLowerCase(); return s === 'paused' ? 'bg-orange-100 text-orange-700' : s === 'revoked' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'; },
	},
};
</script>
