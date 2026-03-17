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
		};
	},
	methods: {
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
					'name', 'job_id', 'client', 'mode', 'priority',
					'status', 'progress_percent', 'queued_at',
					'started_at', 'finished_at', 'duration_seconds',
					'error_message',
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
