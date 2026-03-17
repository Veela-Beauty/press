<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[{ label: 'Backup Jobs', route: '/backups/jobs' }]"
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

		<!-- Job Detail Dialog -->
		<Dialog v-model="detailDialogOpen" :options="{ title: selectedJob?.job_id || 'Job Details', size: 'lg' }">
			<template #body-content>
				<div v-if="selectedJob" class="space-y-4">
					<!-- Status & Identity -->
					<div class="grid grid-cols-2 gap-4">
						<div>
							<div class="text-xs text-gray-500">Status</div>
							<Badge :label="selectedJob.status" />
						</div>
						<div>
							<div class="text-xs text-gray-500">Priority</div>
							<div class="text-sm font-medium">{{ selectedJob.priority || '-' }}</div>
						</div>
						<div>
							<div class="text-xs text-gray-500">Client</div>
							<div class="text-sm font-medium">{{ selectedJob.client || '-' }}</div>
						</div>
						<div>
							<div class="text-xs text-gray-500">Mode</div>
							<div class="text-sm font-medium">{{ selectedJob.mode || '-' }}</div>
						</div>
					</div>

					<!-- Progress -->
					<div v-if="selectedJob.status === 'Running'" class="rounded border p-3">
						<div class="mb-1 flex justify-between text-sm">
							<span class="text-gray-500">Progress</span>
							<span>{{ Math.round(selectedJob.progress_percent || 0) }}%</span>
						</div>
						<div class="h-2 w-full overflow-hidden rounded-full bg-gray-200">
							<div
								class="h-full rounded-full bg-blue-500 transition-all"
								:style="{ width: `${selectedJob.progress_percent || 0}%` }"
							></div>
						</div>
						<div v-if="selectedJob.current_phase" class="mt-1 text-xs text-gray-500">
							Phase: {{ selectedJob.current_phase }}
						</div>
					</div>

					<!-- Timing -->
					<div class="rounded border p-3">
						<div class="mb-2 text-sm font-medium text-gray-700">Timing</div>
						<div class="grid grid-cols-2 gap-3 text-sm">
							<div>
								<div class="text-xs text-gray-500">Queued At</div>
								<div>{{ formatDetailDate(selectedJob.queued_at) }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Started At</div>
								<div>{{ formatDetailDate(selectedJob.started_at) }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Finished At</div>
								<div>{{ formatDetailDate(selectedJob.finished_at) }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Duration</div>
								<div>{{ formatDuration(selectedJob.duration_seconds) }}</div>
							</div>
						</div>
					</div>

					<!-- Error Message -->
					<div v-if="selectedJob.error_message" class="rounded border border-red-200 bg-red-50 p-3">
						<div class="mb-1 text-sm font-medium text-red-700">Error</div>
						<pre class="whitespace-pre-wrap text-xs text-red-600">{{ selectedJob.error_message }}</pre>
					</div>

					<!-- Worker Info -->
					<div v-if="selectedJob.worker_name" class="rounded border p-3">
						<div class="mb-2 text-sm font-medium text-gray-700">Worker</div>
						<div class="grid grid-cols-3 gap-3 text-sm">
							<div>
								<div class="text-xs text-gray-500">Worker</div>
								<div>{{ selectedJob.worker_name || '-' }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">PID</div>
								<div>{{ selectedJob.worker_pid || '-' }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Queue</div>
								<div>{{ selectedJob.queue_name || '-' }}</div>
							</div>
						</div>
					</div>

					<!-- Retry Info -->
					<div v-if="selectedJob.retry_count > 0" class="rounded border p-3">
						<div class="mb-2 text-sm font-medium text-gray-700">Retry Info</div>
						<div class="grid grid-cols-3 gap-3 text-sm">
							<div>
								<div class="text-xs text-gray-500">Retries</div>
								<div>{{ selectedJob.retry_count }} / {{ selectedJob.max_retries }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Next Retry</div>
								<div>{{ formatDetailDate(selectedJob.next_retry_at) }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">Exit Code</div>
								<div>{{ selectedJob.exit_code ?? '-' }}</div>
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
						Live Progress
					</Button>
					<Button @click="detailDialogOpen = false">Close</Button>
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
	getJobProgress,
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
			progressTimer: null,
			progressQueueName: null,
			progressGeneration: 0,
			detailDialogOpen: false,
			selectedJob: null,
		};
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
			this.stopPolling();
			this.progressQueueName = name;
			this.progressData = {};
			this.progressGeneration++;
			this.progressDialogOpen = true;
			this.pollProgress(this.progressGeneration);
		},
		async pollProgress(gen) {
			if (!this.progressQueueName || gen !== this.progressGeneration) return;
			try {
				this.progressData = await getJobProgress(this.progressQueueName);
			} catch (e) {
				this.progressData = { status: 'Error', progress_percent: 0, progress_message: e.message };
				return;
			}
			if (this.progressDialogOpen && gen === this.progressGeneration && this.progressData.status === 'Running') {
				this.progressTimer = setTimeout(() => this.pollProgress(gen), 3000);
			}
		},
		stopPolling() {
			if (this.progressTimer) clearTimeout(this.progressTimer);
			this.progressTimer = null;
			this.progressGeneration++;
			this.progressDialogOpen = false;
		},
	},
	beforeUnmount() {
		if (this.progressTimer) clearTimeout(this.progressTimer);
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
					'worker_name', 'worker_pid', 'queue_name',
					'retry_count', 'max_retries', 'next_retry_at',
					'error_message', 'exit_code', 'triggered_by', 'triggered_method',
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
