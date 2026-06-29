<template>
	<div class="space-y-4">
		<button class="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800" @click="$emit('back')">
			<lucide-arrow-left class="h-4 w-4" /> All customers
		</button>

		<div v-if="loading" class="py-16 text-center text-sm text-gray-400">Loading account…</div>
		<div v-else-if="error" class="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">{{ error }}</div>

		<template v-else-if="account">
			<!-- Header -->
			<div class="flex flex-wrap items-center gap-4">
				<div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-gray-900 text-base font-bold text-white">
					{{ initials }}
				</div>
				<div class="min-w-0">
					<p class="truncate text-xl font-bold text-gray-900">{{ account.customer_name || account.customer }}</p>
					<div class="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-gray-500">
						<span>{{ account.customer }}</span>
						<span class="h-1.5 w-1.5 rounded-full bg-green-500"></span><span>Active</span>
						<Badge v-if="planLabel" :label="planLabel" theme="purple" />
						<Badge v-if="account.support_plan" :label="account.support_plan.plan_name" theme="gray" />
					</div>
				</div>
				<div class="ml-auto text-right">
					<p class="text-[11px] uppercase tracking-wide text-gray-400">Outstanding</p>
					<p class="text-lg font-bold" :class="outstanding > 0 ? 'text-red-600' : 'text-green-600'">{{ fmtMoney(outstanding) }}</p>
				</div>
			</div>

			<!-- Attention banner -->
			<div v-if="attention.length" class="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
				<lucide-triangle-alert class="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
				<div class="text-sm text-red-700">
					<b>{{ attention.length }} {{ attention.length === 1 ? 'site needs' : 'sites need' }} attention.</b>
					<span v-for="(a, i) in attention" :key="i"> {{ a.site }} — {{ a.reason }}.</span>
					Upgrade the hosting plan to restore headroom.
				</div>
			</div>

			<!-- Quick facts -->
			<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
				<StatCard label="Sites" color="info" :number="(account.sites || []).length" subline="hosted" />
				<StatCard label="Apps" color="good" :number="appCount" subline="entitlements" />
				<StatCard label="Attention" :color="attention.length ? 'bad' : 'good'" :number="attention.length" subline="over limit" />
				<StatCard label="Support" color="info" :number="account.support_plan ? 1 : 0"
					:subline="account.support_plan ? account.support_plan.plan_name : 'no plan'" />
			</div>

			<!-- Per-site: hosting meters + apps -->
			<div v-if="!(account.sites || []).length" class="rounded-lg border border-gray-200 bg-white py-10 text-center text-sm text-gray-400">
				No sites mapped for this customer yet.
			</div>
			<div v-for="site in account.sites" :key="site.site_url" class="rounded-lg border border-gray-200 bg-white">
				<div class="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 px-4 py-3">
					<div class="flex items-center gap-2">
						<lucide-server class="h-4 w-4 text-gray-400" />
						<span class="text-sm font-semibold text-gray-800">{{ site.site_url }}</span>
					</div>
					<Badge :label="site.status || 'Unknown'" :theme="site.status === 'Active' ? 'green' : 'gray'" />
				</div>

				<!-- meters -->
				<div class="grid gap-4 px-4 py-3 sm:grid-cols-2">
					<div v-for="kind in ['db', 'storage']" :key="kind"
						class="rounded-lg border p-3" :class="isOver(site.usage, kind) ? 'border-red-200 bg-red-50' : 'border-gray-100'">
						<div class="mb-1.5 flex items-center justify-between">
							<span class="flex items-center gap-1.5 text-xs font-medium text-gray-500">
								<lucide-database v-if="kind === 'db'" class="h-3.5 w-3.5" />
								<lucide-hard-drive v-else class="h-3.5 w-3.5" />
								{{ kind === 'db' ? 'Database' : 'Storage' }}
							</span>
							<Badge :label="pctLabel(site.usage, kind)" :theme="meterTheme(site.usage, kind)" />
						</div>
						<p class="mb-1.5 text-sm font-bold" :class="isOver(site.usage, kind) ? 'text-red-600' : 'text-gray-900'">
							{{ usedLabel(site.usage, kind) }}
						</p>
						<div class="h-1.5 overflow-hidden rounded-full bg-gray-100">
							<div class="h-full rounded-full" :class="barColor(site.usage, kind)" :style="{ width: barWidth(site.usage, kind) }"></div>
						</div>
					</div>
				</div>

				<!-- apps on this site -->
				<div v-if="(site.apps || []).length" class="border-t border-gray-100 px-4 py-2">
					<table class="w-full">
						<thead>
							<tr class="text-left text-[11px] uppercase tracking-wide text-gray-400">
								<th class="py-1.5 font-medium">App</th>
								<th class="py-1.5 font-medium">Tier</th>
								<th class="py-1.5 font-medium">Status</th>
								<th class="py-1.5 font-medium">Seats</th>
								<th class="py-1.5 font-medium">Renews</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="(a, i) in site.apps" :key="i" class="border-t border-gray-50">
								<td class="py-2">
									<div class="flex items-center gap-2">
										<span class="flex h-7 w-7 items-center justify-center rounded-md text-[10px] font-bold text-white" :class="appColor(a.app)">
											{{ appInitials(a.app) }}
										</span>
										<span class="text-sm text-gray-800">{{ a.app }}</span>
									</div>
								</td>
								<td class="py-2"><Badge :label="a.tier || 'Basic'" theme="purple" /></td>
								<td class="py-2"><Badge :label="a.state" :theme="stateTheme(a.state)" /></td>
								<td class="py-2 text-sm text-gray-500">{{ a.seats || '—' }}</td>
								<td class="py-2 text-sm text-gray-400">{{ a.renews || '—' }}</td>
							</tr>
						</tbody>
					</table>
				</div>
				<p v-if="site.usage && site.usage.synced_on" class="px-4 pb-2 text-[10px] text-gray-300">
					usage synced {{ site.usage.synced_on }}
				</p>
			</div>

			<!-- Billing + Support -->
			<div class="grid gap-4 sm:grid-cols-2">
				<div class="rounded-lg border border-gray-200 bg-white p-4">
					<p class="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
						<lucide-credit-card class="h-4 w-4" /> Billing
					</p>
					<div class="flex justify-between border-b border-gray-50 py-2 text-sm">
						<span class="text-gray-500">Outstanding</span>
						<span class="font-semibold" :class="outstanding > 0 ? 'text-red-600' : 'text-gray-900'">{{ fmtMoney(outstanding) }}</span>
					</div>
					<div class="flex justify-between py-2 text-sm">
						<span class="text-gray-500">Next invoice</span>
						<span class="font-semibold text-gray-900">{{ (account.billing && account.billing.next_invoice) || '—' }}</span>
					</div>
				</div>
				<div class="rounded-lg border border-gray-200 bg-white p-4">
					<p class="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
						<lucide-life-buoy class="h-4 w-4" /> Support &amp; SLA
					</p>
					<template v-if="account.support_plan">
						<Badge :label="account.support_plan.plan_name" theme="purple" />
						<div class="mt-2 space-y-1 text-sm text-gray-600">
							<p v-if="account.support_plan.response_sla_hours" class="flex items-center gap-2">
								<lucide-clock class="h-3.5 w-3.5 text-green-500" /> {{ account.support_plan.response_sla_hours }}-hour first response
							</p>
							<p v-if="account.support_plan.uptime_sla" class="flex items-center gap-2">
								<lucide-circle-check class="h-3.5 w-3.5 text-green-500" /> {{ account.support_plan.uptime_sla }} uptime
							</p>
							<p v-if="account.support_plan.channels" class="flex items-center gap-2">
								<lucide-message-circle class="h-3.5 w-3.5 text-green-500" /> {{ account.support_plan.channels }}
							</p>
						</div>
					</template>
					<p v-else class="text-sm text-gray-400">No support plan on file.</p>
				</div>
			</div>
		</template>
	</div>
</template>

<script>
import { Badge } from 'frappe-ui';
import { toast } from 'vue-sonner';
import StatCard from '../_shared/StatCard.vue';
import { getCustomerAccount, stateTheme, fmtMoney } from './customersApi.js';

const APP_COLORS = ['bg-sky-500', 'bg-violet-500', 'bg-amber-500', 'bg-emerald-500', 'bg-rose-500', 'bg-indigo-500'];

export default {
	name: 'CustomerDetail',
	components: { Badge, StatCard },
	props: {
		customer: { type: String, required: true },
		company: { type: String, default: '' },
	},
	emits: ['back'],
	data() {
		return { loading: false, error: '', account: null };
	},
	computed: {
		initials() {
			const n = (this.account?.customer_name || this.account?.customer || '?').trim();
			return n.split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase() || '?';
		},
		outstanding() {
			return (this.account?.billing && this.account.billing.outstanding) || 0;
		},
		attention() {
			return this.account?.needs_attention || [];
		},
		appCount() {
			return (this.account?.sites || []).reduce((n, s) => n + (s.apps || []).length, 0);
		},
		planLabel() {
			const subs = this.account?.subscriptions || [];
			for (const s of subs) for (const p of s.plans || []) if (p.tier) return p.tier + ' plan';
			return '';
		},
	},
	watch: {
		customer: 'load',
	},
	mounted() {
		this.load();
	},
	methods: {
		stateTheme,
		fmtMoney,
		async load() {
			this.loading = true;
			this.error = '';
			this.account = null;
			try {
				this.account = await getCustomerAccount(this.customer, this.company);
			} catch (e) {
				this.error = e?.messages?.[0] || 'Failed to load account.';
				toast.error('Failed to load account');
			}
			this.loading = false;
		},
		isOver(u, kind) {
			return !!(u && u[`${kind === 'db' ? 'db' : 'storage'}_over_limit`]);
		},
		_pct(u, kind) {
			return (u && u[`${kind}_pct`]) || 0;
		},
		barWidth(u, kind) {
			return Math.min(100, Math.max(0, this._pct(u, kind))) + '%';
		},
		barColor(u, kind) {
			const p = this._pct(u, kind);
			if (p >= 100) return 'bg-red-500';
			if (p >= 80) return 'bg-yellow-500';
			return 'bg-green-500';
		},
		meterTheme(u, kind) {
			const p = this._pct(u, kind);
			if (p >= 100) return 'red';
			if (p >= 80) return 'orange';
			return 'green';
		},
		pctLabel(u, kind) {
			const p = this._pct(u, kind);
			return this.isOver(u, kind) ? `${p}% over` : `${p}%`;
		},
		usedLabel(u, kind) {
			if (!u) return '—';
			const used = u[`${kind}_used_gb`] || 0;
			const limit = u[`${kind}_limit_gb`] || 0;
			if (!limit) return `${used} GB · no limit set`;
			return `${used} GB of ${limit} GB`;
		},
		appInitials(app) {
			const parts = String(app || '?').replace(/[_-]/g, ' ').split(/\s+/).filter(Boolean);
			return ((parts[0]?.[0] || '') + (parts[1]?.[0] || parts[0]?.[1] || '')).toUpperCase() || '?';
		},
		appColor(app) {
			let h = 0;
			for (const c of String(app || '')) h = (h + c.charCodeAt(0)) % APP_COLORS.length;
			return APP_COLORS[h];
		},
	},
};
</script>
