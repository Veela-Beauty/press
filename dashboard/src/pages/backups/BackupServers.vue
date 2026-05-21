<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[{ label: 'Daman Backup Servers', route: '/backups/backup-servers' }]"
				/>
			</Header>
		</div>
		<div class="p-5">
			<!-- Summary Cards — shared style via StatCard -->
			<div class="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-4">
				<StatCard label="Total Servers" :number="stats.total || 0" />
				<StatCard label="Enabled" :number="stats.enabled || 0" color="good" />
				<StatCard label="Connected" :number="stats.connected || 0" color="info" />
				<StatCard label="Disconnected" :number="stats.disconnected || 0" color="bad" />
			</div>

			<ObjectList ref="serverList" :options="listOptions" />
		</div>

		<!-- Server Detail Dialog -->
		<Dialog v-model="detailDialogOpen" :options="{ title: selectedServer?.server_name || 'Server Details', size: 'xl' }">
			<template #body-content>
				<div v-if="selectedServer" class="space-y-4">
					<!-- Identity -->
					<div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
						<div>
							<div class="text-xs text-gray-500">Server Name</div>
							<div class="text-sm font-medium">{{ selectedServer.server_name || '-' }}</div>
						</div>
						<div>
							<div class="text-xs text-gray-500">Server Type</div>
							<div class="text-sm font-medium">{{ selectedServer.server_type || '-' }}</div>
						</div>
						<div>
							<div class="text-xs text-gray-500">Connection Status</div>
							<Badge :label="selectedServer.connection_status || 'Unknown'" />
						</div>
						<div>
							<div class="text-xs text-gray-500">Enabled</div>
							<div class="text-sm font-medium">{{ selectedServer.enabled ? 'Yes' : 'No' }}</div>
						</div>
					</div>

					<!-- Connection Details -->
					<div class="rounded border p-3">
						<div class="mb-2 text-sm font-medium text-gray-700">Connection</div>
						<div class="grid grid-cols-2 gap-3 sm:grid-cols-4 text-sm">
							<div>
								<div class="text-xs text-gray-500">Host</div>
								<div class="font-mono">{{ selectedServer.host || '-' }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Port</div>
								<div>{{ selectedServer.port || '-' }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">SSH User</div>
								<div>{{ selectedServer.ssh_user || '-' }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Connection Type</div>
								<div>{{ selectedServer.connection_type || '-' }}</div>
							</div>
						</div>
					</div>

					<!-- Storage & Type -->
					<div class="rounded border p-3">
						<div class="mb-2 text-sm font-medium text-gray-700">Storage</div>
						<div class="grid grid-cols-2 gap-3 sm:grid-cols-4 text-sm">
							<div>
								<div class="text-xs text-gray-500">Storage Type</div>
								<div>{{ selectedServer.storage_type || '-' }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Quota</div>
								<div>{{ selectedServer.size_quota_gb ? `${selectedServer.size_quota_gb} GB` : '-' }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Used</div>
								<div>{{ selectedServer.used_space_gb ? `${selectedServer.used_space_gb} GB` : '-' }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Available</div>
								<div>{{ selectedServer.available_space_gb ? `${selectedServer.available_space_gb} GB` : '-' }}</div>
							</div>
						</div>
						<!-- Storage bar -->
						<div v-if="selectedServer.storage_usage_percent" class="mt-3">
							<div class="mb-1 flex justify-between text-xs text-gray-500">
								<span>Storage Usage</span>
								<span>{{ Math.round(selectedServer.storage_usage_percent) }}%</span>
							</div>
							<div class="h-2.5 w-full overflow-hidden rounded-full bg-gray-200">
								<div
									class="h-full rounded-full transition-all"
									:class="selectedServer.storage_usage_percent > 90 ? 'bg-red-500' : selectedServer.storage_usage_percent > 70 ? 'bg-yellow-500' : 'bg-green-500'"
									:style="{ width: `${selectedServer.storage_usage_percent}%` }"
								></div>
							</div>
						</div>
					</div>

					<!-- Ownership -->
					<div class="rounded border p-3">
						<div class="mb-2 text-sm font-medium text-gray-700">Ownership</div>
						<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 text-sm">
							<div>
								<div class="text-xs text-gray-500">Client</div>
								<div>{{ selectedServer.client || '-' }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Location</div>
								<div>{{ selectedServer.server_location || '-' }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Total Backups</div>
								<div class="font-medium">{{ selectedServer.total_backups || 0 }}</div>
							</div>
						</div>
					</div>

					<!-- Activity -->
					<div class="rounded border p-3">
						<div class="mb-2 text-sm font-medium text-gray-700">Activity</div>
						<div class="grid grid-cols-2 gap-3 text-sm">
							<div>
								<div class="text-xs text-gray-500">Last Connection Check</div>
								<div>{{ formatDetailDate(selectedServer.last_check_on) }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Last Used On</div>
								<div>{{ formatDetailDate(selectedServer.last_used_on) }}</div>
							</div>
						</div>
					</div>
				</div>
			</template>
			<template #actions>
				<Button @click="detailDialogOpen = false">Close</Button>
			</template>
		</Dialog>
	</div>
</template>

<script>
import ObjectList from '../../components/ObjectList.vue';
import { Button, Dialog, Badge, createResource } from 'frappe-ui';
import { date } from '../../utils/format';
import StatCard from '../../components/_shared/StatCard.vue';

export default {
	name: 'BackupServers',
	components: { ObjectList, Button, Dialog, Badge, StatCard },
	data() {
		return {
			stats: {},
			detailDialogOpen: false,
			selectedServer: null,
		};
	},
	mounted() {
		this.fetchStats();
	},
	methods: {
		formatDetailDate(value) {
			if (!value) return '-';
			return date(value, 'llll');
		},
		fetchStats() {
			if (!this._statsResource) {
				this._statsResource = createResource({
					url: 'frappe.client.get_list',
					onSuccess: (result) => {
						const servers = result || [];
						this.stats = {
							total: servers.length,
							enabled: servers.filter((s) => s.enabled).length,
							connected: servers.filter((s) => s.connection_status === 'Connected').length,
							disconnected: servers.filter((s) => s.connection_status === 'Disconnected').length,
						};
					},
				});
			}
			this._statsResource.submit({
				doctype: 'Backup Server',
				fields: ['name', 'enabled', 'connection_status'],
				limit_page_length: 0,
			});
		},
	},
	computed: {
		listOptions() {
			return {
				doctype: 'Backup Server',
				orderBy: 'modified desc',
				fields: [
					'name', 'server_name', 'server_type', 'host', 'port',
					'storage_type', 'connection_type', 'connection_status', 'enabled',
					'ssh_user', 'client', 'server_location',
					'size_quota_gb', 'available_space_gb', 'used_space_gb',
					'storage_usage_percent', 'total_backups',
					'last_check_on', 'last_used_on',
				],
				columns: [
					{ label: 'Server Name', fieldname: 'server_name', width: 1 },
					{ label: 'Host', fieldname: 'host', width: 0.8 },
					{ label: 'Type', fieldname: 'server_type', width: '120px', align: 'center' },
					{ label: 'Storage', fieldname: 'storage_type', width: '120px', align: 'center' },
					{
						label: 'Status',
						fieldname: 'connection_status',
						width: '120px',
						align: 'center',
						type: 'Badge',
					},
					{
						label: 'Usage',
						fieldname: 'storage_usage_percent',
						width: '100px',
						align: 'center',
						format: (value) => value ? `${Math.round(value)}%` : '-',
					},
					{
						label: 'Enabled',
						fieldname: 'enabled',
						width: '80px',
						type: 'Icon',
						Icon: (value) => value ? 'check' : '',
					},
				],
				onRowClick: (row) => {
					this.selectedServer = row;
					this.detailDialogOpen = true;
				},
				filterControls: () => [
					{
						type: 'select',
						label: 'Type',
						fieldname: 'server_type',
						options: ['', 'Source', 'Destination', 'Both'],
					},
					{
						type: 'select',
						label: 'Status',
						fieldname: 'connection_status',
						options: ['', 'Connected', 'Disconnected', 'Unknown'],
					},
					{
						type: 'checkbox',
						label: 'Enabled Only',
						fieldname: 'enabled',
					},
				],
			};
		},
	},
};
</script>
