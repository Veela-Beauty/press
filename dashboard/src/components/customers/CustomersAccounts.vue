<template>
	<div>
		<!-- DETAIL view -->
		<CustomerDetail v-if="selected" :customer="selected" :company="company" @back="selected = ''" />

		<!-- LIST view -->
		<div v-else class="space-y-3">
			<div class="flex flex-wrap items-center gap-2">
				<select v-model="company" class="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm" @change="loadCustomers">
					<option :value="''">All companies</option>
					<option v-for="c in companies" :key="c" :value="c">{{ c }}</option>
				</select>
				<div class="relative min-w-[200px] flex-1">
					<lucide-search class="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-gray-400" />
					<input
						v-model="search"
						type="text"
						placeholder="Search customer…"
						class="w-full rounded-md border border-gray-300 py-1.5 pl-8 pr-3 text-sm"
						@keyup.enter="loadCustomers"
					/>
				</div>
				<Button label="Search" @click="loadCustomers" />
			</div>

			<div class="rounded-lg border border-gray-200 bg-white">
				<div class="flex items-center justify-between border-b border-gray-100 px-4 py-2.5">
					<p class="text-xs font-semibold uppercase tracking-wide text-gray-400">
						Customers <span v-if="!listLoading">· {{ customers.length }}</span>
					</p>
				</div>
				<div v-if="listLoading" class="py-12 text-center text-sm text-gray-400">Loading…</div>
				<div v-else-if="!customers.length" class="py-12 text-center text-sm text-gray-400">No customers match.</div>
				<div v-else class="divide-y divide-gray-50">
					<button
						v-for="c in customers"
						:key="c.customer"
						class="flex w-full items-center gap-3 px-4 py-2.5 text-left transition hover:bg-gray-50"
						@click="selected = c.customer"
					>
						<div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-xs font-bold text-gray-600">
							{{ initials(c) }}
						</div>
						<div class="min-w-0 flex-1">
							<p class="truncate text-sm font-medium text-gray-800">{{ c.customer_name || c.customer }}</p>
							<p class="truncate text-xs text-gray-400">{{ (c.companies || []).join(' · ') || 'no company yet' }}</p>
						</div>
						<span class="shrink-0 rounded-md bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500">
							{{ c.sites }} site{{ c.sites === 1 ? '' : 's' }}
						</span>
						<lucide-chevron-right class="h-4 w-4 shrink-0 text-gray-300" />
					</button>
				</div>
			</div>
		</div>
	</div>
</template>

<script>
import { Button } from 'frappe-ui';
import { toast } from 'vue-sonner';
import CustomerDetail from './CustomerDetail.vue';
import { listCompanies, listCustomers } from './customersApi.js';

export default {
	name: 'CustomersAccounts',
	components: { Button, CustomerDetail },
	data() {
		return {
			companies: [],
			company: '',
			search: '',
			customers: [],
			listLoading: false,
			selected: '',
		};
	},
	async mounted() {
		try {
			this.companies = (await listCompanies()) || [];
		} catch (e) {
			/* non-fatal: filter just shows "All" */
		}
		this.loadCustomers();
	},
	methods: {
		async loadCustomers() {
			this.selected = '';
			this.listLoading = true;
			try {
				this.customers = (await listCustomers(this.company, this.search)) || [];
			} catch (e) {
				toast.error('Failed to load customers');
				this.customers = [];
			}
			this.listLoading = false;
		},
		initials(c) {
			const n = (c.customer_name || c.customer || '?').trim();
			return n.split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase() || '?';
		},
	},
};
</script>
