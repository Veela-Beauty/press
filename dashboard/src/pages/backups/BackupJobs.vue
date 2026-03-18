<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[{ label: 'Daman Job Queue', route: '/backups/jobs' }]"
				/>
				<template #actions>
					<Button variant="solid" @click="showRunDialog">
						Run Backup
					</Button>
				</template>
			</Header>
		</div>
		<div class="p-5">
			<ObjectList ref="jobList" :options="listOptions" />
		</div>

		<!-- Run Backup Dialog -->
		<Dialog v-model="runDialogOpen" :options="{ title: 'Run Backup', size: 'sm' }">
			<template #body-content>
				<div class="space-y-4">
					<FormControl
						label="Backup Job"
						type="autocomplete"
						v-model="runForm.job_name"
						:options="jobOptions"
						placeholder="Select a backup job..."
					/>
					<FormControl
						label="Mode"
						type="select"
						v-model="runForm.mode"
						:options="[
							{ label: 'Run (full backup)', value: 'run' },
							{ label: 'Dry Run (simulate)', value: 'dry-run' },
							{ label: 'Check (verify repo)', value: 'check' },
							{ label: 'Smart Cycle', value: 'smart-cycle' },
						]"
					/>
					<FormControl
						label="Priority"
						type="select"
						v-model="runForm.priority"
						:options="[
							{ label: 'Normal', value: 'Normal' },
							{ label: 'Critical', value: 'Critical' },
							{ label: 'High', value: 'High' },
							{ label: 'Low', value: 'Low' },
						]"
					/>
				</div>
			</template>
			<template #actions>
				<Button variant="solid" @click="executeRun" :loading="runLoading">
					Run Now
				</Button>
			</template>
		</Dialog>

		<!-- Progress Dialog -->
		<Dialog v-model="progressDialogOpen" :options="{ title: 'Job Progress', size: 'sm' }">
			<template #body-content>
				<div class="space-y-3">
					<div class="flex items-center justify-between">
						<span class="text-sm text-gray-600">Status</span>
						<Badge :label="progressData.status || '...'" />
					</div>
					<div>
						<div class="mb-1 flex justify-between text-sm">
							<span>Progress</span>
							<span>{{ Math.round(progressData.progress_percent || 0) }}%</span>
						</div>
						<div class="h-2 w-full overflow-hidden rounded-full bg-gray-200">
							<div
								class="h-full rounded-full bg-blue-500 transition-all"
								:style="{ width: (progressData.progress_percent || 0) + '%' }"
							></div>
						</div>
					</div>
					<div v-if="progressData.progress_message" class="text-sm text-gray-500">
						{{ progressData.progress_message }}
					</div>
					<div v-if="progressData.current_phase" class="text-sm text-gray-500">
						Phase: {{ progressData.current_phase }}
					</div>
				</div>
			</template>
			<template #actions>
				<Button @click="stopPolling">Close</Button>
			</template>
		</Dialog>

		<!-- Job Detail Dialog (Enriched) -->
		<Dialog v-model="detailDialogOpen" :options="{ title: selectedJob?.job_id || 'Job Details', size: 'xl' }">
			<template #body-content>
				<div v-if="selectedJob" class="max-h-[70vh] overflow-y-auto pr-1">

					<!-- Section 1: Identity -->
					<div class="mb-4 rounded-md border border-gray-200 p-4">
						<h4 class="mb-3 text-sm font-semibold text-gray-800">{{ 'Identity' }}</h4>
						<div class="divide-y divide-gray-100">
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Job ID' }}</span>
								<span class="text-sm font-medium font-mono">{{ selectedJob.job_id || '\u2014' }}</span>
							</div>
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Backup Job' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.job_name || '\u2014' }}</span>
							</div>
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Client' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.client || '\u2014' }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Mode' }}</span>
								<Badge v-if="selectedJob.mode" :label="selectedJob.mode" variant="subtle" theme="blue" />
								<span v-else class="text-sm font-medium">&mdash;</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Priority' }}</span>
								<Badge v-if="selectedJob.priority" :label="selectedJob.priority" variant="subtle" :theme="priorityTheme(selectedJob.priority)" />
								<span v-else class="text-sm font-medium">&mdash;</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Status' }}</span>
								<Badge v-if="selectedJob.status" :label="selectedJob.status" :theme="statusTheme(selectedJob.status)" />
								<span v-else class="text-sm font-medium">&mdash;</span>
							</div>
						</div>
					</div>

					<!-- Section 2: Progress -->
					<div class="mb-4 rounded-md border border-gray-200 p-4">
						<h4 class="mb-3 text-sm font-semibold text-gray-800">{{ 'Progress' }}</h4>
						<div class="divide-y divide-gray-100">
							<div class="py-1.5">
								<div class="mb-1 flex justify-between text-sm">
									<span class="text-gray-600">{{ 'Progress' }}</span>
									<span class="font-medium">{{ Math.round(selectedJob.progress_percent || 0) }}%</span>
								</div>
								<div class="h-2.5 w-full overflow-hidden rounded-full bg-gray-200">
									<div
										class="h-full rounded-full transition-all duration-300"
										:class="progressBarColor(selectedJob.status, selectedJob.progress_percent)"
										:style="{ width: `${selectedJob.progress_percent || 0}%` }"
									></div>
								</div>
							</div>
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Progress Message' }}</span>
								<span class="text-sm font-medium text-right max-w-[60%]">{{ selectedJob.progress_message || '\u2014' }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Current Phase' }}</span>
								<Badge v-if="selectedJob.current_phase" :label="selectedJob.current_phase" variant="subtle" theme="orange" />
								<span v-else class="text-sm font-medium">&mdash;</span>
							</div>
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Files Processed' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.files_processed ? selectedJob.files_processed.toLocaleString() : '\u2014' }}</span>
							</div>
						</div>
					</div>

					<!-- Section 3: Timing -->
					<div class="mb-4 rounded-md border border-gray-200 p-4">
						<h4 class="mb-3 text-sm font-semibold text-gray-800">{{ 'Timing' }}</h4>
						<div class="divide-y divide-gray-100">
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Queued At' }}</span>
								<span class="text-sm font-medium">{{ formatDetailDate(selectedJob.queued_at) }}</span>
							</div>
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Started At' }}</span>
								<span class="text-sm font-medium">{{ formatDetailDate(selectedJob.started_at) }}</span>
							</div>
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Finished At' }}</span>
								<span class="text-sm font-medium">{{ formatDetailDate(selectedJob.finished_at) }}</span>
							</div>
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Duration' }}</span>
								<span class="text-sm font-medium">{{ formatDuration(selectedJob.duration_seconds) }}</span>
							</div>
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Queue Wait' }}</span>
								<span class="text-sm font-medium">{{ formatDuration(selectedJob.queue_wait_seconds) }}</span>
							</div>
						</div>
					</div>

					<!-- Section 4: Worker -->
					<div class="mb-4 rounded-md border border-gray-200 p-4">
						<h4 class="mb-3 text-sm font-semibold text-gray-800">{{ 'Worker' }}</h4>
						<div class="divide-y divide-gray-100">
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Worker Name' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.worker_name || '\u2014' }}</span>
							</div>
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Worker PID' }}</span>
								<span class="text-sm font-medium font-mono">{{ selectedJob.worker_pid || '\u2014' }}</span>
							</div>
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Queue Name' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.queue_name || '\u2014' }}</span>
							</div>
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'RQ Job ID' }}</span>
								<span class="text-sm font-medium font-mono truncate max-w-[60%]" :title="selectedJob.rq_job_id">{{ selectedJob.rq_job_id || '\u2014' }}</span>
							</div>
						</div>
					</div>

					<!-- Section 5: Retry -->
					<div class="mb-4 rounded-md border border-gray-200 p-4">
						<h4 class="mb-3 text-sm font-semibold text-gray-800">{{ 'Retry' }}</h4>
						<div class="divide-y divide-gray-100">
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Retry Count' }}</span>
								<span class="text-sm font-medium">{{ (selectedJob.retry_count || 0) }} / {{ (selectedJob.max_retries || 0) }}</span>
							</div>
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Next Retry At' }}</span>
								<span class="text-sm font-medium">{{ formatDetailDate(selectedJob.next_retry_at) }}</span>
							</div>
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Triggered By' }}</span>
								<span class="text-sm font-medium">{{ selectedJob.triggered_by || '\u2014' }}</span>
							</div>
							<div class="flex items-center justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Triggered Method' }}</span>
								<Badge v-if="selectedJob.triggered_method" :label="selectedJob.triggered_method" variant="subtle" theme="gray" />
								<span v-else class="text-sm font-medium">&mdash;</span>
							</div>
						</div>
					</div>

					<!-- Section 6: Result -->
					<div class="rounded-md border border-gray-200 p-4">
						<h4 class="mb-3 text-sm font-semibold text-gray-800">{{ 'Result' }}</h4>
						<div class="divide-y divide-gray-100">
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Exit Code' }}</span>
								<span class="text-sm font-medium font-mono" :class="exitCodeClass(selectedJob.exit_code)">{{ selectedJob.exit_code ?? '\u2014' }}</span>
							</div>
							<div class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Run Log' }}</span>
								<a
									v-if="selectedJob.run_log"
									:href="`/app/backup-run-log/${selectedJob.run_log}`"
									target="_blank"
									class="text-sm font-medium text-blue-600 hover:underline"
								>{{ selectedJob.run_log }}</a>
								<span v-else class="text-sm font-medium">&mdash;</span>
							</div>
							<div v-if="selectedJob.error_message" class="py-1.5">
								<div class="mb-1 text-sm text-gray-600">{{ 'Error Message' }}</div>
								<pre class="error-message-block">{{ selectedJob.error_message }}</pre>
							</div>
							<div v-else class="flex justify-between py-1.5">
								<span class="text-sm text-gray-600">{{ 'Error Message' }}</span>
								<span class="text-sm font-medium">&mdash;</span>
							</div>
						</div>
					</div>

				</div>
			</template>
			<template #actions>
				<div class="flex gap-2">
					<Button
						v-if="selectedJob?.status === 'Running'"
						variant="subtle"
						@click="detailDialogOpen = false; showProgress(selectedJob.name)"
					>
						{{ 'Live Progress' }}
					</Button>
					<Button @click="detailDialogOpen = false">{{ 'Close' }}</Button>
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script>
import ObjectList from '../../components/ObjectList.vue';
import { Button, Dialog, FormControl, Badge } from 'frappe-ui';
import { date } from '../../utils/format';
import {
	runBackupJob,
	cancelJob,
	retryJob,
	forceCompleteJob,
} from '../../utils/backupApi';

export default {
	name: 'BackupJobs',
	components: { ObjectList, Button, Dialog, FormControl, Badge },
	data() {
		return {
			runDialogOpen: false,
			runForm: { job_name: '', mode: 'run', priority: 'Normal' },
			runLoading: false,
			jobOptions: [],
			progressDialogOpen: false,
			progressData: {},
			progressQueueName: null,
			detailDialogOpen: false,
			selectedJob: null,
		};
	},
	methods: {
		formatDetailDate(value) {
			if (!value) return '\u2014';
			return date(value, 'llll');
		},
		formatDuration(seconds) {
			if (seconds == null || seconds === '' || seconds === 0) return '\u2014';
			const s = Math.round(seconds);
			if (s < 60) return `${s}s`;
			const h = Math.floor(s / 3600);
			const m = Math.floor((s % 3600) / 60);
			const rem = s % 60;
			if (h > 0) return `${h}h ${m}m ${rem}s`;
			return `${m}m ${rem}s`;
		},
		statusTheme(status) {
			const map = {
				Success: 'green',
				Running: 'blue',
				Queued: 'gray',
				Failed: 'red',
				Cancelled: 'orange',
			};
			return map[status] || 'gray';
		},
		priorityTheme(priority) {
			const map = {
				Critical: 'red',
				High: 'orange',
				Normal: 'blue',
				Low: 'gray',
			};
			return map[priority] || 'gray';
		},
		progressBarColor(status, percent) {
			if (status === 'Failed') return 'bg-red-500';
			if (status === 'Cancelled') return 'bg-orange-400';
			if (status === 'Success') return 'bg-green-500';
			if (percent >= 80) return 'bg-green-500';
			if (percent >= 40) return 'bg-blue-500';
			return 'bg-blue-400';
		},
		exitCodeClass(code) {
			if (code == null) return '';
			return code === 0 ? 'text-green-600' : 'text-red-600';
		},
		async showRunDialog() {
			try {
				const params = new URLSearchParams({
					doctype: 'Backup Job',
					filters: JSON.stringify({ enabled: 1 }),
					fields: JSON.stringify(['name', 'job_title', 'client']),
					limit_page_length: 100,
				});
				const res = await fetch(
					`/api/method/frappe.client.get_list?${params}`,
					{ headers: { 'X-Frappe-CSRF-Token': window.csrf_token } }
				);
				const data = await res.json();
				this.jobOptions = (data.message || []).map((j) => ({
					label: `${j.job_title} (${j.client})`,
					value: j.name,
				}));
			} catch (e) {
				this.jobOptions = [];
			}
			this.runForm = { job_name: '', mode: 'run', priority: 'Normal' };
			this.runDialogOpen = true;
		},
		async executeRun() {
			const jobName = typeof this.runForm.job_name === 'object'
				? this.runForm.job_name.value
				: this.runForm.job_name;
			if (!jobName) {
				this.$toast({ title: 'Select a backup job', variant: 'error' });
				return;
			}
			this.runLoading = true;
			try {
				const result = await runBackupJob(jobName, this.runForm.mode, this.runForm.priority);
				if (result.success !== false) {
					this.$toast({ title: 'Backup started', variant: 'success' });
					this.runDialogOpen = false;
					this.reloadList();
				} else {
					this.$toast({ title: result.message || 'Failed', variant: 'error' });
				}
			} catch (e) {
				this.$toast({ title: `Error: ${e.message}`, variant: 'error' });
			} finally {
				this.runLoading = false;
			}
		},
		reloadList() {
			this.$refs.jobList?.$list?.reload();
		},
		async doCancel(name) {
			try {
				await cancelJob(name);
				this.$toast({ title: 'Job cancelled', variant: 'success' });
				this.reloadList();
			} catch (e) {
				this.$toast({ title: `Cancel failed: ${e.message}`, variant: 'error' });
			}
		},
		async doRetry(name) {
			try {
				const result = await retryJob(name);
				this.$toast({
					title: result.success !== false
						? `Retry queued: ${result.new_job_id || ''}`
						: result.message || 'Retry failed',
					variant: result.success !== false ? 'success' : 'error',
				});
				this.reloadList();
			} catch (e) {
				this.$toast({ title: `Retry failed: ${e.message}`, variant: 'error' });
			}
		},
		async doForceComplete(name) {
			if (!confirm('Force-complete this stuck job? It will be marked as Failed.')) return;
			try {
				await forceCompleteJob(name);
				this.$toast({ title: 'Job force-completed', variant: 'success' });
				this.reloadList();
			} catch (e) {
				this.$toast({ title: `Failed: ${e.message}`, variant: 'error' });
			}
		},
		showProgress(name) {
			this.progressQueueName = name;
			this.progressData = {};
			this.progressDialogOpen = true;
		},
		
		stopPolling() {
			this.progressDialogOpen = false;
		},
	},
	mounted() {
		this.$socket.on('backup_job_progress', (data) => {
			if (this.progressQueueName === data.job_name && this.progressDialogOpen) {
				this.progressData = { ...this.progressData, ...data };
			}
		});
		this.$socket.on('backup_job_completed', () => {
			this.reloadList();
		});
		this.$socket.on('backup_job_failed', () => {
			this.reloadList();
		});
	},
	beforeUnmount() {
		this.$socket.off('backup_job_progress');
		this.$socket.off('backup_job_completed');
		this.$socket.off('backup_job_failed');
	},
	computed: {
		listOptions() {
			return {
				doctype: 'Backup Job Queue',
				orderBy: 'queued_at desc',
				fields: [
					'name', 'job_id', 'job_name', 'client', 'mode', 'priority',
					'status', 'progress_percent', 'progress_message', 'current_phase',
					'files_processed', 'queued_at', 'started_at', 'finished_at',
					'duration_seconds', 'queue_wait_seconds',
					'worker_name', 'worker_pid', 'queue_name', 'rq_job_id',
					'retry_count', 'max_retries', 'next_retry_at',
					'error_message', 'exit_code', 'run_log',
					'triggered_by', 'triggered_method',
				],
				columns: [
					{ label: 'Job ID', fieldname: 'job_id', width: 0.6 },
					{ label: 'Client', fieldname: 'client', width: 0.8 },
					{ label: 'Mode', fieldname: 'mode', width: '100px', align: 'center' },
					{ label: 'Status', fieldname: 'status', width: '120px', align: 'center', type: 'Badge' },
					{
						label: 'Progress',
						fieldname: 'progress_percent',
						width: '100px',
						align: 'center',
						format: (value) => value ? `${Math.round(value)}%` : '-',
					},
					{ label: 'Priority', fieldname: 'priority', width: '100px', align: 'center' },
					{
						label: 'Queued At',
						fieldname: 'queued_at',
						width: 0.8,
						align: 'right',
						format: (value) => value ? date(value, 'llll') : '',
					},
				],
				onRowClick: (row) => {
					this.selectedJob = row;
					this.detailDialogOpen = true;
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
						label: 'Status',
						fieldname: 'status',
						options: ['', 'Queued', 'Running', 'Success', 'Failed', 'Cancelled'],
					},
					{
						type: 'select',
						label: 'Mode',
						fieldname: 'mode',
						options: ['', 'run', 'dry-run', 'check'],
					},
					{
						type: 'select',
						label: 'Priority',
						fieldname: 'priority',
						options: ['', 'Critical', 'High', 'Normal', 'Low'],
					},
				],
				rowActions: ({ row }) => {
					const actions = [];
					if (row.status === 'Queued' || row.status === 'Running') {
						actions.push({
							label: 'Cancel',
							onClick: () => this.doCancel(row.name),
						});
					}
					if (row.status === 'Running') {
						actions.push({
							label: 'View Progress',
							onClick: () => this.showProgress(row.name),
						});
						actions.push({
							label: 'Force Complete',
							onClick: () => this.doForceComplete(row.name),
						});
					}
					if (row.status === 'Failed' || row.status === 'Cancelled') {
						actions.push({
							label: 'Retry',
							onClick: () => this.doRetry(row.name),
						});
					}
					return actions;
				},
			};
		},
	},
};
</script>

<style scoped>
.error-message-block {
	max-height: 200px;
	overflow-y: auto;
	white-space: pre-wrap;
	word-break: break-word;
	font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace;
	font-size: 0.75rem;
	line-height: 1.5;
	padding: 0.75rem;
	border-radius: 0.375rem;
	background-color: #fef2f2;
	border: 1px solid #fecaca;
	color: #dc2626;
}
</style>
