<template>
	<div class="space-y-4">
		<!-- KPI cards - shared StatCard, same as AdminPanel teams tab -->
		<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
			<StatCard label="Active" color="good" :number="counts.active" :subline="`across ${counts.sites} sites`" />
			<StatCard label="In Grace" color="warn" :number="counts.grace_lapsed" subline="renew soon" />
			<StatCard label="Lapsed / Revoked" color="bad" :number="counts.grace_lapsed" subline="features locked" />
			<StatCard label="Sites" color="info" :number="counts.sites" subline="distinct node-locks" />
		</div>

		<!-- Heartbeat alerts -->
		<div class="rounded-lg border border-gray-200 bg-white">
			<div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
				<p class="text-sm font-semibold">Heartbeat alerts</p>
				<Badge v-if="alerts.length" :label="`${alerts.length} over-deploy`" theme="red" />
			</div>
			<div class="px-4 py-3">
				<div v-if="loading" class="py-6 text-center text-sm text-gray-400">Loading…</div>
				<div v-else-if="error" class="py-6 text-center text-sm text-red-500">{{ error }}</div>
				<div v-else-if="!alerts.length" class="py-6 text-center text-sm text-gray-400">
					No heartbeat alerts. Every key is on one site.
				</div>
				<div v-else class="space-y-2">
					<div
						v-for="(a, i) in alerts"
						:key="i"
						class="flex items-start gap-3 rounded-lg border p-3"
						:class="a.level === 'bad' ? 'border-red-200 bg-red-50' : 'border-yellow-200 bg-yellow-50'"
					>
						<lucide-triangle-alert class="mt-0.5 h-4 w-4 shrink-0" :class="a.level === 'bad' ? 'text-red-500' : 'text-yellow-500'" />
						<div class="min-w-0 flex-1">
							<p class="text-sm font-semibold text-gray-800">{{ a.title }}</p>
							<p class="text-xs text-gray-500">{{ a.detail }}</p>
						</div>
						<span class="font-mono text-[11px] text-gray-400">{{ a.license_key }}</span>
					</div>
				</div>
			</div>
		</div>

		<!-- Static lifecycle notes -->
		<div class="rounded-lg border border-gray-200 bg-white">
			<div class="border-b border-gray-100 px-4 py-3">
				<p class="text-sm font-semibold">Recent activity</p>
			</div>
			<div class="space-y-2 px-4 py-3">
				<div class="flex items-start gap-3 rounded-lg border border-green-200 bg-green-50 p-3">
					<lucide-circle-check class="mt-0.5 h-4 w-4 shrink-0 text-green-500" />
					<div>
						<p class="text-sm font-semibold text-gray-800">License lifecycle is tracked live</p>
						<p class="text-xs text-gray-500">Issue, renew and revoke from the Licenses tab; readers reflect the master license doctype.</p>
					</div>
				</div>
				<div class="flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 p-3">
					<lucide-download class="mt-0.5 h-4 w-4 shrink-0 text-blue-500" />
					<div>
						<p class="text-sm font-semibold text-gray-800">Offline files available</p>
						<p class="text-xs text-gray-500">Generate an Ed25519-signed token for air-gapped client sites on the Offline tab.</p>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script>
import { Badge } from 'frappe-ui';
import { toast } from 'vue-sonner';
import StatCard from '../_shared/StatCard.vue';
import { overview } from './tesseraApi.js';

export default {
	name: 'TesseraOverview',
	components: { StatCard, Badge },
	data() {
		return {
			loading: false,
			error: '',
			counts: { active: 0, grace_lapsed: 0, sites: 0 },
			alerts: [],
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
				const data = await overview();
				this.counts = data?.counts || { active: 0, grace_lapsed: 0, sites: 0 };
				this.alerts = data?.alerts || [];
			} catch (e) {
				this.error = e?.messages?.[0] || 'Failed to load overview.';
				toast.error('Failed to load Tessera overview');
			}
			this.loading = false;
		},
	},
};
</script>
