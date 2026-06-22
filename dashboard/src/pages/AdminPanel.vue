<template>
	<div class="mx-auto max-w-7xl p-4">
		<div class="mb-4 flex items-center justify-between">
			<div>
				<p class="text-xs font-medium uppercase tracking-wide text-gray-400">{{ activeGroupLabel }}</p>
				<h1 class="text-xl font-bold text-gray-900">{{ activeTabLabel }}</h1>
			</div>
			<div class="flex gap-2">
				<Button v-if="activeMainTab === 'teams'" variant="solid" @click="showCreateTeam = true">
					<template #prefix><lucide-plus class="h-4 w-4" /></template>
					Create Team
				</Button>
				<Button @click="loadData" :loading="loading">
					<template #icon><lucide-refresh-ccw class="h-4 w-4" /></template>
				</Button>
			</div>
		</div>

		<!-- TAB: Teams (default) -->
		<template v-if="activeMainTab === 'teams'">
			<!-- Stats — shared style via StatCard component -->
			<div v-if="stats" class="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
				<StatCard label="Teams" :number="stats.total_teams" />
				<StatCard label="Sites" :number="stats.total_sites" />
				<StatCard label="Benches" :number="stats.total_benches" />
				<StatCard label="Monthly Cost" color="info">
					<template #number>&euro;{{ stats.total_cost }}</template>
				</StatCard>
				<StatCard
					label="Servers"
					:number="serverCosts.length"
					:subline="serverCosts.map(s => s.name.split('.')[0]).join(', ')"
					class="sm:col-span-2"
				/>
			</div>

			<!-- Server Costs -->
			<div class="mb-4 rounded-lg border border-gray-200 bg-white">
				<div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
					<p class="text-sm font-semibold">Server Costs</p>
				</div>
				<table class="w-full text-sm">
					<thead class="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
						<tr><th class="px-4 py-2 text-left">Server</th><th class="px-4 py-2 text-left">IP</th><th class="px-4 py-2 text-left">Plan</th><th class="px-4 py-2 text-right">Teams</th><th class="px-4 py-2 text-right">Sites</th><th class="px-4 py-2 text-right">Cost/mo</th></tr>
					</thead>
					<tbody>
						<tr v-for="s in serverCosts" :key="s.name" class="border-b border-gray-50 last:border-0">
							<td class="px-4 py-2 font-medium">{{ s.name.split('.')[0] }}</td>
							<td class="px-4 py-2 text-gray-500">{{ s.ip }}</td>
							<td class="px-4 py-2">{{ s.plan }}</td>
							<td class="px-4 py-2 text-right">{{ s.teams }}</td>
							<td class="px-4 py-2 text-right">{{ s.sites }}</td>
							<td class="px-4 py-2 text-right font-bold">&euro;{{ s.cost }}</td>
						</tr>
						<tr class="bg-gray-50 font-bold">
							<td class="px-4 py-2" colspan="5">Total</td>
							<td class="px-4 py-2 text-right text-blue-600">&euro;{{ stats?.total_cost }}</td>
						</tr>
					</tbody>
				</table>
			</div>

			<!-- Search -->
			<div class="mb-3 flex items-center gap-2">
				<input v-model="search" type="text" placeholder="Search teams..." class="max-w-sm rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none">
				<Button size="sm" :variant="filter === 'all' ? 'solid' : 'outline'" @click="filter = 'all'">All ({{ teams.length }})</Button>
				<Button size="sm" :variant="filter === 'active' ? 'solid' : 'outline'" theme="green" @click="filter = 'active'">Active ({{ teams.filter(t => t.enabled).length }})</Button>
				<Button size="sm" :variant="filter === 'blocked' ? 'solid' : 'outline'" theme="red" @click="filter = 'blocked'">Blocked ({{ teams.filter(t => !t.enabled).length }})</Button>
			</div>

			<!-- Teams Table -->
			<div class="rounded-lg border border-gray-200 bg-white overflow-hidden">
				<table class="w-full text-sm">
					<thead class="border-b border-gray-200 bg-gray-50 text-xs uppercase text-gray-500">
						<tr>
							<th class="w-8 px-3 py-2"></th>
							<th class="px-3 py-2 text-left">Team</th>
							<th class="px-3 py-2 text-left">Status</th>
							<th class="px-3 py-2 text-left">Members</th>
							<th class="px-3 py-2 text-left">Sites</th>
							<th class="px-3 py-2 text-left">Benches</th>
							<th class="px-3 py-2 text-right">Cost/mo</th>
							<th class="px-3 py-2 text-right">Actions</th>
						</tr>
					</thead>
					<tbody>
						<template v-for="team in filteredTeams" :key="team.name">
							<tr class="cursor-pointer border-b border-gray-100 hover:bg-gray-50" :class="{ 'bg-blue-50': expandedTeam === team.name }" @click="toggleExpand(team.name)">
								<td class="px-3 py-2.5"><lucide-chevron-right class="h-3.5 w-3.5 text-gray-400 transition-transform" :class="{ 'rotate-90': expandedTeam === team.name }" /></td>
								<td class="px-3 py-2.5">
									<div class="flex items-center gap-2">
										<div class="flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold text-white" :style="{ background: team.enabled ? '#2490ef' : '#8d99a6' }">{{ (team.user || '?')[0].toUpperCase() }}</div>
										<div><div class="font-medium">{{ team.user }}</div><div class="text-xs text-gray-400">{{ team.name }}</div></div>
									</div>
								</td>
								<td class="px-3 py-2.5"><Badge :label="team.enabled ? 'Active' : 'Blocked'" :theme="team.enabled ? 'green' : 'red'" /></td>
								<td class="px-3 py-2.5">{{ team.member_count }}</td>
								<td class="px-3 py-2.5">
									<div class="flex items-center gap-2">
										<div class="h-1.5 w-16 overflow-hidden rounded-full bg-gray-200"><div class="h-full rounded-full" :class="usageColor(team.site_count, team.max_sites)" :style="{ width: usagePct(team.site_count, team.max_sites) + '%' }"></div></div>
										<span class="text-xs text-gray-500">{{ team.site_count }}/{{ team.max_sites || '∞' }}</span>
									</div>
								</td>
								<td class="px-3 py-2.5">
									<div class="flex items-center gap-2">
										<div class="h-1.5 w-16 overflow-hidden rounded-full bg-gray-200"><div class="h-full rounded-full" :class="usageColor(team.bench_count, team.max_benches)" :style="{ width: usagePct(team.bench_count, team.max_benches) + '%' }"></div></div>
										<span class="text-xs text-gray-500">{{ team.bench_count }}/{{ team.max_benches || '∞' }}</span>
									</div>
								</td>
								<td class="px-3 py-2.5 text-right font-bold text-blue-600">&euro;{{ team.cost }}</td>
								<td class="px-3 py-2.5 text-right" @click.stop>
									<Button v-if="team.enabled" size="sm" theme="red" variant="outline" @click="blockTeam(team.name)">Block</Button>
									<Button v-else size="sm" theme="green" variant="outline" @click="unblockTeam(team.name)">Unblock</Button>
								</td>
							</tr>
							<!-- Expanded Detail -->
							<tr v-if="expandedTeam === team.name">
								<td colspan="8" class="border-b border-gray-200 bg-white p-0">
									<TeamDetail :team="team" :features="featureRegistry" @updated="loadData" />
								</td>
							</tr>
						</template>
					</tbody>
				</table>
			</div>
		</template>

		<!-- TAB: Servers (admin) -->
		<template v-if="activeMainTab === 'servers'">
			<ServerAdmin @updated="$refs.adminData?.fetch?.()" />
		</template>

		<!-- TAB: AI Governance -->
		<template v-if="activeMainTab === 'ai-governance'">
			<AiGovernance @edit-rules="goTab('policy')" />
		</template>

		<!-- TAB: Escalations -->
		<template v-if="activeMainTab === 'escalations'">
			<AiEscalations :is-team-leader="true" :is-admin="true" />
		</template>

		<!-- TAB: Usage & Cost -->
		<template v-if="activeMainTab === 'usage-cost'">
			<AiUsageCost />
		</template>

		<!-- TAB: Seats -->
		<template v-if="activeMainTab === 'seats'">
			<AiSeats />
		</template>

		<!-- TAB: Providers -->
		<template v-if="activeMainTab === 'providers'">
			<AiProviders />
		</template>

		<!-- TAB: Subscriptions -->
		<template v-if="activeMainTab === 'subscriptions'">
			<AiSubscriptions />
		</template>

		<!-- TAB: Buy seats -->
		<template v-if="activeMainTab === 'buy-seats'">
			<AiBuySeats />
		</template>


		<!-- TAB: Policy -->
		<template v-if="activeMainTab === 'security'">
			<ConfidentialSecurity />
		</template>

		<template v-if="activeMainTab === 'policy'">
			<AiPolicyGate @acknowledged="goTab('teams')" />
		</template>

		<!-- TAB: MCP -->
		<template v-if="activeMainTab === 'mcp'">
			<AdminPanelMcp />
		</template>

		<!-- Create Team Dialog -->
		<Dialog :options="{ title: 'Create New Team', size: 'md' }" v-model="showCreateTeam">
			<template #body-content>
				<div class="space-y-3">
					<FormControl label="Email" v-model="newTeam.email" placeholder="user@company.com" />
					<FormControl label="Full Name" v-model="newTeam.fullName" placeholder="John Doe" />
					<div class="grid grid-cols-3 gap-3">
						<FormControl label="Max Sites" type="number" v-model="newTeam.maxSites" />
						<FormControl label="Max Benches" type="number" v-model="newTeam.maxBenches" />
						<FormControl label="Max Disk (GB)" type="number" v-model="newTeam.maxDisk" />
					</div>
				</div>
			</template>
			<template #actions>
				<Button variant="solid" :loading="creatingTeam" @click="createTeam">Create Team</Button>
			</template>
		</Dialog>
	</div>
</template>

<script>
import { call } from 'frappe-ui';
import { toast } from 'vue-sonner';
import TeamDetail from '../components/admin/TeamDetail.vue';
import ServerAdmin from '../components/admin/ServerAdmin.vue';
import AiGovernance from '../components/admin/AiGovernance.vue';
import ConfidentialSecurity from '../components/admin/ConfidentialSecurity.vue';
import AiEscalations from '../components/admin/AiEscalations.vue';
import AiUsageCost from '../components/admin/AiUsageCost.vue';
import AiPolicyGate from '../components/admin/AiPolicyGate.vue';
import AiSeats from '../components/admin/AiSeats.vue';
import AiProviders from '../components/admin/AiProviders.vue';
import AiSubscriptions from '../components/admin/AiSubscriptions.vue';
import AiBuySeats from '../components/admin/AiBuySeats.vue';
import AdminPanelMcp from './admin/AdminPanelMcp.vue';
import { TAB_STRIP_BASE, tabClass } from '../components/_shared/tabClasses.js';
import StatCard from '../components/_shared/StatCard.vue';

const API = 'press.api.admin_panel';

export default {
	name: 'AdminPanel',
	components: { TeamDetail, ServerAdmin, AiGovernance, AiEscalations, AiUsageCost, AiPolicyGate, AdminPanelMcp, StatCard, ConfidentialSecurity, AiSeats, AiProviders, AiSubscriptions, AiBuySeats },
	setup() {
		// Expose shared tab constants to the template
		return { TAB_STRIP_BASE, tabClass };
	},
	data() {
		return {
			loading: false,
			teams: [],
			stats: null,
			serverCosts: [],
			featureRegistry: {},
			search: '',
			filter: 'all',
			expandedTeam: null,
			showCreateTeam: false,
			creatingTeam: false,
			newTeam: { email: '', fullName: '', maxSites: 0, maxBenches: 0, maxDisk: 0 },
			activeMainTab: 'teams',
			mainTabs: [
				{ id: 'teams', label: 'Teams', icon: 'fa fa-users' },
				{ id: 'servers', label: 'Servers', icon: 'fa fa-server' },
				{ id: 'ai-governance', label: 'AI Governance', icon: 'fa fa-robot', badge: '2', badgeColor: 'bg-red-500' },
				{ id: 'escalations', label: 'Escalations', icon: 'fa fa-exclamation-circle', badge: '1', badgeColor: 'bg-orange-500' },
				{ id: 'usage-cost', label: 'Usage & Cost', icon: 'fa fa-bar-chart' },
				{ id: 'seats', label: 'Seats', icon: 'fa fa-id-badge' },
				{ id: 'providers', label: 'Providers', icon: 'fa fa-plug' },
				{ id: 'subscriptions', label: 'Subscriptions', icon: 'fa fa-refresh' },
				{ id: 'buy-seats', label: 'Buy seats', icon: 'fa fa-shopping-cart' },
				{ id: 'policy', label: 'Policy', icon: 'fa fa-file-text-o' },
				{ id: 'mcp', label: 'MCP', icon: 'fa fa-key' },
				{ id: 'security', label: 'Security', icon: 'fa fa-lock' },
			],
		};
	},
	computed: {
		filteredTeams() {
			let list = this.teams;
			if (this.filter === 'active') list = list.filter(t => t.enabled);
			if (this.filter === 'blocked') list = list.filter(t => !t.enabled);
			if (this.search) {
				const q = this.search.toLowerCase();
				list = list.filter(t => t.user?.toLowerCase().includes(q) || t.name?.toLowerCase().includes(q));
			}
			return list;
		},
		// The sidebar group now drives navigation; the page heading reflects the active tab.
		activeTabLabel() {
			const t = this.mainTabs.find((x) => x.id === this.activeMainTab);
			return t ? t.label : 'Admin Panel';
		},
		activeGroupLabel() {
			const ai = ['ai-governance', 'usage-cost', 'seats', 'providers', 'subscriptions', 'escalations', 'buy-seats'];
			return ai.includes(this.activeMainTab) ? 'Sanad AI' : 'Admin';
		},
	},
	mounted() {
		this.activeMainTab = this.$route.params.tab || 'teams';
		this.loadData();
	},
	watch: {
		'$route.params.tab'(v) {
			if (v && v !== this.activeMainTab) this.activeMainTab = v;
		},
	},
	methods: {
		// Tab clicks deep-link to /admin/<id> so the sidebar group highlights the
		// active child. MCP has its own page/route. replace() keeps history clean.
		goTab(id) {
			if (id === 'mcp') {
				this.$router.push({ name: 'Admin Panel MCP' });
				return;
			}
			this.activeMainTab = id;
			if (this.$route.params.tab !== id) {
				this.$router.replace('/admin/' + id).catch(() => {});
			}
		},
		async loadData() {
			this.loading = true;
			try {
				const [data, features] = await Promise.all([
					call(`${API}.get_admin_data`),
					call(`${API}.get_feature_registry`),
				]);
				this.teams = data.teams;
				this.stats = data.stats;
				this.serverCosts = data.server_costs;
				this.featureRegistry = features;
			} catch (e) { toast.error('Failed to load admin data'); }
			this.loading = false;
		},
		toggleExpand(name) { this.expandedTeam = this.expandedTeam === name ? null : name; },
		usagePct(used, max) { return max > 0 ? Math.min(100, Math.round((used / max) * 100)) : 30; },
		usageColor(used, max) {
			if (!max) return 'bg-blue-400';
			const pct = used / max;
			if (pct >= 0.9) return 'bg-red-500';
			if (pct >= 0.7) return 'bg-yellow-500';
			return 'bg-green-500';
		},
		async blockTeam(name) {
			if (!confirm('Block this team? All sites will be suspended.')) return;
			await call(`${API}.toggle_team`, { team: name, action: 'block' });
			toast.success('Team blocked');
			this.loadData();
		},
		async unblockTeam(name) {
			await call(`${API}.toggle_team`, { team: name, action: 'unblock' });
			toast.success('Team unblocked');
			this.loadData();
		},
		async createTeam() {
			this.creatingTeam = true;
			try {
				await call(`${API}.create_team_from_admin`, {
					email: this.newTeam.email, full_name: this.newTeam.fullName,
					max_sites: this.newTeam.maxSites, max_benches: this.newTeam.maxBenches, max_disk_gb: this.newTeam.maxDisk,
				});
				toast.success('Team created');
				this.showCreateTeam = false;
				this.newTeam = { email: '', fullName: '', maxSites: 0, maxBenches: 0, maxDisk: 0 };
				this.loadData();
			} catch (e) { toast.error(e.messages?.[0] || 'Failed to create team'); }
			this.creatingTeam = false;
		},
	},
};
</script>
