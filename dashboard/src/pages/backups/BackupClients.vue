<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[
						{ label: 'Daman Backup', route: '/backups/overview' },
						{ label: 'Clients' },
					]"
				/>
			</Header>
		</div>
		<div class="p-5">
			<!-- Summary Cards -->
			<div class="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-4">
				<div class="rounded-lg border bg-white p-4">
					<div class="text-sm text-gray-500">{{ 'Total Clients' }}</div>
					<div class="text-2xl font-semibold">{{ stats.total || 0 }}</div>
				</div>
				<div class="rounded-lg border bg-white p-4">
					<div class="text-sm text-gray-500">{{ 'Healthy' }}</div>
					<div class="text-2xl font-semibold text-green-600">{{ stats.healthy || 0 }}</div>
				</div>
				<div class="rounded-lg border bg-white p-4">
					<div class="text-sm text-gray-500">{{ 'Warning' }}</div>
					<div class="text-2xl font-semibold text-yellow-600">{{ stats.warning || 0 }}</div>
				</div>
				<div class="rounded-lg border bg-white p-4">
					<div class="text-sm text-gray-500">{{ 'Critical' }}</div>
					<div class="text-2xl font-semibold text-red-600">{{ stats.critical || 0 }}</div>
				</div>
			</div>

			<ObjectList ref="clientList" :options="listOptions" />
		</div>
	</div>
</template>

<script>
import ObjectList from '../../components/ObjectList.vue';
import { Badge, createResource } from 'frappe-ui';
import { date } from '../../utils/format';

const BASE_API = 'daman_backup.daman_backup.press_api';

export default {
	name: 'BackupClients',
	components: { ObjectList, Badge },
	data() {
		return {
			stats: {},
			clients: [],
		};
	},
	mounted() {
		this.fetchClients();
	},
	created() {
		this._clientsResource = createResource({
			url: `${BASE_API}.get_clients_list`,
			onSuccess: (result) => {
				const list = Array.isArray(result) ? result : (result?.clients || []);
				this.clients = list;
				this.stats = {
					total: list.length,
					healthy: list.filter((c) => c.health === 'Healthy').length,
					warning: list.filter((c) => c.health === 'Warning').length,
					critical: list.filter((c) => c.health === 'Critical').length,
				};
			},
			onError: () => {
				this.fetchStatsFallback();
			},
		});
		this._statsFallbackResource = createResource({
			url: 'frappe.client.get_list',
			onSuccess: (result) => {
				const list = result || [];
				this.stats = {
					total: list.length,
					healthy: list.filter((c) => c.health_status === 'Healthy').length,
					warning: list.filter((c) => c.health_status === 'Warning').length,
					critical: list.filter((c) => c.health_status === 'Critical').length,
				};
			},
		});
	},
	methods: {
		fetchClients() {
			this._clientsResource.submit({});
		},
		fetchStatsFallback() {
			this._statsFallbackResource.submit({
				doctype: 'Backup Client',
				fields: ['name', 'client_name', 'status', 'health_status'],
				limit_page_length: 0,
			});
		},
		formatStorageBar(row) {
			if (!row.storage_used_gb && !row.storage_allowed_gb) return null;
			const used = parseFloat(row.storage_used_gb) || 0;
			const allowed = parseFloat(row.storage_allowed_gb) || 0;
			const pct = allowed > 0 ? Math.min((used / allowed) * 100, 100) : 0;
			return { used, allowed, pct };
		},
	},
	computed: {
		listOptions() {
			return {
				doctype: 'Backup Client',
				orderBy: 'modified desc',
				fields: [
					'name', 'client_name', 'status', 'health_status',
					'last_backup_date', 'days_since_backup',
					'storage_used_gb', 'storage_allowed_gb',
					'auto_backup_enabled',
				],
				columns: [
					{ label: 'Client Name', fieldname: 'client_name', width: 1 },
					{
						label: 'Status',
						fieldname: 'status',
						width: '120px',
						align: 'center',
						type: 'Badge',
					},
					{
						label: 'Health',
						fieldname: 'health_status',
						width: '120px',
						align: 'center',
						type: 'Badge',
					},
					{
						label: 'Last Backup',
						fieldname: 'last_backup_date',
						width: 0.8,
						format: (value) => value ? date(value, 'lll') : 'Never',
					},
					{
						label: 'Days Since',
						fieldname: 'days_since_backup',
						width: '100px',
						align: 'center',
						format: (value) => {
							if (value == null || value === '') return '-';
							return value;
						},
					},
					{
						label: 'Storage',
						fieldname: 'storage_used_gb',
						width: '160px',
						format: (value, row) => {
							const used = parseFloat(row?.storage_used_gb) || 0;
							const allowed = parseFloat(row?.storage_allowed_gb) || 0;
							if (!used && !allowed) return '-';
							return `${used.toFixed(1)} / ${allowed.toFixed(1)} GB`;
						},
					},
					{
						label: 'Auto Backup',
						fieldname: 'auto_backup_enabled',
						width: '100px',
						type: 'Icon',
						Icon: (value) => value ? 'check' : '',
					},
				],
				onRowClick: (row) => {
					this.$router.push(`/backups/clients/${row.name}`);
				},
				filterControls: () => [
					{
						type: 'select',
						label: 'Status',
						fieldname: 'status',
						options: ['', 'Active', 'Deactivate', 'Hold'],
					},
					{
						type: 'select',
						label: 'Health',
						fieldname: 'health_status',
						options: ['', 'Healthy', 'Warning', 'Critical', 'Unknown'],
					},
					{
						type: 'checkbox',
						label: 'Auto Backup Only',
						fieldname: 'auto_backup_enabled',
					},
				],
			};
		},
	},
};
</script>
