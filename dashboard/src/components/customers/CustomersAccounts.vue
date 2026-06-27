<template>
	<div class="space-y-3">
		<!-- Filters -->
		<div class="flex flex-wrap items-center gap-2">
			<select
				v-model="company"
				class="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm"
				@change="onFilter"
			>
				<option :value="''">All companies</option>
				<option v-for="c in companies" :key="c" :value="c">{{ c }}</option>
			</select>
			<input
				v-model="search"
				type="text"
				placeholder="Search customer…"
				class="min-w-[180px] flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm"
				@keyup.enter="loadCustomers"
			/>
			<Button label="Search" @click="loadCustomers" />
		</div>

		<div class="grid gap-4 lg:grid-cols-[320px_1fr]">
			<!-- LEFT: customer list -->
			<div class="rounded-lg border border-gray-200 bg-white">
				<div class="border-b border-gray-100 px-3 py-2 text-xs font-semibold uppercase text-gray-400">
					Customers ({{ customers.length }})
				</div>
				<div class="max-h-[60vh] overflow-y-auto">
					<div v-if="listLoading" class="py-6 text-center text-sm text-gray-400">Loading…</div>
					<div v-else-if="!customers.length" class="py-6 text-center text-sm text-gray-400">No customers.</div>
					<button
						v-for="c in customers"
						:key="c.customer"
						class="flex w-full items-center justify-between border-b border-gray-50 px-3 py-2 text-left hover:bg-gray-50"
						:class="selected === c.customer ? 'bg-blue-50' : ''"
						@click="openCustomer(c.customer)"
					>
						<div class="min-w-0">
							<p class="truncate text-sm font-medium text-gray-800">{{ c.customer_name || c.customer }}</p>
							<p class="truncate text-xs text-gray-400">{{ (c.companies || []).join(', ') || '—' }}</p>
						</div>
						<span class="ml-2 shrink-0 rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-500">
							{{ c.sites }} site{{ c.sites === 1 ? '' : 's' }}
						</span>
					</button>
				</div>
			</div>

			<!-- RIGHT: account detail -->
			<div class="rounded-lg border border-gray-200 bg-white">
				<div v-if="!selected" class="py-16 text-center text-sm text-gray-400">
					Select a customer to see apps, hosting and payment.
				</div>
				<div v-else-if="detailLoading" class="py-16 text-center text-sm text-gray-400">Loading account…</div>
				<div v-else-if="account" class="divide-y divide-gray-100">
					<!-- header + payment -->
					<div class="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
						<div>
							<p class="text-base font-semibold text-gray-900">{{ account.customer_name || account.customer }}</p>
							<p v-if="account.support_plan" class="mt-0.5 text-xs text-gray-500">
								Support: {{ account.support_plan.plan_name }}
								<span v-if="account.support_plan.response_sla_hours"> · {{ account.support_plan.response_sla_hours }}h SLA</span>
							</p>
						</div>
						<div class="text-right">
							<p class="text-xs text-gray-400">Outstanding</p>
							<p class="text-sm font-semibold" :class="outstanding > 0 ? 'text-red-600' : 'text-green-600'">
								{{ fmtMoney(outstanding) }}
							</p>
							<p v-if="account.billing && account.billing.next_invoice" class="text-[11px] text-gray-400">
								next {{ account.billing.next_invoice }}
							</p>
						</div>
					</div>

					<!-- needs attention -->
					<div v-if="(account.needs_attention || []).length" class="px-4 py-3">
						<div
							v-for="(na, i) in account.needs_attention"
							:key="i"
							class="mb-1 flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700"
						>
							<lucide-triangle-alert class="h-4 w-4 shrink-0" />
							<span>{{ na.site }} — {{ na.reason }}</span>
						</div>
					</div>

					<!-- sites -->
					<div v-if="!(account.sites || []).length" class="px-4 py-6 text-center text-sm text-gray-400">
						No sites mapped for this customer yet.
					</div>
					<div v-for="site in account.sites" :key="site.site_url" class="px-4 py-3">
						<div class="mb-2 flex items-center justify-between">
							<p class="truncate text-sm font-medium text-gray-800">{{ site.site_url }}</p>
							<Badge :label="site.status || 'Unknown'" :theme="site.status === 'Active' ? 'green' : 'gray'" />
						</div>

						<!-- apps -->
						<div v-if="(site.apps || []).length" class="mb-3 flex flex-wrap gap-1.5">
							<span
								v-for="(a, i) in site.apps"
								:key="i"
								class="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-gray-50 px-2 py-1 text-[11px]"
							>
								<span class="font-medium text-gray-700">{{ a.app }}</span>
								<Badge :label="a.tier || 'Basic'" theme="blue" />
								<Badge :label="a.state" :theme="stateTheme(a.state)" />
								<span v-if="a.seats" class="text-gray-400">{{ a.seats }} seats</span>
							</span>
						</div>

						<!-- hosting usage meters -->
						<div class="grid gap-2 sm:grid-cols-2">
							<div>
								<div class="mb-1 flex justify-between text-[11px] text-gray-500">
									<span>Database</span>
									<span :class="site.usage && site.usage.db_over_limit ? 'font-semibold text-red-600' : ''">
										{{ usageLabel(site.usage, 'db') }}
									</span>
								</div>
								<div class="h-1.5 overflow-hidden rounded-full bg-gray-100">
									<div class="h-full rounded-full" :class="meterColor(site.usage ? site.usage.db_pct : 0)"
										:style="{ width: barWidth(site.usage ? site.usage.db_pct : 0) }"></div>
								</div>
							</div>
							<div>
								<div class="mb-1 flex justify-between text-[11px] text-gray-500">
									<span>Storage</span>
									<span :class="site.usage && site.usage.storage_over_limit ? 'font-semibold text-red-600' : ''">
										{{ usageLabel(site.usage, 'storage') }}
									</span>
								</div>
								<div class="h-1.5 overflow-hidden rounded-full bg-gray-100">
									<div class="h-full rounded-full" :class="meterColor(site.usage ? site.usage.storage_pct : 0)"
										:style="{ width: barWidth(site.usage ? site.usage.storage_pct : 0) }"></div>
								</div>
							</div>
						</div>
						<p v-if="site.usage && site.usage.synced_on" class="mt-1 text-[10px] text-gray-300">
							usage synced {{ site.usage.synced_on }}
						</p>
					</div>
				</div>
				<div v-else class="py-16 text-center text-sm text-red-500">{{ error }}</div>
			</div>
		</div>
	</div>
</template>

<script>
import { Badge, Button } from 'frappe-ui';
import { toast } from 'vue-sonner';
import {
	listCompanies,
	listCustomers,
	getCustomerAccount,
	stateTheme,
	meterColor,
	fmtMoney,
} from './customersApi.js';

export default {
	name: 'CustomersAccounts',
	components: { Badge, Button },
	data() {
		return {
			companies: [],
			company: '',
			search: '',
			customers: [],
			listLoading: false,
			selected: '',
			account: null,
			detailLoading: false,
			error: '',
		};
	},
	computed: {
		outstanding() {
			return (this.account && this.account.billing && this.account.billing.outstanding) || 0;
		},
	},
	async mounted() {
		try {
			this.companies = (await listCompanies()) || [];
		} catch (e) {
			// non-fatal: filter just shows "All"
		}
		this.loadCustomers();
	},
	methods: {
		stateTheme,
		meterColor,
		fmtMoney,
		onFilter() {
			this.selected = '';
			this.account = null;
			this.loadCustomers();
		},
		async loadCustomers() {
			this.listLoading = true;
			try {
				this.customers = (await listCustomers(this.company, this.search)) || [];
			} catch (e) {
				toast.error('Failed to load customers');
				this.customers = [];
			}
			this.listLoading = false;
		},
		async openCustomer(customer) {
			this.selected = customer;
			this.detailLoading = true;
			this.error = '';
			this.account = null;
			try {
				this.account = await getCustomerAccount(customer, this.company);
			} catch (e) {
				this.error = e?.messages?.[0] || 'Failed to load account.';
				toast.error('Failed to load account');
			}
			this.detailLoading = false;
		},
		barWidth(pct) {
			return Math.min(100, Math.max(0, Number(pct) || 0)) + '%';
		},
		usageLabel(usage, kind) {
			if (!usage) return '—';
			const used = usage[`${kind}_used_gb`] || 0;
			const limit = usage[`${kind}_limit_gb`] || 0;
			const pct = usage[`${kind}_pct`] || 0;
			if (!limit) return `${used} GB · no limit`;
			return `${used} / ${limit} GB · ${pct}%`;
		},
	},
};
</script>
