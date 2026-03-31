<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs :items="[{ label: 'Dev Overview', route: '/dev-overview' }]" />
				<template #actions>
					<Button
						variant="outline"
						:loading="$resources.benches.loading"
						@click="$resources.benches.reload()"
					>
						Refresh
					</Button>
				</template>
			</Header>
		</div>

		<div class="p-5 space-y-6">
			<!-- Summary cards -->
			<div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
				<div class="rounded-lg border p-4 text-center">
					<div class="text-2xl font-bold">{{ totalBenches }}</div>
					<div class="text-sm text-gray-500">Total Benches</div>
				</div>
				<div class="rounded-lg border p-4 text-center border-purple-200 bg-purple-50">
					<div class="text-2xl font-bold text-purple-700">{{ devBenches }}</div>
					<div class="text-sm text-purple-600">Dev Benches</div>
				</div>
				<div class="rounded-lg border p-4 text-center border-green-200 bg-green-50">
					<div class="text-2xl font-bold text-green-700">{{ activeSites }}</div>
					<div class="text-sm text-green-600">Active Sites</div>
				</div>
				<div class="rounded-lg border p-4 text-center border-red-200 bg-red-50">
					<div class="text-2xl font-bold text-red-700">{{ sitesWithErrors }}</div>
					<div class="text-sm text-red-600">Sites with Errors</div>
				</div>
			</div>

			<!-- Loading state -->
			<div v-if="$resources.benches.loading" class="py-12 text-center text-gray-400">
				Loading benches…
			</div>

			<!-- Bench rows -->
			<div v-else class="space-y-3">
				<div
					v-for="bench in enrichedBenches"
					:key="bench.name"
					class="rounded-lg border bg-white"
					:class="bench.is_development_bench ? 'border-l-4 border-l-purple-500' : ''"
				>
					<!-- Bench header -->
					<div class="flex items-center justify-between px-4 py-3">
						<div class="flex items-center gap-3 min-w-0">
							<span class="font-semibold text-sm text-gray-800 truncate max-w-[260px]">
								{{ bench.name }}
							</span>
							<Badge
								v-if="bench.is_development_bench"
								label="DEV"
								theme="purple"
								size="sm"
							/>
							<Badge
								:label="bench.status"
								:theme="benchStatusTheme(bench.status)"
								size="sm"
							/>
						</div>
						<div class="flex items-center gap-2 shrink-0">
							<!-- Dev bench toggle -->
							<Button
								size="sm"
								variant="outline"
								:loading="bench._togglingDev"
								@click="toggleDevBench(bench)"
							>
								{{ bench.is_development_bench ? 'Unset Dev' : 'Mark Dev' }}
							</Button>
							<!-- Restart bench -->
							<Button
								size="sm"
								variant="outline"
								:loading="bench._restarting"
								@click="restartBench(bench)"
							>
								Restart
							</Button>
							<!-- VS Code (dev benches only) -->
							<a
								v-if="bench.is_development_bench"
								:href="`vscode://vscode-remote/ssh-remote+press-ctrl/home/frappe/benches/${bench.name}/apps`"
								target="_blank"
								class="inline-flex items-center gap-1 rounded border px-2 py-1 text-xs hover:bg-gray-50"
								title="Open in VS Code"
							>
								<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
									<path d="M23.15 2.587L18.21.21a1.494 1.494 0 0 0-1.705.29l-9.46 8.63-4.12-3.128a.999.999 0 0 0-1.276.057L.327 7.261A1 1 0 0 0 .326 8.74L3.899 12 .326 15.26a1 1 0 0 0 .001 1.479L1.65 17.94a.999.999 0 0 0 1.276.057l4.12-3.128 9.46 8.63a1.492 1.492 0 0 0 1.704.29l4.942-2.377A1.5 1.5 0 0 0 24 19.88V4.12a1.5 1.5 0 0 0-.85-1.533zm-5.146 14.861L10.826 12l7.178-5.448v10.896z"/>
								</svg>
								<span>VSCode</span>
							</a>
						</div>
					</div>

					<!-- Sites table -->
					<div v-if="bench.sites && bench.sites.length" class="border-t">
						<table class="w-full text-sm">
							<thead>
								<tr class="border-b bg-gray-50 text-left text-xs text-gray-500">
									<th class="px-4 py-2 font-medium">Site</th>
									<th class="px-4 py-2 font-medium">Status</th>
									<th class="px-4 py-2 font-medium">Scheduler</th>
									<th class="px-4 py-2 font-medium">Last Migration</th>
									<th class="px-4 py-2 font-medium">Errors</th>
								</tr>
							</thead>
							<tbody>
								<tr
									v-for="site in bench.sites"
									:key="site.name"
									class="border-b last:border-0 hover:bg-gray-50"
								>
									<td class="px-4 py-2">
										<router-link
											:to="`/sites/${site.name}/overview`"
											class="text-blue-600 hover:underline font-medium"
										>
											{{ site.name }}
										</router-link>
									</td>
									<td class="px-4 py-2">
										<Badge
											:label="site.status"
											:theme="siteStatusTheme(site.status)"
											size="sm"
										/>
									</td>
									<td class="px-4 py-2">
										<span
											v-if="site._schedulerStatus"
											class="inline-flex items-center gap-1 text-xs"
										>
											<span
												class="h-2 w-2 rounded-full"
												:class="site._schedulerStatus.enabled ? 'bg-green-500' : 'bg-red-500'"
											/>
											{{ site._schedulerStatus.enabled ? 'ON' : 'OFF' }}
										</span>
										<span v-else class="text-gray-300 text-xs">—</span>
									</td>
									<td class="px-4 py-2 text-xs text-gray-500">
										<template v-if="site._migrationStatus && site._migrationStatus.last_action">
											{{ site._migrationStatus.last_action }}
											<span class="text-gray-400 ml-1">{{ formatDate(site._migrationStatus.last_run) }}</span>
										</template>
										<span v-else class="text-gray-300">—</span>
									</td>
									<td class="px-4 py-2">
										<span
											v-if="site._recentErrors && site._recentErrors.count > 0"
											class="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700"
										>
											{{ site._recentErrors.count }} error{{ site._recentErrors.count !== 1 ? 's' : '' }}
										</span>
										<span v-else-if="site._recentErrors" class="text-xs text-gray-400">None</span>
										<span v-else class="text-gray-300 text-xs">—</span>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
					<div v-else class="border-t px-4 py-3 text-sm text-gray-400">
						No sites in this bench
					</div>
				</div>

				<div v-if="!enrichedBenches.length" class="py-12 text-center text-gray-400">
					No benches found
				</div>
			</div>
		</div>
	</div>
</template>

<script>
import { createResource } from 'frappe-ui';
import Badge from '@/components/global/Badge.vue';
import Header from '@/components/Header.vue';
import { Breadcrumbs, Button } from 'frappe-ui';
import { toast } from 'vue-sonner';

export default {
	name: 'DevOverview',
	components: { Badge, Header, Breadcrumbs, Button },

	data() {
		return {
			benchState: {},
		};
	},

	resources: {
		benches() {
			return {
				type: 'list',
				doctype: 'Bench',
				fields: ['name', 'status', 'is_development_bench', 'group', 'server'],
				order_by: 'is_development_bench desc, name asc',
				pageLength: 50,
				auto: true,
				onSuccess: (data) => {
					this.loadSitesForBenches(data);
				},
			};
		},
	},

	computed: {
		enrichedBenches() {
			return (this.$resources.benches.data || []).map((b) => ({
				...b,
				sites: this.benchState[b.name]?.sites || [],
				_togglingDev: this.benchState[b.name]?._togglingDev || false,
				_restarting: this.benchState[b.name]?._restarting || false,
			}));
		},
		totalBenches() {
			return (this.$resources.benches.data || []).length;
		},
		devBenches() {
			return (this.$resources.benches.data || []).filter((b) => b.is_development_bench).length;
		},
		activeSites() {
			return Object.values(this.benchState)
				.flatMap((b) => b.sites || [])
				.filter((s) => s.status === 'Active').length;
		},
		sitesWithErrors() {
			return Object.values(this.benchState)
				.flatMap((b) => b.sites || [])
				.filter((s) => s._recentErrors?.count > 0).length;
		},
	},

	methods: {
		setBenchState(benchName, patch) {
			this.benchState = {
				...this.benchState,
				[benchName]: { ...(this.benchState[benchName] || {}), ...patch },
			};
		},
		setSiteState(benchName, siteName, patch) {
			const sites = (this.benchState[benchName]?.sites || []).map((s) =>
				s.name === siteName ? { ...s, ...patch } : s,
			);
			this.setBenchState(benchName, { sites });
		},

		loadSitesForBenches(benches) {
			benches.forEach((bench) => {
				createResource({
					url: 'frappe.client.get_list',
					params: {
						doctype: 'Site',
						filters: [['bench', '=', bench.name]],
						fields: ['name', 'status', 'bench'],
						limit: 20,
					},
					auto: true,
					onSuccess: (sites) => {
						this.setBenchState(bench.name, { sites: sites || [] });
						(sites || []).forEach((site) => this.loadSiteHealth(bench.name, site.name));
					},
				});
			});
		},

		runDocMethod(dt, dn, method, args = {}) {
			const res = createResource({ url: 'press.api.client.run_doc_method' });
			return res.submit({ dt, dn, method, ...args });
		},

		loadSiteHealth(benchName, siteName) {
			this.runDocMethod('Site', siteName, 'get_scheduler_status')
				.then((r) => this.setSiteState(benchName, siteName, { _schedulerStatus: r }))
				.catch(() => this.setSiteState(benchName, siteName, { _schedulerStatus: { enabled: true } }));

			this.runDocMethod('Site', siteName, 'get_migration_status')
				.then((r) => this.setSiteState(benchName, siteName, { _migrationStatus: r }))
				.catch(() => this.setSiteState(benchName, siteName, { _migrationStatus: null }));

			this.runDocMethod('Site', siteName, 'get_recent_errors')
				.then((r) => this.setSiteState(benchName, siteName, { _recentErrors: r }))
				.catch(() => this.setSiteState(benchName, siteName, { _recentErrors: { count: 0, errors: [] } }));
		},

		toggleDevBench(bench) {
			this.setBenchState(bench.name, { _togglingDev: true });
			this.runDocMethod('Bench', bench.name, 'set_development_bench', {
				enable: bench.is_development_bench ? 0 : 1,
			})
				.then(() => {
					toast.success(bench.is_development_bench ? 'Bench set to production' : 'Bench marked as dev');
					this.$resources.benches.reload();
				})
				.catch((e) => toast.error(e.messages?.join(', ') || 'Failed'))
				.finally(() => this.setBenchState(bench.name, { _togglingDev: false }));
		},

		restartBench(bench) {
			this.setBenchState(bench.name, { _restarting: true });
			this.runDocMethod('Bench', bench.name, 'restart_bench')
				.then(() => toast.success(`Bench ${bench.name} restarted`))
				.catch((e) => toast.error(e.messages?.join(', ') || 'Failed to restart'))
				.finally(() => this.setBenchState(bench.name, { _restarting: false }));
		},

		benchStatusTheme(status) {
			const map = { Active: 'green', Broken: 'red', Archived: 'gray', Pending: 'yellow', Installing: 'blue' };
			return map[status] || 'gray';
		},
		siteStatusTheme(status) {
			const map = {
				Active: 'green',
				Inactive: 'gray',
				Broken: 'red',
				Pending: 'yellow',
				Suspended: 'orange',
				Updating: 'blue',
			};
			return map[status] || 'gray';
		},
		formatDate(dateStr) {
			if (!dateStr) return '';
			try {
				const d = new Date(dateStr);
				const diff = Math.floor((Date.now() - d) / 1000);
				if (diff < 60) return 'just now';
				if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
				if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
				return `${Math.floor(diff / 86400)}d ago`;
			} catch {
				return dateStr;
			}
		},
	},
};
</script>
