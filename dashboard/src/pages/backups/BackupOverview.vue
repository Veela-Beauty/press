<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[{ label: 'Backup Overview', route: '/backups/overview' }]"
				/>
				<template #actions>
					<Button variant="solid" @click="showRunDialog">
						Run Backup
					</Button>
				</template>
			</Header>
		</div>

		<div class="p-5 space-y-6">
			<!-- Health Summary Cards -->
			<div class="grid grid-cols-1 md:grid-cols-5 gap-4">
				<div class="rounded-lg border p-4 text-center">
					<div class="text-2xl font-bold">{{ overview?.total_clients || 0 }}</div>
					<div class="text-sm text-gray-600">Total Clients</div>
				</div>
				<div class="rounded-lg border p-4 text-center border-green-200 bg-green-50">
					<div class="text-2xl font-bold text-green-700">{{ overview?.health_summary?.Healthy || 0 }}</div>
					<div class="text-sm text-green-600">Healthy</div>
				</div>
				<div class="rounded-lg border p-4 text-center border-yellow-200 bg-yellow-50">
					<div class="text-2xl font-bold text-yellow-700">{{ overview?.health_summary?.Warning || 0 }}</div>
					<div class="text-sm text-yellow-600">Warning</div>
				</div>
				<div class="rounded-lg border p-4 text-center border-red-200 bg-red-50">
					<div class="text-2xl font-bold text-red-700">{{ overview?.health_summary?.Critical || 0 }}</div>
					<div class="text-sm text-red-600">Critical</div>
				</div>
				<div class="rounded-lg border p-4 text-center border-gray-200 bg-gray-50">
					<div class="text-2xl font-bold text-gray-700">{{ overview?.health_summary?.Unknown || 0 }}</div>
					<div class="text-sm text-gray-600">Unknown</div>
				</div>
			</div>

			<!-- Job Queue Stats -->
			<div class="rounded-lg border p-4">
				<h3 class="text-lg font-semibold mb-3">Job Queue</h3>
				<div class="flex gap-4 flex-wrap">
					<Badge v-for="(count, status) in overview?.job_stats" :key="status"
						:label="`${status}: ${count}`"
						:theme="jobStatusTheme(status)"
					/>
				</div>
			</div>

			<!-- Active Alerts -->
			<div v-if="overview?.active_alerts?.length" class="rounded-lg border border-orange-200 bg-orange-50 p-4">
				<h3 class="text-lg font-semibold mb-3 text-orange-800">Active Alerts (Last 7 Days)</h3>
				<div class="space-y-2">
					<div v-for="alert in overview.active_alerts" :key="alert.name"
						class="flex items-center justify-between bg-white rounded p-2">
						<div>
							<span class="font-medium">{{ alert.alert_name }}</span>
							<Badge :label="alert.priority" :theme="severityTheme(alert.priority)" class="ml-2" />
						</div>
						<div class="text-sm text-gray-500">
							Triggered {{ formatDate(alert.last_triggered) }} ({{ alert.trigger_count }}x)
						</div>
					</div>
				</div>
			</div>

			<!-- Recent Jobs Table -->
			<div class="rounded-lg border p-4">
				<div class="flex items-center justify-between mb-3">
					<h3 class="text-lg font-semibold">Recent Jobs (24h)</h3>
					<router-link to="/backups/jobs" class="text-sm text-blue-600 hover:underline">
						View All
					</router-link>
				</div>
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b text-left text-gray-500">
								<th class="py-2 pr-4">Client</th>
								<th class="py-2 pr-4">Mode</th>
								<th class="py-2 pr-4">Status</th>
								<th class="py-2 pr-4">Priority</th>
								<th class="py-2">Queued</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="job in overview?.recent_jobs" :key="job.name" class="border-b last:border-0">
								<td class="py-2 pr-4">{{ job.client }}</td>
								<td class="py-2 pr-4">{{ job.mode }}</td>
								<td class="py-2 pr-4">
									<Badge :label="job.status" :theme="jobStatusTheme(job.status)" />
								</td>
								<td class="py-2 pr-4">{{ job.priority }}</td>
								<td class="py-2">{{ formatDate(job.queued_at) }}</td>
							</tr>
							<tr v-if="!overview?.recent_jobs?.length">
								<td colspan="5" class="py-4 text-center text-gray-400">No recent jobs</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>

			<!-- Client List -->
			<div class="rounded-lg border p-4">
				<div class="flex items-center justify-between mb-3">
					<h3 class="text-lg font-semibold">Backup Clients</h3>
					<router-link to="/backups/servers" class="text-sm text-blue-600 hover:underline">
						View All
					</router-link>
				</div>
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b text-left text-gray-500">
								<th class="py-2 pr-4">Client</th>
								<th class="py-2 pr-4">Health</th>
								<th class="py-2 pr-4">Last Backup</th>
								<th class="py-2 pr-4">Storage %</th>
								<th class="py-2">Auto</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="client in overview?.clients" :key="client.name" class="border-b last:border-0">
								<td class="py-2 pr-4 font-medium">{{ client.client_name || client.name }}</td>
								<td class="py-2 pr-4">
									<Badge :label="client.backup_health_status || 'Unknown'" :theme="healthTheme(client.backup_health_status)" />
								</td>
								<td class="py-2 pr-4">{{ formatDate(client.last_backup_on) }}</td>
								<td class="py-2 pr-4">{{ client.storage_usage_percent ? `${client.storage_usage_percent}%` : '-' }}</td>
								<td class="py-2">{{ client.auto_backup_enabled ? 'Yes' : 'No' }}</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>
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
	</div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { Badge, Button, Dialog, FormControl } from 'frappe-ui';
import { date as formatDateUtil } from '../../utils/format';
import { runBackupJob } from '../../utils/backupApi';

const overview = ref(null);
const runDialogOpen = ref(false);
const runForm = ref({ job_name: '', mode: 'run', priority: 'Normal' });
const runLoading = ref(false);
const jobOptions = ref([]);

function formatDate(value) {
	if (!value) return '-';
	return formatDateUtil(value, 'lll');
}

function jobStatusTheme(status) {
	const themes = {
		'Queued': 'blue',
		'Running': 'orange',
		'Success': 'green',
		'Failed': 'red',
		'Cancelled': 'gray',
	};
	return themes[status] || 'gray';
}

function healthTheme(status) {
	const themes = {
		'Healthy': 'green',
		'Warning': 'orange',
		'Critical': 'red',
		'Unknown': 'gray',
	};
	return themes[status] || 'gray';
}

function severityTheme(severity) {
	const themes = {
		'Critical': 'red',
		'High': 'orange',
		'Medium': 'blue',
		'Low': 'gray',
	};
	return themes[severity] || 'gray';
}

async function fetchOverview() {
	try {
		const res = await fetch('/api/method/daman_backup.daman_backup.press_api.get_backup_overview', {
			headers: { 'X-Frappe-CSRF-Token': window.csrf_token },
		});
		const data = await res.json();
		overview.value = data.message;
	} catch (e) {
		console.error('Failed to fetch backup overview:', e);
	}
}

async function showRunDialog() {
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
		jobOptions.value = (data.message || []).map((j) => ({
			label: `${j.job_title} (${j.client})`,
			value: j.name,
		}));
	} catch (e) {
		jobOptions.value = [];
	}
	runForm.value = { job_name: '', mode: 'run', priority: 'Normal' };
	runDialogOpen.value = true;
}

async function executeRun() {
	const jobName = typeof runForm.value.job_name === 'object'
		? runForm.value.job_name.value
		: runForm.value.job_name;
	if (!jobName) return;
	runLoading.value = true;
	try {
		const result = await runBackupJob(jobName, runForm.value.mode, runForm.value.priority);
		if (result.success !== false) {
			runDialogOpen.value = false;
			fetchOverview();
		}
	} catch (e) {
		// HTTP/parse errors already thrown by backupApi
	} finally {
		runLoading.value = false;
	}
}

onMounted(() => {
	fetchOverview();
});
</script>
