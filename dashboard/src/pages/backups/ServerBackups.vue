<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[{ label: 'Server Backups', route: '/backups/servers' }]"
				/>
			</Header>
		</div>
		<div class="p-5">
			<div class="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-4">
				<div class="rounded-lg border bg-white p-4">
					<div class="text-sm text-gray-500">Total Clients</div>
					<div class="text-2xl font-semibold">{{ stats.total_clients || 0 }}</div>
				</div>
				<div class="rounded-lg border bg-white p-4">
					<div class="text-sm text-gray-500">Healthy</div>
					<div class="text-2xl font-semibold text-green-600">{{ stats.healthy || 0 }}</div>
				</div>
				<div class="rounded-lg border bg-white p-4">
					<div class="text-sm text-gray-500">Warning</div>
					<div class="text-2xl font-semibold text-orange-500">{{ stats.warning || 0 }}</div>
				</div>
				<div class="rounded-lg border bg-white p-4">
					<div class="text-sm text-gray-500">Critical</div>
					<div class="text-2xl font-semibold text-red-600">{{ stats.critical || 0 }}</div>
				</div>
			</div>
			<ObjectList :options="listOptions" />
		</div>
	</div>
</template>

<script>
import ObjectList from '../../components/ObjectList.vue';
import { createResource } from 'frappe-ui';
import { date } from '../../utils/format';

export default {
	name: 'ServerBackups',
	components: {
		ObjectList,
	},
	data() {
		return {
			stats: {},
		};
	},
	mounted() {
		this.fetchStats();
	},
	methods: {
		fetchStats() {
			createResource({
				url: 'frappe.client.get_count',
				params: { doctype: 'Backup Client' },
				auto: true,
				onSuccess: (count) => {
					this.stats.total_clients = count;
				},
			});
			createResource({
				url: 'frappe.client.get_count',
				params: { doctype: 'Backup Client', filters: { backup_backup_health_status: 'Healthy' } },
				auto: true,
				onSuccess: (count) => {
					this.stats.healthy = count;
				},
			});
			createResource({
				url: 'frappe.client.get_count',
				params: { doctype: 'Backup Client', filters: { backup_backup_health_status: 'Warning' } },
				auto: true,
				onSuccess: (count) => {
					this.stats.warning = count;
				},
			});
			createResource({
				url: 'frappe.client.get_count',
				params: { doctype: 'Backup Client', filters: { backup_backup_health_status: 'Critical' } },
				auto: true,
				onSuccess: (count) => {
					this.stats.critical = count;
				},
			});
		},
	},
	computed: {
		listOptions() {
			return {
				doctype: 'Backup Client',
				orderBy: 'modified desc',
				fields: [
					'name',
					'client_name',
					'backup_backup_health_status',
					'last_backup_on',
					'days_since_last_backup',
					'storage_usage_percent',
					'auto_backup_enabled_enabled',
				],
				columns: [
					{
						label: 'Client',
						fieldname: 'client_name',
						width: 1,
					},
					{
						label: 'Health',
						fieldname: 'backup_backup_health_status',
						width: '120px',
						align: 'center',
						type: 'Badge',
					},
					{
						label: 'Last Backup',
						fieldname: 'last_backup_on',
						width: 0.8,
						format(value) {
							return value ? date(value, 'llll') : 'Never';
						},
					},
					{
						label: 'Days Ago',
						fieldname: 'days_since_last_backup',
						width: '100px',
						align: 'center',
					},
					{
						label: 'Storage %',
						fieldname: 'storage_usage_percent',
						width: '100px',
						align: 'center',
						format(value) {
							return value ? Math.round(value) + '%' : '-';
						},
					},
					{
						label: 'Auto',
						fieldname: 'auto_backup_enabled_enabled',
						width: '80px',
						type: 'Icon',
						Icon(value) {
							return value ? 'check' : '';
						},
					},
				],
				filterControls() {
					return [
						{
							type: 'select',
							label: 'Health',
							fieldname: 'backup_backup_health_status',
							options: ['', 'Healthy', 'Warning', 'Critical', 'Unknown'],
						},
						{
							type: 'checkbox',
							label: 'Auto Backup',
							fieldname: 'auto_backup_enabled_enabled',
						},
					];
				},
			};
		},
	},
};
</script>
