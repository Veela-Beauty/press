<template>
	<div class="space-y-4">
		<div class="flex items-center justify-between">
			<div>
				<h2 class="text-lg font-semibold">Providers</h2>
				<p class="text-xs text-gray-500">Gateway pool — two accounts on the same model load-balance by weight.</p>
			</div>
			<Button variant="solid" @click="openConnect()">Add provider</Button>
		</div>
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<table class="w-full text-xs">
				<thead>
					<tr class="border-b border-gray-100 text-left text-gray-500">
						<th class="py-2">Provider</th><th>Serves as</th><th>Region</th><th>Cost MTD</th><th></th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="(p, i) in providers" :key="i" class="border-b border-gray-50">
						<td class="py-2 text-gray-800">{{ p.provider }}</td>
						<td class="font-mono text-gray-500">{{ p.tier }}</td>
						<td>{{ p.region || '—' }}</td>
						<td>
							<span v-if="p.connected" class="font-mono">${{ fmt(p.cost) }}</span>
							<span v-else class="text-gray-400">not connected</span>
						</td>
						<td class="text-right">
							<Button v-if="!p.connected" size="sm" variant="outline" @click="openConnect(p.tier)">Connect</Button>
						</td>
					</tr>
					<tr v-if="loading"><td colspan="5" class="py-6 text-center text-gray-400">Loading…</td></tr>
					<tr v-if="!loading && providers.length === 0"><td colspan="5" class="py-6 text-center text-gray-400">No providers configured.</td></tr>
				</tbody>
			</table>
		</div>
		<Dialog :options="{ title: 'Connect provider', size: 'md' }" v-model="show">
			<template #body-content>
				<div class="space-y-3">
					<FormControl type="select" label="Provider" v-model="form.provider" :options="providerOptions" />
					<FormControl type="password" label="API key" v-model="form.token" placeholder="paste the provider API key" />
					<FormControl label="Account label" v-model="form.account_label" placeholder="e.g. Z.AI #2" />
					<FormControl label="Serve as model" v-model="form.serve_as_model" placeholder="glm-4.5-air" />
					<div class="grid grid-cols-2 gap-3">
						<FormControl type="number" label="Weight" v-model="form.weight" placeholder="1" />
						<FormControl type="number" label="Monthly budget (USD)" v-model="form.monthly_budget" placeholder="optional" />
					</div>
					<p class="text-xs text-gray-400">Two accounts with the same “Serve as model” load-balance by weight. Subscription logins are own-use only.</p>
				</div>
			</template>
			<template #actions><Button variant="solid" :loading="saving" @click="submit">Test &amp; connect</Button></template>
		</Dialog>
	</div>
</template>

<script>
import { Button, Dialog, FormControl, call } from 'frappe-ui';
import { toast } from 'vue-sonner';

export default {
	name: 'AiProviders',
	components: { Button, Dialog, FormControl },
	data() {
		return {
			providers: [], catalog: [], loading: false, show: false, saving: false,
			form: { provider: '', token: '', account_label: '', serve_as_model: '', weight: 1, monthly_budget: null },
		};
	},
	computed: {
		providerOptions() {
			return (this.catalog || []).filter((r) => r.connectable).map((r) => ({ label: r.label || r.provider_key, value: r.provider_key }));
		},
	},
	mounted() { this.load(); },
	methods: {
		async load() {
			this.loading = true;
			try {
				const a = await call('sanad_ai_control_center.api.get_accounts_overview');
				this.providers = this.mapProviders(a);
			} catch (e) { /* control-center unreachable */ }
			this.loading = false;
		},
		async openConnect(prefillModel) {
			this.form = { provider: '', token: '', account_label: '', serve_as_model: prefillModel || '', weight: 1, monthly_budget: null };
			if (!this.catalog.length) {
				try { this.catalog = await call('sanad_ai_control_center.gateway.catalog.get_provider_catalog'); }
				catch (e) { toast.error('Could not load the provider catalog'); return; }
			}
			if (!this.form.provider && this.providerOptions.length) this.form.provider = this.providerOptions[0].value;
			this.show = true;
		},
		async submit() {
			const f = this.form;
			if (!f.provider || !f.token || !f.serve_as_model) { toast.error('Provider, API key, and Serve-as-model are required'); return; }
			this.saving = true;
			try {
				await call('sanad_ai_control_center.api.connect_account', {
					provider: f.provider, token: f.token, account_label: f.account_label || f.provider,
					serve_as_model: f.serve_as_model, weight: f.weight || 1, monthly_budget: f.monthly_budget || null,
				});
				toast.success('Provider connected to the gateway pool');
				this.show = false;
				this.load();
			} catch (e) { toast.error(e.messages?.[0] || 'Could not connect the provider'); }
			this.saving = false;
		},
		mapProviders(data) {
			const groups = (data && data.groups) || [];
			const rows = [];
			groups.forEach((grp) => {
				const accounts = grp.accounts || [];
				if (accounts.length === 0) {
					rows.push({ provider: grp.model || '—', tier: grp.tier || grp.model || '—', region: grp.region || '—', cost: grp.cost || 0, connected: false });
					return;
				}
				accounts.forEach((acc) => {
					rows.push({
						provider: acc.account_label || acc.provider || grp.model || '—',
						tier: acc.serve_as_model || acc.tier || grp.tier || grp.model || '—',
						region: acc.region || '—',
						cost: acc.spend_to_date != null ? acc.spend_to_date : acc.cost != null ? acc.cost : 0,
						connected: acc.connected != null ? acc.connected : true,
					});
				});
			});
			return rows;
		},
		fmt(n) { const v = Number(n); return v ? v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'; },
	},
};
</script>
