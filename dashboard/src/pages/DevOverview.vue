<template>
	<div>
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs :items="[{ label: 'Dev Overview', route: '/dev-overview' }]" />
				<template #actions>
					<Button
						variant="outline"
						:loading="$resources.benches.loading"
						@click="reload()"
					>
						Refresh
					</Button>
				</template>
			</Header>
		</div>

		<!-- Summary cards -->
		<div class="mx-5 mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
			<div class="rounded-lg border p-4 text-center">
				<div class="text-2xl font-bold">{{ totalBenches }}</div>
				<div class="text-sm text-gray-500">Total Benches</div>
			</div>
			<div class="rounded-lg border border-purple-200 bg-purple-50 p-4 text-center">
				<div class="text-2xl font-bold text-purple-700">{{ devBenches }}</div>
				<div class="text-sm text-purple-600">Dev Benches</div>
			</div>
			<div class="rounded-lg border border-green-200 bg-green-50 p-4 text-center">
				<div class="text-2xl font-bold text-green-700">{{ activeSites }}</div>
				<div class="text-sm text-green-600">Active Sites</div>
			</div>
			<div class="rounded-lg border border-red-200 bg-red-50 p-4 text-center">
				<div class="text-2xl font-bold text-red-700">{{ sitesWithErrors }}</div>
				<div class="text-sm text-red-600">Sites with Errors</div>
			</div>
		</div>

		<div class="mt-4">
			<ObjectList :options="listOptions" />
		</div>
	</div>
</template>

<script lang="jsx">
import { Breadcrumbs, Button, Tooltip, createResource } from 'frappe-ui';
import { defineAsyncComponent, h } from 'vue';
import { toast } from 'vue-sonner';
import Badge from '@/components/global/Badge.vue';
import Header from '@/components/Header.vue';
import ObjectList from '@/components/ObjectList.vue';
import ActionButton from '@/components/ActionButton.vue';
import { icon, confirmDialog } from '@/utils/components';

export default {
	name: 'DevOverview',
	components: { Header, Breadcrumbs, Button, ObjectList },

	data() {
		return {
			// site name → { schedulerStatus, migrationStatus, recentErrors }
			siteHealth: {},
		};
	},

	resources: {
		benches() {
			return {
				type: 'list',
				doctype: 'Bench',
				fields: [
					'name',
					'status',
					'is_development_bench',
					'group',
					'group.title as group_title',
					'server',
					'server.title as server_title',
					'cluster.title as cluster_title',
				],
				order_by: 'is_development_bench desc, name asc',
				pageLength: 100,
				auto: true,
				onSuccess: () => {
					this.$resources.sites.fetch();
				},
			};
		},
		sites() {
			return {
				type: 'list',
				doctype: 'Site',
				fields: ['name', 'status', 'bench', 'host_name', 'is_development_site'],
				filters: { skip_team_filter_for_system_user_and_support_agent: true },
				order_by: 'bench asc, name asc',
				pageLength: 999,
				auto: false,
				onSuccess: (data) => {
					(data || []).forEach((site) => this.loadSiteHealth(site.name));
				},
			};
		},
	},

	computed: {
		totalBenches() {
			return (this.$resources.benches.data || []).length;
		},
		devBenches() {
			return (this.$resources.benches.data || []).filter((b) => b.is_development_bench).length;
		},
		activeSites() {
			return (this.$resources.sites.data || []).filter((s) => s.status === 'Active').length;
		},
		sitesWithErrors() {
			return Object.values(this.siteHealth).filter((h) => h.errors?.count > 0).length;
		},

		listOptions() {
			const vm = this;
			return {
				list: this.$resources.sites,
				groupHeader: ({ group: bench }) => {
					if (!bench?.status) return null;
					return (
						<div class="flex items-center gap-3 py-1">
							<a
								class="text-base font-medium leading-6 text-gray-900 hover:underline cursor-pointer"
								href={`/dashboard/benches/${bench.name}`}
							>
								{bench.name}
							</a>
							{bench.is_development_bench && (
								<Badge label="DEV" theme="purple" size="sm" />
							)}
							{bench.status !== 'Active' && (
								<Badge label={bench.status} size="sm" />
							)}
							{bench.server_title && (
								<span class="text-sm text-gray-500">
									{bench.server_title || bench.server}
								</span>
							)}
							<div class="ml-auto flex items-center gap-2">
								<ActionButton
									options={vm.benchActions(bench)}
									label="Actions"
								/>
							</div>
						</div>
					);
				},
				transform(data) {
					return vm.groupSitesByBench(data);
				},
				emptyStateMessage: 'No sites found',
				filterControls() {
					return [
						{
							type: 'select',
							label: 'Status',
							fieldname: 'status',
							options: ['', 'Active', 'Inactive', 'Broken', 'Suspended', 'Pending'],
						},
						{
							type: 'link',
							label: 'Server',
							fieldname: 'server',
							options: { doctype: 'Server' },
						},
						{
							type: 'link',
							label: 'Release Group',
							fieldname: 'group',
							options: { doctype: 'Release Group' },
						},
					];
				},
				columns: [
					{
						label: 'Site',
						fieldname: 'name',
						class: 'font-medium',
						format(value, row) {
							return row.host_name || value;
						},
						link: (value) => `/sites/${value}/overview`,
					},
					{
						label: 'Status',
						fieldname: 'status',
						type: 'Badge',
						width: '120px',
					},
					{
						label: 'Dev',
						fieldname: 'is_development_site',
						type: 'Component',
						width: '60px',
						component({ row }) {
							if (!row.is_development_site) return null;
							return h(Badge, { label: 'DEV', theme: 'purple', size: 'sm' });
						},
					},
					{
						label: 'Scheduler',
						fieldname: 'name',
						type: 'Component',
						width: '100px',
						component({ row }) {
							const health = vm.siteHealth[row.name];
							if (!health?.scheduler) return h('span', { class: 'text-gray-300 text-xs' }, '—');
							const on = health.scheduler.enabled;
							return h('span', { class: 'inline-flex items-center gap-1 text-xs' }, [
								h('span', {
									class: `h-2 w-2 rounded-full ${on ? 'bg-green-500' : 'bg-red-500'}`,
								}),
								on ? 'ON' : 'OFF',
							]);
						},
					},
					{
						label: 'Last Migration',
						fieldname: 'name',
						type: 'Component',
						width: '140px',
						component({ row }) {
							const health = vm.siteHealth[row.name];
							if (!health?.migration?.last_action) return h('span', { class: 'text-gray-300 text-xs' }, '—');
							return h('span', { class: 'text-xs text-gray-500' }, [
								health.migration.last_action,
								' ',
								h('span', { class: 'text-gray-400' }, vm.formatDate(health.migration.last_run)),
							]);
						},
					},
					{
						label: 'Errors',
						fieldname: 'name',
						type: 'Component',
						width: '80px',
						component({ row }) {
							const health = vm.siteHealth[row.name];
							if (!health?.errors) return h('span', { class: 'text-gray-300 text-xs' }, '—');
							if (health.errors.count === 0) return h('span', { class: 'text-xs text-gray-400' }, 'None');
							return h('span', {
								class: 'inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700',
							}, `${health.errors.count} error${health.errors.count !== 1 ? 's' : ''}`);
						},
					},
				],
			};
		},
	},

	methods: {
		reload() {
			this.$resources.benches.reload();
		},

		groupSitesByBench(data) {
			const benches = this.$resources.benches.data;
			if (!benches) return [];
			return benches.map((bench) => ({
				...bench,
				group: bench.name,
				rows: (data || []).filter((s) => s.bench === bench.name),
				collapsed: false,
			}));
		},

		runDocMethod(dt, dn, method, args = {}) {
			const res = createResource({ url: 'press.api.client.run_doc_method' });
			return res.submit({ dt, dn, method, ...args });
		},

		loadSiteHealth(siteName) {
			const set = (key, val) => {
				this.siteHealth = {
					...this.siteHealth,
					[siteName]: { ...(this.siteHealth[siteName] || {}), [key]: val },
				};
			};
			this.runDocMethod('Site', siteName, 'get_scheduler_status')
				.then((r) => set('scheduler', r))
				.catch(() => set('scheduler', { enabled: true }));
			this.runDocMethod('Site', siteName, 'get_migration_status')
				.then((r) => set('migration', r))
				.catch(() => set('migration', null));
			this.runDocMethod('Site', siteName, 'get_recent_errors')
				.then((r) => set('errors', r))
				.catch(() => set('errors', { count: 0, errors: [] }));
		},

		benchActions(bench) {
			const vm = this;
			return [
				{
					label: bench.is_development_bench ? 'Unset Dev Bench' : 'Mark Dev Bench',
					icon: icon('code'),
					onClick() {
						const enabling = !bench.is_development_bench;
						vm.runDocMethod('Bench', bench.name, 'set_development_bench', {
							enable: enabling ? 1 : 0,
						})
							.then(() => {
								toast.success(enabling ? 'Marked as dev bench' : 'Removed dev bench flag');
								vm.$resources.benches.reload();
							})
							.catch((e) => toast.error(e.messages?.join(', ') || 'Failed'));
					},
				},
				{
					label: 'Restart Bench',
					icon: icon('refresh-cw'),
					condition: () => bench.status === 'Active',
					onClick() {
						confirmDialog({
							title: 'Restart Bench',
							message: `Are you sure you want to restart <b>${bench.name}</b>? Running processes will be interrupted.`,
							onSuccess: ({ hide }) => {
								return vm.runDocMethod('Bench', bench.name, 'restart_bench')
									.then(() => {
										toast.success(`Bench ${bench.name} restarted`);
										hide();
									})
									.catch((e) => toast.error(e.messages?.join(', ') || 'Failed to restart'));
							},
						});
					},
				},
				{
					label: 'Open in VS Code',
					icon: icon('code'),
					condition: () => bench.is_development_bench,
					onClick() {
						window.open(
							`vscode://vscode-remote/ssh-remote+press-ctrl/home/frappe/benches/${bench.name}/apps`,
							'_blank',
						);
					},
				},
				{
					label: 'View in Desk',
					icon: icon('external-link'),
					onClick() {
						window.open(
							`${window.location.protocol}//${window.location.host}/app/bench/${bench.name}`,
							'_blank',
						);
					},
				},
			].filter((a) => (a.condition ? a.condition() : true));
		},

		formatDate(dateStr) {
			if (!dateStr) return '';
			try {
				const diff = Math.floor((Date.now() - new Date(dateStr)) / 1000);
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
