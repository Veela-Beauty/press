<template>
	<div class="space-y-4">
		<!-- KPI row - 4 cards (matches prototype) -->
		<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Spend, MTD</p>
				<p class="mt-1 text-2xl font-bold">${{ fmtMoney(kpi.spend_mtd) }}</p>
				<p class="text-xs text-gray-400">
					{{ budgetPct }}% of ${{ fmtMoney(kpi.budget) }} budget
				</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Active seats</p>
				<p class="mt-1 text-2xl font-bold">
					{{ kpi.active_seats || 0 }}
					<span class="text-sm font-normal text-gray-400">/ {{ kpi.total_seats || 0 }}</span>
				</p>
				<p class="text-xs text-gray-400">{{ seatsNote }}</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Subscriptions</p>
				<p class="mt-1 text-2xl font-bold">{{ kpi.subscriptions || subscriptions.length }}</p>
				<p class="text-xs text-gray-400">{{ subscriptionsNote }}</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Open incidents</p>
				<p class="mt-1 text-2xl font-bold" :class="openIncidents > 0 ? 'text-orange-600' : ''">
					{{ openIncidents }}
				</p>
				<p class="text-xs text-gray-400">seats paused on budget</p>
			</div>
		</div>

		<!-- Governance and Risk (5 cards) -->
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<div class="mb-3">
				<h3 class="text-sm font-semibold">Governance and Risk</h3>
				<p class="text-xs text-gray-400">Across all client sites: activity over the last 30 days; exposure is current state.</p>
			</div>
			<div class="grid grid-cols-2 gap-3 sm:grid-cols-5">
				<div>
					<p class="text-xs font-medium uppercase text-gray-500">High-risk pending</p>
					<p class="mt-1 text-2xl font-bold" :class="risk.pending > 0 ? 'text-orange-600' : ''">{{ risk.pending || 0 }}</p>
					<p class="text-xs text-gray-400">awaiting approval now</p>
				</div>
				<div>
					<p class="text-xs font-medium uppercase text-gray-500">God-mode exposure</p>
					<p class="mt-1 text-2xl font-bold" :class="risk.god_mode > 0 ? 'text-orange-600' : ''">{{ risk.god_mode || 0 }}</p>
					<p class="text-xs text-gray-400">auto-accept agents{{ risk.open_access ? ', ' + risk.open_access + ' open to all' : '' }}</p>
				</div>
				<div>
					<p class="text-xs font-medium uppercase text-gray-500">run_sql calls</p>
					<p class="mt-1 text-2xl font-bold">{{ fmtNum(risk.run_sql) }}</p>
					<p class="text-xs text-gray-400">{{ risk.ai_sql_users || 0 }} users with SQL access</p>
				</div>
				<div>
					<p class="text-xs font-medium uppercase text-gray-500">Auto-accepted writes</p>
					<p class="mt-1 text-2xl font-bold">{{ fmtNum(risk.auto_writes) }}</p>
					<p class="text-xs text-gray-400">{{ fmtNum(risk.high_risk) }} high-risk actions</p>
				</div>
				<div>
					<p class="text-xs font-medium uppercase text-gray-500">Gateway probes</p>
					<p class="mt-1 text-2xl font-bold" :class="risk.probes > 0 ? 'text-red-600' : ''">{{ fmtNum(risk.probes) }}</p>
					<p class="text-xs text-gray-400">rejected auth/SSRF attempts</p>
				</div>
			</div>
		</div>

		<!-- Seats, grouped by customer (collapsed by default so a long customer list stays scannable) -->
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-sm font-semibold">Seats</h3>
				<Button size="sm" variant="solid" @click="openProvision">Provision seat</Button>
			</div>
			<div v-if="seats.length === 0" class="py-6 text-center text-xs text-gray-400">No seats provisioned yet.</div>
			<div v-else class="divide-y divide-gray-100">
				<div v-for="grp in seatGroups" :key="grp.client">
					<button type="button" class="flex w-full items-center justify-between rounded-none py-2.5 text-left" @click="toggleGroup(grp.client)">
						<span class="flex items-center gap-2">
							<svg class="h-3 w-3 shrink-0 text-gray-400 transition-transform" :class="expanded[grp.client] ? 'rotate-90' : ''" viewBox="0 0 12 12" fill="none">
								<path d="M4 2l4 4-4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
							</svg>
							<span class="text-sm font-semibold text-gray-800">{{ grp.client }}</span>
							<span class="text-xs text-gray-400">{{ grp.count }} seat{{ grp.count === 1 ? '' : 's' }}, {{ grp.active }} active</span>
						</span>
						<span class="font-mono text-xs text-gray-500">${{ fmtMoney(grp.spend) }}</span>
					</button>
					<table v-if="expanded[grp.client]" class="mb-2 w-full text-xs">
						<thead>
							<tr class="border-b border-gray-100 text-left text-gray-500">
								<th class="py-2 pl-5">Seat (user)</th>
								<th>Tier</th>
								<th>Budget</th>
								<th>Spend</th>
								<th>Status</th>
								<th></th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="seat in grp.seats" :key="seat.user" class="border-b border-gray-50">
								<td class="py-2 pl-5 font-mono text-gray-700">{{ seat.user }}</td>
								<td class="text-gray-500">{{ seat.tier }}</td>
								<td class="font-mono">${{ fmtMoney(seat.budget) }}</td>
								<td>
									<div class="font-mono">${{ fmtMoney(seat.spend) }}</div>
									<div class="mt-1 h-1.5 overflow-hidden rounded-full bg-gray-100">
										<div class="h-full rounded-full" :class="seatBarClass(seat)" :style="{ width: seatPct(seat) + '%' }"></div>
									</div>
								</td>
								<td>
									<span class="rounded-full px-2 py-0.5 text-[10px] font-medium" :class="statusBadgeClass(seat.status)">{{ seat.status || 'Active' }}</span>
								</td>
								<td class="text-right">
									<Button size="sm" variant="outline">{{ (seat.status || '').toLowerCase() === 'paused' ? 'Resume' : 'Manage' }}</Button>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>
		</div>

		<!-- Subscriptions + Providers (two-up) -->
		<div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
			<!-- Subscriptions table -->
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<h3 class="mb-3 text-sm font-semibold">Subscriptions</h3>
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
							<td>{{ sub.seats || 0 }}<span v-if="sub.seats_allowed">/{{ sub.seats_allowed }}</span></td>
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
				<div class="mb-3 flex items-center justify-between">
					<h3 class="text-sm font-semibold">Providers</h3>
					<Button size="sm" variant="subtle" @click="openConnect()">Add provider</Button>
				</div>
				<table class="w-full text-xs">
					<thead>
						<tr class="border-b border-gray-100 text-left text-gray-500">
							<th class="py-2">Provider</th>
							<th>Tier</th>
							<th>Region</th>
							<th>Cost MTD</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="(p, i) in providers" :key="i" class="border-b border-gray-50">
							<td class="py-2 text-gray-800">{{ p.provider }}</td>
							<td class="text-gray-500">{{ p.tier }}</td>
							<td>{{ p.region || '-' }}</td>
							<td>
								<span v-if="p.connected" class="font-mono">${{ fmtMoney(p.cost) }}</span>
								<Button v-else size="sm" variant="outline" @click="openConnect(p.tier)">Connect</Button>
							</td>
						</tr>
						<tr v-if="providers.length === 0">
							<td colspan="4" class="py-6 text-center text-gray-400">No providers configured.</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<!-- Provision seat dialog - wired to sanad_ai_control_center.api.provision_seat -->
		<Dialog :options="{ title: 'Provision seat', size: 'md' }" v-model="showProvision">
			<template #body-content>
				<div class="space-y-3">
					<FormControl label="User" v-model="provision.user" placeholder="user@client-site" />
					<FormControl label="Client site" v-model="provision.client_site" placeholder="lipton.eg" />
					<FormControl
						label="Monthly budget (USD)"
						type="number"
						v-model="provision.monthly_budget_usd"
						placeholder="20"
					/>
					<FormControl label="Tier access" v-model="provision.tier_access" placeholder="smart,fast" />
				</div>
			</template>
			<template #actions>
				<Button variant="solid" :loading="provisioning" @click="submitProvision">Provision seat</Button>
			</template>
		</Dialog>

		<!-- Connect provider dialog - wired to sanad_ai_control_center.api.connect_account -->
		<Dialog :options="{ title: 'Connect provider', size: 'md' }" v-model="showConnect">
			<template #body-content>
				<div class="space-y-3">
					<FormControl
						type="select"
						label="Provider"
						v-model="connectForm.provider"
						:options="providerOptions"
					/>
					<FormControl
						type="password"
						label="API key"
						v-model="connectForm.token"
						placeholder="paste the provider API key"
					/>
					<FormControl
						label="Account label"
						v-model="connectForm.account_label"
						placeholder="e.g. Z.AI #2"
					/>
					<FormControl
						label="Serve as model"
						v-model="connectForm.serve_as_model"
						placeholder="glm-4.5-air"
					/>
					<div class="grid grid-cols-2 gap-3">
						<FormControl type="number" label="Weight" v-model="connectForm.weight" placeholder="1" />
						<FormControl
							type="number"
							label="Monthly budget (USD)"
							v-model="connectForm.monthly_budget"
							placeholder="optional"
						/>
					</div>
					<p class="text-xs text-gray-400">
						Two accounts with the same “Serve as model” load-balance by weight. Subscription logins
						(Claude/ChatGPT) are own-use only and can’t be connected here.
					</p>
				</div>
			</template>
			<template #actions>
				<Button variant="solid" :loading="connecting" @click="submitConnect">Test &amp; connect</Button>
			</template>
		</Dialog>
	</div>
</template>

<script>
import { Button, Dialog, FormControl, call } from 'frappe-ui';
import { toast } from 'vue-sonner';

export default {
	name: 'AiGovernance',
	components: { Button, Dialog, FormControl },
	emits: ['edit-rules'],
	data() {
		return {
			kpi: {},
			risk: {},
			expanded: {},
			seats: [],
			subscriptions: [],
			providers: [],
			showProvision: false,
			provisioning: false,
			provision: { user: '', client_site: '', monthly_budget_usd: 20, tier_access: 'smart,fast' },
			showConnect: false,
			connecting: false,
			catalog: [],
			connectForm: { provider: '', token: '', account_label: '', serve_as_model: '', weight: 1, monthly_budget: null },
		};
	},
	computed: {
		// Seats grouped by customer (subscription/client_site), busiest first. Collapsed
		// by default via `expanded` so a long customer list stays scannable.
		seatGroups() {
			const map = {};
			for (const s of this.seats) {
				const key = s.subscription || '(unassigned)';
				const g = (map[key] = map[key] || { client: key, seats: [], spend: 0, count: 0, active: 0 });
				g.seats.push(s);
				g.spend += Number(s.spend || 0);
				g.count += 1;
				if ((s.status || 'active').toLowerCase() === 'active') g.active += 1;
			}
			return Object.values(map).sort((a, b) => b.count - a.count);
		},
		budgetPct() {
			if (!this.kpi.budget || !this.kpi.spend_mtd) return 0;
			return Math.round((this.kpi.spend_mtd / this.kpi.budget) * 100);
		},
		// API returns kpis.paused + kpis.revoked (ints) - derive the sub-label the prototype shows.
		seatsNote() {
			const parts = [];
			if (this.kpi.paused) parts.push(`${this.kpi.paused} paused`);
			if (this.kpi.revoked) parts.push(`${this.kpi.revoked} revoked`);
			return parts.join(', ');
		},
		openIncidents() {
			return this.kpi.paused || 0;
		},
		subscriptionsNote() {
			const active = this.subscriptions.filter((s) => (s.status || 'active') === 'active').length;
			const trial = this.subscriptions.filter((s) => s.status === 'trial').length;
			if (trial) return `${active} active, ${trial} trial`;
			return `${active} active`;
		},
		// Only api_key providers can join the gateway pool (connectable). Subscription
		// logins (Claude/ChatGPT) are filtered out - connect_account refuses them anyway.
		providerOptions() {
			return (this.catalog || [])
				.filter((r) => r.connectable)
				.map((r) => ({ label: r.label || r.provider_key, value: r.provider_key }));
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
				this.kpi = g.kpis || g.kpi || {};
				this.seats = g.seats || [];
				this.subscriptions = g.subscriptions || [];
			} catch (e) {
				// control-center unreachable - leave KPIs/seats/subscriptions empty
			}
			try {
				const a = await call('sanad_ai_control_center.api.get_accounts_overview');
				this.providers = this.mapProviders(a);
			} catch (e) {
				// control-center unreachable: leave providers empty
			}
			try {
				this.risk = (await call('sanad_ai_control_center.api.get_governance_risk')) || {};
			} catch (e) {
				// control-center unreachable: leave the risk cards at zero
			}
		},
		openProvision() {
			this.provision = { user: '', client_site: '', monthly_budget_usd: 20, tier_access: 'smart,fast' };
			this.showProvision = true;
		},
		async submitProvision() {
			if (!this.provision.user || !this.provision.client_site) {
				toast.error('User and client site are required');
				return;
			}
			this.provisioning = true;
			try {
				await call('sanad_ai_control_center.api.provision_seat', {
					user: this.provision.user,
					client_site: this.provision.client_site,
					monthly_budget_usd: this.provision.monthly_budget_usd,
					tier_access: this.provision.tier_access,
				});
				toast.success('Seat provisioned');
				this.showProvision = false;
				this.load();
			} catch (e) {
				toast.error(e.messages?.[0] || 'Could not provision seat');
			}
			this.provisioning = false;
		},
		async openConnect(prefillModel) {
			this.connectForm = {
				provider: '',
				token: '',
				account_label: '',
				serve_as_model: prefillModel || '',
				weight: 1,
				monthly_budget: null,
			};
			if (!this.catalog.length) {
				try {
					this.catalog = await call('sanad_ai_control_center.gateway.catalog.get_provider_catalog');
				} catch (e) {
					toast.error('Could not load the provider catalog');
					return;
				}
			}
			if (!this.connectForm.provider && this.providerOptions.length) {
				this.connectForm.provider = this.providerOptions[0].value;
			}
			this.showConnect = true;
		},
		async submitConnect() {
			const f = this.connectForm;
			if (!f.provider || !f.token || !f.serve_as_model) {
				toast.error('Provider, API key, and Serve-as-model are required');
				return;
			}
			this.connecting = true;
			try {
				await call('sanad_ai_control_center.api.connect_account', {
					provider: f.provider,
					token: f.token,
					account_label: f.account_label || f.provider,
					serve_as_model: f.serve_as_model,
					weight: f.weight || 1,
					monthly_budget: f.monthly_budget || null,
				});
				toast.success('Provider connected to the gateway pool');
				this.showConnect = false;
				this.load();
			} catch (e) {
				toast.error(e.messages?.[0] || 'Could not connect the provider');
			}
			this.connecting = false;
		},
		// get_accounts_overview shape: { groups: [{ model, accounts: [{ account_label, provider,
		//   serve_as_model, spend_to_date, region, connected }] }] }
		// Flatten each group's accounts into provider rows, carrying the group's model/tier.
		mapProviders(data) {
			const groups = (data && data.groups) || [];
			const rows = [];
			groups.forEach((grp) => {
				const accounts = grp.accounts || [];
				if (accounts.length === 0) {
					rows.push({
						provider: grp.model || '-',
						tier: grp.tier || grp.model || '-',
						region: grp.region || '-',
						cost: grp.cost || 0,
						connected: false,
					});
					return;
				}
				accounts.forEach((acc) => {
					rows.push({
						// account_label is the friendly name ('Anthropic (Claude)'); provider is the short key.
						provider: acc.account_label || acc.provider || grp.model || '-',
						// Tier = the model this account serves as ('smart'/'fast'/'cheap').
						tier: acc.serve_as_model || acc.tier || grp.tier || grp.model || '-',
						region: acc.region || '-',
						// Real spend field is spend_to_date.
						cost: acc.spend_to_date != null ? acc.spend_to_date : acc.cost != null ? acc.cost : 0,
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
		fmtNum(n) {
			return Number(n || 0).toLocaleString('en-US');
		},
		toggleGroup(client) {
			// Reassign so Vue 2/3 reliably tracks the new key.
			this.expanded = { ...this.expanded, [client]: !this.expanded[client] };
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
