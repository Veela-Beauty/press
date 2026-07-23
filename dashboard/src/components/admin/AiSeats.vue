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
						<td class="text-right"><Button size="sm" variant="outline" @click="openManage(seat)">Manage</Button></td>
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
		<Dialog :options="{ title: 'Manage seat', size: 'md' }" v-model="showManage">
			<template #body-content>
				<div class="space-y-3">
					<p class="text-xs text-gray-500">{{ manage.user }} — {{ manage.subscription }}</p>
					<div v-if="manage.status === 'revoked'" class="rounded bg-red-50 px-3 py-2 text-xs text-red-700">
						This seat is revoked — the user has no AI access. Re-provision it to restore access.
					</div>
					<template v-else>
						<FormControl type="select" label="Tier" v-model="manage.tier_access" :options="tierOptions" />
						<FormControl type="number" label="Monthly budget (USD)" v-model="manage.monthly_budget_usd" />
						<p class="text-[11px] text-gray-400">Spend this month: ${{ fmt(manage.spend) }} of ${{ fmt(manage.monthly_budget_usd) }}</p>
						<p class="text-[11px] text-gray-400">Revoking stops the user's AI access immediately and can't be undone here — you'd re-provision to restore it. Their app role is cleaned up on their site's next sync.</p>
					</template>
				</div>
			</template>
			<template #actions v-if="manage.status !== 'revoked'">
				<Button variant="subtle" theme="red" :loading="managing" @click="confirmRevoke">Revoke seat</Button>
				<Button variant="solid" :loading="managing" @click="doManage('update')">Save changes</Button>
			</template>
		</Dialog>
	</div>
</template>

<script>
import { Button, Dialog, FormControl, call } from 'frappe-ui';
import { confirmDialog } from '../../utils/components';
import { toast } from 'vue-sonner';

export default {
	name: 'AiSeats',
	components: { Button, Dialog, FormControl },
	data() {
		return {
			seats: [], loading: false, show: false, saving: false,
			form: { user: '', client_site: '', monthly_budget_usd: 20, tier_access: 'smart,fast' },
			showManage: false, managing: false,
			manage: { name: '', user: '', subscription: '', tier_access: '', monthly_budget_usd: 20, spend: 0, status: 'active' },
			tierOptions: [
				{ label: 'Fast (DeepSeek)', value: 'fast' },
				{ label: 'Smart (GLM)', value: 'smart' },
				{ label: 'Cheap (Qwen)', value: 'cheap' },
				{ label: 'Smart + Fast', value: 'smart,fast' },
			],
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
		openManage(seat) {
			this.manage = {
				name: seat.name, user: seat.user, subscription: seat.subscription,
				tier_access: seat.tier || 'fast', monthly_budget_usd: seat.budget || 20,
				spend: seat.spend || 0, status: (seat.status || 'active').toLowerCase(),
			};
			this.showManage = true;
		},
		confirmRevoke() {
			confirmDialog({
				title: 'Revoke seat',
				message: `Revoke AI access for <b>${this.manage.user}</b>? Their access stops immediately and this can't be undone here — you'd re-provision to restore it.`,
				onSuccess: ({ hide }) => { this.doManage('revoke'); hide(); },
			});
		},
		async doManage(action) {
			if (!this.manage.name) { toast.error('Seat id missing'); return; }
			this.managing = true;
			try {
				await call('sanad_ai_control_center.api.manage_seat', {
					seat: this.manage.name, action,
					tier_access: this.manage.tier_access, monthly_budget_usd: this.manage.monthly_budget_usd,
				});
				toast.success(action === 'revoke' ? 'Seat revoked' : 'Seat updated');
				this.showManage = false;
				this.load();
			} catch (e) { toast.error(e.messages?.[0] || 'Could not manage seat'); }
			this.managing = false;
		},
		fmt(n) { const v = Number(n); return v ? v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'; },
		pct(s) { if (!s.budget || !s.spend) return 0; return Math.min(100, Math.round((s.spend / s.budget) * 100)); },
		barClass(s) { const p = this.pct(s); return p >= 100 ? 'bg-red-500' : p >= 90 ? 'bg-orange-500' : 'bg-gray-800'; },
		badge(st) { const s = (st || 'active').toLowerCase(); return s === 'paused' ? 'bg-orange-100 text-orange-700' : s === 'revoked' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'; },
	},
};
</script>
