<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[{ label: 'Daman Backup Jobs', route: '/backups/servers' }]"
				/>
			</Header>
		</div>
		<div class="p-5">
			<!-- Summary Cards — shared style via StatCard -->
			<div class="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-4">
				<StatCard label="Total Jobs" :number="stats.total || 0" />
				<StatCard label="Enabled" :number="stats.enabled || 0" color="good" />
				<StatCard label="Scheduled" :number="stats.scheduled || 0" color="info" />
				<StatCard label="Last Failed" :number="stats.failed || 0" color="bad" />
			</div>

			<ObjectList ref="jobList" :options="listOptions" />
		</div>

		<!-- Output Dialog (archives / repo info) -->
		<Dialog v-model="outputDialogOpen" :options="{ title: outputTitle, size: 'lg' }">
			<template #body-content>
				<pre
					class="max-h-96 overflow-auto rounded bg-gray-900 p-4 text-xs text-green-400"
					style="white-space: pre-wrap; word-break: break-all;"
				>{{ outputContent }}</pre>
			</template>
			<template #actions>
				<Button @click="outputDialogOpen = false">Close</Button>
			</template>
		</Dialog>

		<!-- Job Detail Dialog (enriched 6-section layout) -->
		<Dialog
			v-model="detailDialogOpen"
			:options="{ title: selectedJob?.job_title || 'Job Details', size: '4xl' }"
		>
			<template #body-content>
				<div v-if="detailLoading" class="flex items-center justify-center py-12">
					<div class="text-sm text-gray-500">{{ 'Loading details...' }}</div>
				</div>
				<div v-else-if="selectedJob" class="max-h-[75vh] overflow-y-auto pr-1">

					<!-- Section 1: Identity -->
					<div class="mb-5">
						<div class="mb-3 border-b pb-2 text-sm font-semibold text-gray-800">
							{{ 'Identity' }}
						</div>
						<div class="grid grid-cols-1 gap-x-6 gap-y-0 sm:grid-cols-2">
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Job Title' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.job_title || '\u2014' }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Job Type' }}</span>
								<Badge
									:label="selectedJob.job_type || '\u2014'"
									variant="subtle"
									theme="blue"
								/>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Client' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.client || '\u2014' }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Priority' }}</span>
								<Badge
									:label="selectedJob.priority || '\u2014'"
									variant="subtle"
									:theme="priorityTheme(selectedJob.priority)"
								/>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Enabled' }}</span>
								<Badge
									:label="selectedJob.enabled ? 'Enabled' : 'Disabled'"
									variant="subtle"
									:theme="selectedJob.enabled ? 'green' : 'red'"
								/>
							</div>
							<div v-if="selectedJob.description" class="flex items-start justify-between py-1.5 sm:col-span-2">
								<span class="text-sm text-gray-600 shrink-0">{{ 'Description' }}</span>
								<span class="text-sm font-medium text-right ml-4 max-w-[65%]">{{ selectedJob.description }}</span>
							</div>
						</div>
					</div>

					<!-- Section 2: Source -->
					<div class="mb-5">
						<div class="mb-3 border-b pb-2 text-sm font-semibold text-gray-800">
							{{ 'Source' }}
						</div>
						<div class="grid grid-cols-1 gap-x-6 gap-y-0 sm:grid-cols-2">
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Source Server' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.source_server || '\u2014' }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Source Type' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.source_type || '\u2014' }}</span>
							</div>
							<div v-if="selectedJob.frappe_cloud_site_name" class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Frappe Cloud Site' }}</span>
								<span class="text-sm font-medium font-mono text-xs">{{ selectedJob.frappe_cloud_site_name }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'SSH User' }}</span>
								<span class="text-sm font-medium font-mono">{{ selectedJob.ssh_user || '\u2014' }}</span>
							</div>
							<div v-if="selectedJob.exclude_patterns" class="flex items-start justify-between py-1.5 sm:col-span-2">
								<span class="text-sm text-gray-600 shrink-0">{{ 'Exclude Patterns' }}</span>
								<span class="text-sm font-medium font-mono text-right ml-4 max-w-[65%] break-all">{{ selectedJob.exclude_patterns }}</span>
							</div>
						</div>
					</div>

					<!-- Section 3: Destination -->
					<div class="mb-5">
						<div class="mb-3 border-b pb-2 text-sm font-semibold text-gray-800">
							{{ 'Destination' }}
						</div>
						<div class="grid grid-cols-1 gap-x-6 gap-y-0 sm:grid-cols-2">
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Destination Server' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.destination_server || '\u2014' }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Destination Path' }}</span>
								<span class="text-sm font-medium font-mono text-xs break-all">{{ selectedJob.destination_path || '\u2014' }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Encryption' }}</span>
								<span class="flex items-center gap-1.5 text-sm font-medium">
									<span
										class="inline-flex h-4 w-4 items-center justify-center rounded-full text-xs text-white"
										:class="selectedJob.encryption_enabled ? 'bg-green-500' : 'bg-gray-300'"
									>{{ selectedJob.encryption_enabled ? '\u2713' : '\u2717' }}</span>
									{{ selectedJob.encryption_enabled ? 'Enabled' : 'Disabled' }}
								</span>
							</div>
							<div v-if="selectedJob.encryption_enabled" class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Passphrase Mode' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.passphrase_mode || '\u2014' }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Repo Initialized' }}</span>
								<span class="flex items-center gap-1.5 text-sm font-medium">
									<span
										class="inline-flex h-4 w-4 items-center justify-center rounded-full text-xs text-white"
										:class="selectedJob.repo_initialized ? 'bg-green-500' : 'bg-gray-300'"
									>{{ selectedJob.repo_initialized ? '\u2713' : '\u2717' }}</span>
									{{ selectedJob.repo_initialized ? 'Yes' : 'No' }}
								</span>
							</div>
						</div>
					</div>

					<!-- Section 4: Settings -->
					<div class="mb-5">
						<div class="mb-3 border-b pb-2 text-sm font-semibold text-gray-800">
							{{ 'Settings' }}
						</div>
						<div class="grid grid-cols-1 gap-x-6 gap-y-0 sm:grid-cols-2">
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Compression Level' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.compression_level || '\u2014' }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Retention Days' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.retention_days ?? '\u2014' }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'One File System' }}</span>
								<span class="flex items-center gap-1.5 text-sm font-medium">
									<span
										class="inline-flex h-4 w-4 items-center justify-center rounded-full text-xs text-white"
										:class="selectedJob.one_file_system ? 'bg-green-500' : 'bg-gray-300'"
									>{{ selectedJob.one_file_system ? '\u2713' : '\u2717' }}</span>
									{{ selectedJob.one_file_system ? 'Yes' : 'No' }}
								</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Exclude Caches' }}</span>
								<span class="flex items-center gap-1.5 text-sm font-medium">
									<span
										class="inline-flex h-4 w-4 items-center justify-center rounded-full text-xs text-white"
										:class="selectedJob.exclude_caches ? 'bg-green-500' : 'bg-gray-300'"
									>{{ selectedJob.exclude_caches ? '\u2713' : '\u2717' }}</span>
									{{ selectedJob.exclude_caches ? 'Yes' : 'No' }}
								</span>
							</div>
						</div>
					</div>

					<!-- Section 5: Schedule -->
					<div class="mb-5">
						<div class="mb-3 border-b pb-2 text-sm font-semibold text-gray-800">
							{{ 'Schedule' }}
						</div>
						<div class="grid grid-cols-1 gap-x-6 gap-y-0 sm:grid-cols-2">
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Schedule Enabled' }}</span>
								<Badge
									:label="selectedJob.schedule_enabled ? 'Active' : 'Inactive'"
									variant="subtle"
									:theme="selectedJob.schedule_enabled ? 'green' : 'gray'"
								/>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Schedule Type' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.schedule_type || '\u2014' }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Schedule Time / Cron' }}</span>
								<span class="text-sm font-medium font-mono">{{ selectedJob.schedule_cron || selectedJob.schedule_time || '\u2014' }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Next Scheduled Run' }}</span>
								<span class="text-sm font-medium">{{ formatDetailDate(selectedJob.next_scheduled_run) }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Schedule Paused' }}</span>
								<Badge
									v-if="selectedJob.schedule_paused"
									:label="'Paused'"
									variant="subtle"
									theme="orange"
								/>
								<span v-else class="text-sm font-medium text-gray-400">\u2014</span>
							</div>
						</div>
					</div>

					<!-- Section 6: Statistics -->
					<div class="mb-5">
						<div class="mb-3 border-b pb-2 text-sm font-semibold text-gray-800">
							{{ 'Statistics' }}
						</div>

						<!-- KPI cards row -->
						<div class="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
							<div class="rounded-lg border bg-gray-50 px-3 py-2.5 text-center">
								<div class="text-xs text-gray-500">{{ 'Total Runs' }}</div>
								<div class="mt-0.5 text-lg font-semibold">{{ selectedJob.total_runs || 0 }}</div>
							</div>
							<div class="rounded-lg border bg-gray-50 px-3 py-2.5 text-center">
								<div class="text-xs text-gray-500">{{ 'Success' }}</div>
								<div class="mt-0.5 text-lg font-semibold text-green-600">{{ selectedJob.total_success || 0 }}</div>
							</div>
							<div class="rounded-lg border bg-gray-50 px-3 py-2.5 text-center">
								<div class="text-xs text-gray-500">{{ 'Failed' }}</div>
								<div class="mt-0.5 text-lg font-semibold text-red-600">{{ selectedJob.total_failed || 0 }}</div>
							</div>
							<div class="rounded-lg border bg-gray-50 px-3 py-2.5 text-center">
								<div class="text-xs text-gray-500">{{ 'Success Rate' }}</div>
								<div
									class="mt-0.5 text-lg font-semibold"
									:class="successRateColorClass(selectedJob.success_rate)"
								>
									{{ selectedJob.success_rate != null ? `${Math.round(selectedJob.success_rate)}%` : '\u2014' }}
								</div>
							</div>
						</div>

						<!-- Last run detail rows -->
						<div class="grid grid-cols-1 gap-x-6 gap-y-0 sm:grid-cols-2">
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Last Run On' }}</span>
								<span class="text-sm font-medium">{{ formatDetailDate(selectedJob.last_run_on) }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Last Run Status' }}</span>
								<Badge
									v-if="selectedJob.last_run_status"
									:label="selectedJob.last_run_status"
									variant="subtle"
									:theme="lastRunStatusTheme(selectedJob.last_run_status)"
								/>
								<span v-else class="text-sm font-medium text-gray-400">{{ 'Never' }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Last Run Duration' }}</span>
								<span class="text-sm font-medium">{{ formatDuration(selectedJob.last_run_duration) }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Last Backup Size' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.last_backup_size_mb ? `${selectedJob.last_backup_size_mb} MB` : '\u2014' }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Avg Backup Size' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.avg_backup_size_mb ? `${selectedJob.avg_backup_size_mb} MB` : '\u2014' }}</span>
							</div>
						</div>
					</div>

					<!-- Recent History (from API) -->
					<div v-if="jobHistory?.queue_jobs?.length" class="mb-2">
						<div class="mb-3 border-b pb-2 text-sm font-semibold text-gray-800">
							{{ 'Recent Runs (Last 10)' }}
						</div>
						<div class="overflow-x-auto">
							<table class="w-full text-sm">
								<thead>
									<tr class="border-b text-left text-gray-500">
										<th class="py-1.5 pr-3 text-xs">{{ 'Job ID' }}</th>
										<th class="py-1.5 pr-3 text-xs">{{ 'Status' }}</th>
										<th class="py-1.5 pr-3 text-xs">{{ 'Started' }}</th>
										<th class="py-1.5 pr-3 text-xs">{{ 'Duration' }}</th>
										<th class="py-1.5 text-xs">{{ 'Error' }}</th>
									</tr>
								</thead>
								<tbody>
									<tr v-for="qj in jobHistory.queue_jobs" :key="qj.name" class="border-b last:border-0">
										<td class="py-1.5 pr-3 font-mono text-xs">{{ qj.job_id }}</td>
										<td class="py-1.5 pr-3"><Badge :label="qj.status" size="sm" /></td>
										<td class="py-1.5 pr-3 text-xs">{{ formatDetailDate(qj.started_at) }}</td>
										<td class="py-1.5 pr-3 text-xs">{{ formatDuration(qj.duration_seconds) }}</td>
										<td class="py-1.5 text-xs text-red-500 truncate max-w-[200px]">{{ qj.error_message || '\u2014' }}</td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>

				</div>
				<div v-else class="py-8 text-center text-sm text-gray-400">
					{{ 'No details available' }}
				</div>
			</template>
			<template #actions>
				<Button @click="detailDialogOpen = false">{{ 'Close' }}</Button>
			</template>
		</Dialog>
	</div>
</template>

<script>
import ObjectList from '../../components/ObjectList.vue';
import { Button, Dialog, Badge, createResource } from 'frappe-ui';
import { date } from '../../utils/format';
import StatCard from '../../components/_shared/StatCard.vue';
import {
	runBackupJob,
	toggleJobStatus,
	toggleSchedule,
	setupJob,
	listJobArchives,
	getRepoInfo,
	getJobHistory,
} from '../../utils/backupApi';

export default {
	name: 'ServerBackups',
	components: { ObjectList, Button, Dialog, Badge, StatCard },
	data() {
		return {
			stats: {},
			outputDialogOpen: false,
			outputTitle: '',
			outputContent: '',
			detailDialogOpen: false,
			selectedJob: null,
			jobHistory: null,
			detailLoading: false,
		};
	},
	mounted() {
		this.fetchStats();
	},
	methods: {
		formatDetailDate(value) {
			if (!value) return '\u2014';
			return date(value, 'llll');
		},
		formatDuration(seconds) {
			if (!seconds) return '\u2014';
			if (seconds < 60) return `${seconds}s`;
			if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
			const h = Math.floor(seconds / 3600);
			const m = Math.floor((seconds % 3600) / 60);
			return `${h}h ${m}m`;
		},
		priorityTheme(priority) {
			const map = {
				Critical: 'red',
				High: 'orange',
				Medium: 'blue',
				Low: 'gray',
			};
			return map[priority] || 'gray';
		},
		successRateColorClass(rate) {
			if (rate == null) return 'text-gray-400';
			if (rate > 90) return 'text-green-600';
			if (rate > 70) return 'text-yellow-600';
			return 'text-red-600';
		},
		lastRunStatusTheme(status) {
			const map = {
				Success: 'green',
				Failed: 'red',
				Running: 'blue',
				Queued: 'gray',
			};
			return map[status] || 'gray';
		},
		async openJobDetail(row) {
			this.selectedJob = row;
			this.jobHistory = null;
			this.detailLoading = true;
			this.detailDialogOpen = true;
			try {
				this.jobHistory = await getJobHistory(row.name, 10);
			} catch (e) {
				// history not critical
			} finally {
				this.detailLoading = false;
			}
		},
		fetchStats() {
			if (!this._statsResource) {
				this._statsResource = createResource({
					url: 'frappe.client.get_list',
					onSuccess: (result) => {
						const jobs = result || [];
						this.stats = {
							total: jobs.length,
							enabled: jobs.filter((j) => j.enabled).length,
							scheduled: jobs.filter((j) => j.schedule_enabled).length,
							failed: jobs.filter((j) => j.last_run_status === 'Failed').length,
						};
					},
				});
			}
			this._statsResource.submit({
				doctype: 'Backup Job',
				fields: ['name', 'enabled', 'schedule_enabled', 'last_run_status'],
				limit_page_length: 0,
			});
		},
		reloadList() {
			this.$refs.jobList?.$list?.reload();
		},
		async doRun(jobName, mode) {
			try {
				const result = await runBackupJob(jobName, mode);
				this.$toast({
					title: result.success !== false
						? `Backup started (${mode})`
						: (result.message || 'Failed'),
					variant: result.success !== false ? 'success' : 'error',
				});
				this.reloadList();
			} catch (e) {
				this.$toast({ title: `Error: ${e.message}`, variant: 'error' });
			}
		},
		async doToggleEnabled(jobName, currentEnabled) {
			try {
				const result = await toggleJobStatus(jobName);
				this.$toast({
					title: result.message || (currentEnabled ? 'Job disabled' : 'Job enabled'),
					variant: 'success',
				});
				this.reloadList();
				this.fetchStats();
			} catch (e) {
				this.$toast({ title: `Error: ${e.message}`, variant: 'error' });
			}
		},
		async doToggleSchedule(jobName) {
			try {
				const result = await toggleSchedule(jobName);
				this.$toast({ title: result.message || 'Schedule toggled', variant: 'success' });
				this.reloadList();
			} catch (e) {
				this.$toast({ title: `Error: ${e.message}`, variant: 'error' });
			}
		},
		async doSetup(jobName) {
			if (!confirm('Initialize/setup this backup job? This creates SSH keys and borg repo.')) return;
			this.$toast({ title: 'Setting up job...', variant: 'info' });
			try {
				const result = await setupJob(jobName);
				const ok = result.status === 'success' || result.success;
				this.$toast({
					title: ok ? 'Setup complete' : (result.message || 'Setup failed'),
					variant: ok ? 'success' : 'error',
				});
			} catch (e) {
				this.$toast({ title: `Setup error: ${e.message}`, variant: 'error' });
			}
		},
		async doListArchives(jobName) {
			this.outputTitle = 'Archives';
			this.outputContent = 'Loading...';
			this.outputDialogOpen = true;
			try {
				const result = await listJobArchives(jobName);
				this.outputContent = result.output || JSON.stringify(result, null, 2);
			} catch (e) {
				this.outputContent = `Error: ${e.message}`;
			}
		},
		async doRepoInfo(jobName) {
			this.outputTitle = 'Repository Info';
			this.outputContent = 'Loading...';
			this.outputDialogOpen = true;
			try {
				const result = await getRepoInfo(jobName);
				this.outputContent = result.output || JSON.stringify(result, null, 2);
			} catch (e) {
				this.outputContent = `Error: ${e.message}`;
			}
		},
	},
	computed: {
		listOptions() {
			return {
				doctype: 'Backup Job',
				orderBy: 'modified desc',
				fields: [
					'name', 'job_title', 'client', 'enabled', 'job_type', 'priority', 'description',
					'source_server', 'source_type', 'frappe_cloud_site_name', 'ssh_user', 'exclude_patterns',
					'destination_server', 'destination_path', 'encryption_enabled',
					'passphrase_mode', 'repo_initialized',
					'compression_level', 'retention_days', 'one_file_system', 'exclude_caches',
					'schedule_enabled', 'schedule_type', 'schedule_time', 'schedule_cron',
					'next_scheduled_run', 'schedule_paused',
					'last_run_on', 'last_run_status', 'last_run_duration',
					'total_runs', 'total_success', 'total_failed', 'success_rate',
					'last_backup_size_mb', 'avg_backup_size_mb',
				],
				columns: [
					{ label: 'Job Title', fieldname: 'job_title', width: 1 },
					{ label: 'Client', fieldname: 'client', width: 0.7 },
					{ label: 'Type', fieldname: 'job_type', width: '120px', align: 'center' },
					{
						label: 'Enabled',
						fieldname: 'enabled',
						width: '80px',
						type: 'Icon',
						Icon: (value) => value ? 'check' : '',
					},
					{
						label: 'Last Run',
						fieldname: 'last_run_status',
						width: '100px',
						align: 'center',
						type: 'Badge',
					},
					{
						label: 'Success %',
						fieldname: 'success_rate',
						width: '100px',
						align: 'center',
						format: (value) => value ? `${Math.round(value)}%` : '-',
					},
					{
						label: 'Last Run At',
						fieldname: 'last_run_on',
						width: 0.8,
						format: (value) => value ? date(value, 'lll') : 'Never',
					},
				],
				onRowClick: (row) => {
					this.openJobDetail(row);
				},
				filterControls: () => [
					{
						type: 'link',
						label: 'Client',
						fieldname: 'client',
						options: { doctype: 'Backup Client' },
					},
					{
						type: 'select',
						label: 'Last Status',
						fieldname: 'last_run_status',
						options: ['', 'Success', 'Failed'],
					},
					{
						type: 'checkbox',
						label: 'Enabled Only',
						fieldname: 'enabled',
					},
				],
				rowActions: ({ row }) => [
					{
						label: 'Run Now',
						onClick: () => this.doRun(row.name, 'run'),
					},
					{
						label: 'Dry Run',
						onClick: () => this.doRun(row.name, 'dry-run'),
					},
					{
						label: 'Check Repo',
						onClick: () => this.doRun(row.name, 'check'),
					},
					{
						label: row.enabled ? 'Disable' : 'Enable',
						onClick: () => this.doToggleEnabled(row.name, row.enabled),
					},
					{
						label: row.schedule_enabled ? 'Pause Schedule' : 'Resume Schedule',
						onClick: () => this.doToggleSchedule(row.name),
					},
					{
						label: 'Setup / Init',
						onClick: () => this.doSetup(row.name),
					},
					{
						label: 'List Archives',
						onClick: () => this.doListArchives(row.name),
					},
					{
						label: 'Repo Info',
						onClick: () => this.doRepoInfo(row.name),
					},
				],
			};
		},
	},
};
</script>
