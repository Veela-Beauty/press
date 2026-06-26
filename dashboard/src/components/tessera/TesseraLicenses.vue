<template>
	<div class="space-y-3">
		<!-- Filter chips + Issue button -->
		<div class="flex items-center gap-2">
			<Button
				v-for="f in FILTERS"
				:key="f.key"
				size="sm"
				:variant="filter === f.key ? 'solid' : 'outline'"
				@click="filter = f.key"
			>
				{{ f.label }} ({{ countFor(f.key) }})
			</Button>
			<span class="flex-1"></span>
			<Button variant="solid" @click="showIssue = true">
				<template #prefix><lucide-plus class="h-4 w-4" /></template>
				Issue
			</Button>
		</div>

		<!-- Licenses table grouped by site -->
		<div class="rounded-lg border border-gray-200 bg-white">
			<div v-if="loading" class="py-8 text-center text-sm text-gray-400">Loading…</div>
			<div v-else-if="error" class="py-8 text-center text-sm text-red-500">{{ error }}</div>
			<div v-else-if="!groups.length" class="py-8 text-center text-sm text-gray-400">
				No licenses match this filter.
			</div>
			<table v-else class="w-full text-sm">
				<thead class="border-b border-gray-200 bg-gray-50 text-xs uppercase text-gray-500">
					<tr>
						<th class="px-4 py-2 text-left">Customer / Company</th>
						<th class="px-4 py-2 text-left">App</th>
						<th class="px-4 py-2 text-left">Tier</th>
						<th class="px-4 py-2 text-left">Seats</th>
						<th class="px-4 py-2 text-left">Status</th>
						<th class="px-4 py-2 text-left">Expires</th>
						<th class="px-4 py-2"></th>
					</tr>
				</thead>
				<tbody>
					<template v-for="g in groups" :key="g.site">
						<tr class="border-b border-gray-100 bg-gray-50/60">
							<td colspan="7" class="px-4 py-2">
								<span class="inline-flex items-center gap-1.5 text-xs font-semibold text-gray-700">
									<lucide-building-2 class="h-3.5 w-3.5 text-gray-400" />
									{{ g.site }}
									<span class="font-medium text-gray-400">
										· {{ g.members.length }} {{ g.members.length === 1 ? 'license' : 'licenses' }}
									</span>
								</span>
							</td>
						</tr>
						<tr v-for="r in g.members" :key="r.name" class="border-b border-gray-50 last:border-0">
							<td class="px-4 py-2 pl-8">
								<Badge v-if="!r.company" label="site-wide" theme="gray" />
								<span v-else class="font-medium">{{ r.customer || r.company }}</span>
							</td>
							<td class="px-4 py-2">{{ r.app }}</td>
							<td class="px-4 py-2">
								<span class="rounded bg-gray-100 px-1.5 py-0.5 text-xs font-medium text-gray-600">{{ r.tier }}</span>
							</td>
							<td class="px-4 py-2 text-gray-500">{{ r.seats || '-' }}</td>
							<td class="px-4 py-2">
								<Badge :label="statusTheme(r.status).label" :theme="statusTheme(r.status).theme" />
							</td>
							<td class="px-4 py-2 text-gray-500">{{ fmtDate(r.expires_on) }}</td>
							<td class="px-4 py-2 text-right">
								<Button
									v-if="r.status !== 'Revoked'"
									size="sm"
									theme="red"
									variant="outline"
									@click="onRevoke(r)"
								>
									Revoke
								</Button>
							</td>
						</tr>
					</template>
				</tbody>
			</table>
		</div>

		<TesseraIssueDialog v-model="showIssue" @issued="load" />
	</div>
</template>

<script>
import { Button, Badge } from 'frappe-ui';
import { toast } from 'vue-sonner';
import TesseraIssueDialog from './TesseraIssueDialog.vue';
import { listLicenses, revokeLicense, statusTheme, fmtDate, groupBySite } from './tesseraApi.js';

const FILTERS = [
	{ key: 'all', label: 'All', match: () => true },
	{ key: 'active', label: 'Active', match: (r) => r.status === 'Active' },
	{ key: 'grace', label: 'Grace', match: (r) => r.status === 'Suspended' },
	{ key: 'lapsed', label: 'Lapsed', match: (r) => ['Expired', 'Revoked'].includes(r.status) },
];

export default {
	name: 'TesseraLicenses',
	components: { Button, Badge, TesseraIssueDialog },
	setup() {
		return { statusTheme, fmtDate };
	},
	data() {
		return {
			FILTERS,
			loading: false,
			error: '',
			filter: 'all',
			rows: [],
			showIssue: false,
		};
	},
	computed: {
		filtered() {
			const m = FILTERS.find((f) => f.key === this.filter)?.match || (() => true);
			return this.rows.filter(m);
		},
		groups() {
			return groupBySite(this.filtered);
		},
	},
	mounted() {
		this.load();
	},
	methods: {
		countFor(key) {
			const m = FILTERS.find((f) => f.key === key)?.match || (() => true);
			return this.rows.filter(m).length;
		},
		async load() {
			this.loading = true;
			this.error = '';
			try {
				this.rows = (await listLicenses()) || [];
			} catch (e) {
				this.error = e?.messages?.[0] || 'Failed to load licenses.';
				toast.error('Failed to load licenses');
			}
			this.loading = false;
		},
		async onRevoke(r) {
			if (!confirm(`Revoke the license for ${r.customer || r.company || r.site_url}?`)) return;
			try {
				await revokeLicense(r.license_key);
				toast.success('License revoked');
				await this.load();
			} catch (e) {
				toast.error(e?.messages?.[0] || 'Revoke failed');
			}
		},
	},
};
</script>
