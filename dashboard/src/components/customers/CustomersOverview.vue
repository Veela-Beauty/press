<template>
	<div class="space-y-4">
		<div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
			<StatCard label="Customers" color="info" :number="counts.total_customers" subline="in the hub" />
			<StatCard label="Sites" color="good" :number="counts.total_sites" subline="hosted + mapped" />
			<StatCard label="Companies" color="info" :number="(counts.companies || []).length" subline="selling entities" />
		</div>

		<div class="rounded-lg border border-gray-200 bg-white">
			<div class="border-b border-gray-100 px-4 py-3">
				<p class="text-sm font-semibold">How this maps</p>
			</div>
			<div class="space-y-2 px-4 py-3">
				<div class="flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 p-3">
					<lucide-layout-dashboard class="mt-0.5 h-4 w-4 shrink-0 text-blue-500" />
					<div>
						<p class="text-sm font-semibold text-gray-800">Each customer maps to sites, apps, a plan and payment</p>
						<p class="text-xs text-gray-500">Open the Accounts tab to see a customer's sites, per-app tiers, hosting usage and billing.</p>
					</div>
				</div>
				<div v-if="error" class="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3">
					<lucide-triangle-alert class="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
					<p class="text-xs text-red-600">{{ error }}</p>
				</div>
			</div>
		</div>
	</div>
</template>

<script>
import { toast } from 'vue-sonner';
import StatCard from '../_shared/StatCard.vue';
import { overview } from './customersApi.js';

export default {
	name: 'CustomersOverview',
	components: { StatCard },
	data() {
		return {
			loading: false,
			error: '',
			counts: { total_customers: 0, total_sites: 0, companies: [] },
		};
	},
	mounted() {
		this.load();
	},
	methods: {
		async load() {
			this.loading = true;
			this.error = '';
			try {
				this.counts = (await overview()) || this.counts;
			} catch (e) {
				this.error = e?.messages?.[0] || 'Failed to load customer overview.';
				toast.error('Failed to load customer overview');
			}
			this.loading = false;
		},
	},
};
</script>
