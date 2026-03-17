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
			<!-- Summary Cards -->
			<div class="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-4">
				<div class="rounded-lg border bg-white p-4">
					<div class="text-sm text-gray-500">Total Jobs</div>
					<div class="text-2xl font-semibold">{{ stats.total || 0 }}</div>
				</div>
				<div class="rounded-lg border bg-white p-4">
					<div class="text-sm text-gray-500">Enabled</div>
					<div class="text-2xl font-semibold text-green-600">{{ stats.enabled || 0 }}</div>
				</div>
				<div class="rounded-lg border bg-white p-4">
					<div class="text-sm text-gray-500">Scheduled</div>
					<div class="text-2xl font-semibold text-blue-600">{{ stats.scheduled || 0 }}</div>
				</div>
				<div class="rounded-lg border bg-white p-4">
					<div class="text-sm text-gray-500">Last Failed</div>
					<div class="text-2xl font-semibold text-red-600">{{ stats.failed || 0 }}</div>
				</div>
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

		<!-- Job Detail Dialog -->
		<Dialog v-model="detailDialogOpen" :options="{ title: selectedJob?.job_title || 'Job Details', size: 'xl' }">
			<template #body-content>
				<div v-if="detailLoading" class="flex items-center justify-center py-8">
					<div class="text-sm text-gray-500">Loading details...</div>
				</div>
				<div v-else-if="jobStats" class="space-y-4">
					<!-- Job Info -->
					<div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
						<div>
							<div class="text-xs text-gray-500">Client</div>
							<div class="text-sm font-medium">{{ jobStats.job_info?.client || '-' }}</div>
						</div>
						<div>
							<div class="text-xs text-gray-500">Type</div>
							<div class="text-sm font-medium">{{ jobStats.job_info?.job_type || '-' }}</div>
						</div>
						<div>
							<div class="text-xs text-gray-500">Enabled</div>
							<div class="text-sm font-medium">{{ jobStats.job_info?.enabled ? 'Yes' : 'No' }}</div>
						</div>
						<div>
							<div class="text-xs text-gray-500">Last Run</div>
							<Badge v-if="jobStats.last_run?.status" :label="jobStats.last_run.status" />
							<span v-else class="text-sm">Never</span>
						</div>
					</div>

					<!-- Statistics -->
					<div class="rounded border p-3">
						<div class="mb-2 text-sm font-medium text-gray-700">Statistics</div>
						<div class="grid grid-cols-3 gap-3 sm:grid-cols-6 text-sm">
							<div>
								<div class="text-xs text-gray-500">Total Runs</div>
								<div class="font-medium">{{ jobStats.statistics?.total_runs || 0 }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Success</div>
								<div class="font-medium text-green-600">{{ jobStats.statistics?.total_success || 0 }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Failed</div>
								<div class="font-medium text-red-600">{{ jobStats.statistics?.total_failed || 0 }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Success Rate</div>
								<div class="font-medium">{{ jobStats.statistics?.success_rate || 0 }}%</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Avg Size</div>
								<div class="font-medium">{{ jobStats.statistics?.avg_backup_size_mb || 0 }} MB</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Last Size</div>
								<div class="font-medium">{{ jobStats.statistics?.last_backup_size_mb || 0 }} MB</div>
							</div>
						</div>
					</div>

					<!-- Schedule -->
					<div class="rounded border p-3">
						<div class="mb-2 text-sm font-medium text-gray-700">Schedule</div>
						<div class="grid grid-cols-2 gap-3 sm:grid-cols-4 text-sm">
							<div>
								<div class="text-xs text-gray-500">Schedule</div>
								<div>{{ jobStats.schedule?.enabled ? 'Enabled' : 'Disabled' }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Type</div>
								<div>{{ jobStats.schedule?.type || '-' }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Time / Cron</div>
								<div>{{ jobStats.schedule?.cron || jobStats.schedule?.time || '-' }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Next Run</div>
								<div>{{ jobStats.schedule?.next_run ? formatDetailDate(jobStats.schedule.next_run) : '-' }}</div>
							</div>
						</div>
					</div>

					<!-- Recent History -->
					<div v-if="jobHistory?.queue_jobs?.length" class="rounded border p-3">
						<div class="mb-2 text-sm font-medium text-gray-700">Recent Runs (Last 10)</div>
						<div class="overflow-x-auto">
							<table class="w-full text-sm">
								<thead>
									<tr class="border-b text-left text-gray-500">
										<th class="py-1.5 pr-3 text-xs">Job ID</th>
										<th class="py-1.5 pr-3 text-xs">Status</th>
										<th class="py-1.5 pr-3 text-xs">Started</th>
										<th class="py-1.5 pr-3 text-xs">Duration</th>
										<th class="py-1.5 text-xs">Error</th>
									</tr>
								</thead>
								<tbody>
									<tr v-for="qj in jobHistory.queue_jobs" :key="qj.name" class="border-b last:border-0">
										<td class="py-1.5 pr-3 font-mono text-xs">{{ qj.job_id }}</td>
										<td class="py-1.5 pr-3"><Badge :label="qj.status" size="sm" /></td>
										<td class="py-1.5 pr-3 text-xs">{{ formatDetailDate(qj.started_at) }}</td>
										<td class="py-1.5 pr-3 text-xs">{{ formatDuration(qj.duration_seconds) }}</td>
										<td class="py-1.5 text-xs text-red-500 truncate max-w-[200px]">{{ qj.error_message || '-' }}</td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>
				</div>
				<div v-else class="py-8 text-center text-sm text-gray-400">
					No details available
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
import { Button, Dialog, Badge } from 'frappe-ui';
import { date } from '../../utils/format';
import {
	runBackupJob,
	toggleJobStatus,
	toggleSchedule,
	setupJob,
	listJobArchives,
	getRepoInfo,
	getJobStatistics,
	getJobHistory,
} from '../../utils/backupApi';

export default {
	name: 'ServerBackups',
	components: { ObjectList, Button, Dialog, Badge },
	data() {
		return {
			stats: {},
			outputDialogOpen: false,
			outputTitle: '',
			outputContent: '',
			detailDialogOpen: false,
			selectedJob: null,
			jobStats: null,
			jobHistory: null,
			detailLoading: false,
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
		formatDuration(seconds) {
			if (!seconds) return '-';
			if (seconds < 60) return `${seconds}s`;
			if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
			const h = Math.floor(seconds / 3600);
			const m = Math.floor((seconds % 3600) / 60);
			return `${h}h ${m}m`;
		},
		async openJobDetail(row) {
			this.selectedJob = row;
			this.jobStats = null;
			this.jobHistory = null;
			this.detailLoading = true;
			this.detailDialogOpen = true;
			try {
				const [stats, history] = await Promise.all([
					getJobStatistics(row.name),
					getJobHistory(row.name, 10),
				]);
				this.jobStats = stats;
				this.jobHistory = history;
			} catch (e) {
				this.$toast({ title: `Failed to load details: ${e.message}`, variant: 'error' });
			} finally {
				this.detailLoading = false;
			}
		},
		async fetchStats() {
			try {
				const params = new URLSearchParams({
					doctype: 'Backup Job',
					fields: JSON.stringify(['name', 'enabled', 'schedule_enabled', 'last_run_status']),
					limit_page_length: 0,
				});
				const res = await fetch(
					`/api/method/frappe.client.get_list?${params}`,
					{ headers: { 'X-Frappe-CSRF-Token': window.csrf_token } }
				);
				const data = await res.json();
				const jobs = data.message || [];
				this.stats = {
					total: jobs.length,
					enabled: jobs.filter((j) => j.enabled).length,
					scheduled: jobs.filter((j) => j.schedule_enabled).length,
					failed: jobs.filter((j) => j.last_run_status === 'Failed').length,
				};
			} catch (e) {
				// ignore
			}
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
					'name', 'job_title', 'client', 'enabled', 'job_type',
					'priority', 'source_type', 'last_run_on', 'last_run_status',
					'total_runs', 'total_success', 'total_failed', 'success_rate',
					'schedule_enabled',
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
				rowActions: ({ row }) => {
					const actions = [
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
					];
					return actions;
				},
			};
		},
	},
};
</script>
