<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[
						{ label: 'Daman Backup', route: '/backups/overview' },
						{ label: 'Clients', route: '/backups/clients' },
						{ label: clientName },
					]"
				/>
			</Header>
		</div>

		<!-- Loading State -->
		<div v-if="loading" class="flex items-center justify-center py-16">
			<div class="text-sm text-gray-500">{{ 'Loading client details...' }}</div>
		</div>

		<!-- Error State -->
		<div v-else-if="error" class="flex items-center justify-center py-16">
			<div class="text-sm text-red-500">{{ error }}</div>
		</div>

		<!-- Content -->
		<div v-else class="p-5">
			<!-- Client Header -->
			<div class="mb-6 flex items-center gap-3">
				<h2 class="text-xl font-semibold">{{ portal?.client_name || clientName }}</h2>
				<Badge
					v-if="portal?.health_status"
					:label="portal.health_status"
					:theme="healthTheme(portal.health_status)"
				/>
				<Badge
					v-if="portal?.status"
					:label="portal.status"
					:theme="statusTheme(portal.status)"
				/>
			</div>

			<!-- Tabs -->
			<div class="mb-4 border-b">
				<nav class="-mb-px flex gap-6">
					<button
						v-for="tab in tabs"
						:key="tab.key"
						class="whitespace-nowrap border-b-2 px-1 pb-3 text-sm font-medium transition-colors"
						:class="activeTab === tab.key
							? 'border-blue-500 text-blue-600'
							: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'"
						@click="activeTab = tab.key"
					>
						{{ tab.label }}
					</button>
				</nav>
			</div>

			<!-- Tab: Overview -->
			<div v-if="activeTab === 'overview'">
				<!-- Stat Cards -->
				<div class="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-5">
					<div class="rounded-lg border bg-white p-4">
						<div class="text-xs text-gray-500">{{ 'Total Jobs' }}</div>
						<div class="text-xl font-semibold">{{ portal?.total_jobs || 0 }}</div>
					</div>
					<div class="rounded-lg border bg-white p-4">
						<div class="text-xs text-gray-500">{{ 'Success Rate' }}</div>
						<div
							class="text-xl font-semibold"
							:class="successRateColor(portal?.success_rate)"
						>
							{{ portal?.success_rate != null ? `${Math.round(portal.success_rate)}%` : '-' }}
						</div>
					</div>
					<div class="rounded-lg border bg-white p-4">
						<div class="text-xs text-gray-500">{{ 'Last Backup' }}</div>
						<div class="text-sm font-medium">{{ formatDate(portal?.last_backup_date) }}</div>
					</div>
					<div class="rounded-lg border bg-white p-4">
						<div class="text-xs text-gray-500">{{ 'Total Data' }}</div>
						<div class="text-xl font-semibold">
							{{ portal?.total_data_mb ? `${portal.total_data_mb} MB` : '-' }}
						</div>
					</div>
					<div class="rounded-lg border bg-white p-4">
						<div class="text-xs text-gray-500">{{ 'Storage' }}</div>
						<div class="text-sm font-medium">
							{{ storageLabel }}
						</div>
						<div v-if="storagePercent != null" class="mt-2">
							<div class="h-2 w-full overflow-hidden rounded-full bg-gray-200">
								<div
									class="h-full rounded-full transition-all"
									:class="storagePercent > 90 ? 'bg-red-500' : storagePercent > 70 ? 'bg-yellow-500' : 'bg-green-500'"
									:style="{ width: `${storagePercent}%` }"
								></div>
							</div>
						</div>
					</div>
				</div>

				<!-- Notification Settings -->
				<div class="rounded-lg border bg-white p-4">
					<div class="mb-3 text-sm font-medium text-gray-700">{{ 'Notification Settings' }}</div>
					<div class="grid grid-cols-2 gap-4 sm:grid-cols-3 text-sm">
						<div>
							<div class="text-xs text-gray-500">{{ 'Auto Backup' }}</div>
							<div class="font-medium">{{ portal?.auto_backup_enabled ? 'Enabled' : 'Disabled' }}</div>
						</div>
						<div>
							<div class="text-xs text-gray-500">{{ 'Backup Schedule' }}</div>
							<div>{{ portal?.backup_schedule || '-' }}</div>
						</div>
						<div>
							<div class="text-xs text-gray-500">{{ 'Backup Time' }}</div>
							<div>{{ portal?.backup_time || '-' }}</div>
						</div>
						<div>
							<div class="text-xs text-gray-500">{{ 'Alert Emails' }}</div>
							<div class="break-all">{{ portal?.alert_emails || '-' }}</div>
						</div>
						<div>
							<div class="text-xs text-gray-500">{{ 'Webhook URL' }}</div>
							<div class="break-all font-mono text-xs">{{ portal?.webhook_url || '-' }}</div>
						</div>
					</div>
				</div>
			</div>

			<!-- Tab: Jobs -->
			<div v-if="activeTab === 'jobs'">
				<div v-if="!portalJobs.length" class="py-8 text-center text-sm text-gray-400">
					{{ 'No backup jobs found' }}
				</div>
				<div v-else class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b text-left text-gray-500">
								<th class="py-2 pr-3 text-xs">{{ 'Job Title' }}</th>
								<th class="py-2 pr-3 text-xs">{{ 'Type' }}</th>
								<th class="py-2 pr-3 text-xs">{{ 'Source Server' }}</th>
								<th class="py-2 pr-3 text-xs">{{ 'Dest Server' }}</th>
								<th class="py-2 pr-3 text-xs">{{ 'Schedule' }}</th>
								<th class="py-2 pr-3 text-xs">{{ 'Last Run' }}</th>
								<th class="py-2 text-xs">{{ 'Success %' }}</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="job in portalJobs"
								:key="job.name"
								class="cursor-pointer border-b last:border-0 hover:bg-gray-50"
								@click="openJobDetail(job)"
							>
								<td class="py-2 pr-3 font-medium">{{ job.job_title || job.name }}</td>
								<td class="py-2 pr-3">{{ job.job_type || '-' }}</td>
								<td class="py-2 pr-3">{{ job.source_server || '-' }}</td>
								<td class="py-2 pr-3">{{ job.destination_server || '-' }}</td>
								<td class="py-2 pr-3">{{ job.schedule_type || '-' }}</td>
								<td class="py-2 pr-3">
									<Badge v-if="job.last_run_status" :label="job.last_run_status" size="sm" />
									<span v-else class="text-gray-400">{{ 'Never' }}</span>
								</td>
								<td class="py-2">{{ job.success_rate != null ? `${Math.round(job.success_rate)}%` : '-' }}</td>
							</tr>
						</tbody>
					</table>
				</div>

				<!-- Job Detail Dialog -->
				<Dialog v-model="jobDialogOpen" :options="{ title: selectedJob?.job_title || 'Job Details', size: 'xl' }">
					<template #body-content>
						<div v-if="selectedJob" class="space-y-3 text-sm">
							<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
								<div>
									<div class="text-xs text-gray-500">{{ 'Job Title' }}</div>
									<div class="font-medium">{{ selectedJob.job_title || '-' }}</div>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ 'Job Type' }}</div>
									<div>{{ selectedJob.job_type || '-' }}</div>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ 'Enabled' }}</div>
									<div>{{ selectedJob.enabled ? 'Yes' : 'No' }}</div>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ 'Priority' }}</div>
									<div>{{ selectedJob.priority || '-' }}</div>
								</div>
							</div>
							<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
								<div>
									<div class="text-xs text-gray-500">{{ 'Source Server' }}</div>
									<div>{{ selectedJob.source_server || '-' }}</div>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ 'Destination Server' }}</div>
									<div>{{ selectedJob.destination_server || '-' }}</div>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ 'Schedule' }}</div>
									<div>{{ selectedJob.schedule_type || '-' }}</div>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ 'Compression' }}</div>
									<div>{{ selectedJob.compression_level || '-' }}</div>
								</div>
							</div>
							<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
								<div>
									<div class="text-xs text-gray-500">{{ 'Total Runs' }}</div>
									<div>{{ selectedJob.total_runs || 0 }}</div>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ 'Success Rate' }}</div>
									<div>{{ selectedJob.success_rate != null ? `${Math.round(selectedJob.success_rate)}%` : '-' }}</div>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ 'Last Run On' }}</div>
									<div>{{ formatDate(selectedJob.last_run_on) }}</div>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ 'Last Run Status' }}</div>
									<Badge v-if="selectedJob.last_run_status" :label="selectedJob.last_run_status" />
									<span v-else>-</span>
								</div>
							</div>
							<div v-if="selectedJob.description" class="rounded border p-2">
								<div class="text-xs text-gray-500">{{ 'Description' }}</div>
								<div>{{ selectedJob.description }}</div>
							</div>
						</div>
					</template>
					<template #actions>
						<Button @click="jobDialogOpen = false">{{ 'Close' }}</Button>
					</template>
				</Dialog>
			</div>

			<!-- Tab: History -->
			<div v-if="activeTab === 'history'">
				<div v-if="!portalLogs.length" class="py-8 text-center text-sm text-gray-400">
					{{ 'No backup history found' }}
				</div>
				<div v-else class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b text-left text-gray-500">
								<th class="py-2 pr-3 text-xs">{{ 'Name' }}</th>
								<th class="py-2 pr-3 text-xs">{{ 'Mode' }}</th>
								<th class="py-2 pr-3 text-xs">{{ 'Status' }}</th>
								<th class="py-2 pr-3 text-xs">{{ 'Started' }}</th>
								<th class="py-2 pr-3 text-xs">{{ 'Duration' }}</th>
								<th class="py-2 pr-3 text-xs">{{ 'Files' }}</th>
								<th class="py-2 pr-3 text-xs">{{ 'Size MB' }}</th>
								<th class="py-2 text-xs">{{ 'Compression' }}</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="log in portalLogs"
								:key="log.name"
								class="cursor-pointer border-b last:border-0 hover:bg-gray-50"
								@click="openLogDetail(log)"
							>
								<td class="py-2 pr-3 font-mono text-xs">{{ log.name }}</td>
								<td class="py-2 pr-3">{{ log.mode || '-' }}</td>
								<td class="py-2 pr-3">
									<Badge v-if="log.status" :label="log.status" size="sm" />
									<span v-else>-</span>
								</td>
								<td class="py-2 pr-3 text-xs">{{ formatDate(log.started_at || log.creation) }}</td>
								<td class="py-2 pr-3">{{ formatDuration(log.duration_seconds) }}</td>
								<td class="py-2 pr-3">{{ log.files_count ?? '-' }}</td>
								<td class="py-2 pr-3">{{ log.data_size_mb != null ? log.data_size_mb : '-' }}</td>
								<td class="py-2">{{ log.compression_ratio != null ? `${log.compression_ratio}x` : '-' }}</td>
							</tr>
						</tbody>
					</table>
				</div>

				<!-- Log Detail Dialog -->
				<Dialog v-model="logDialogOpen" :options="{ title: selectedLog?.name || 'Log Details', size: 'xl' }">
					<template #body-content>
						<div v-if="selectedLog" class="space-y-3 text-sm">
							<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
								<div>
									<div class="text-xs text-gray-500">{{ 'Name' }}</div>
									<div class="font-mono text-xs">{{ selectedLog.name }}</div>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ 'Mode' }}</div>
									<div>{{ selectedLog.mode || '-' }}</div>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ 'Status' }}</div>
									<Badge v-if="selectedLog.status" :label="selectedLog.status" />
									<span v-else>-</span>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ 'Duration' }}</div>
									<div>{{ formatDuration(selectedLog.duration_seconds) }}</div>
								</div>
							</div>
							<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
								<div>
									<div class="text-xs text-gray-500">{{ 'Started' }}</div>
									<div>{{ formatDate(selectedLog.started_at || selectedLog.creation) }}</div>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ 'Files' }}</div>
									<div>{{ selectedLog.files_count ?? '-' }}</div>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ 'Size' }}</div>
									<div>{{ selectedLog.data_size_mb != null ? `${selectedLog.data_size_mb} MB` : '-' }}</div>
								</div>
								<div>
									<div class="text-xs text-gray-500">{{ 'Compression Ratio' }}</div>
									<div>{{ selectedLog.compression_ratio != null ? `${selectedLog.compression_ratio}x` : '-' }}</div>
								</div>
							</div>
							<!-- Raw Output -->
							<div v-if="selectedLog.output || selectedLog.error_message">
								<div class="mb-1 text-xs text-gray-500">{{ 'Raw Output' }}</div>
								<pre
									class="max-h-64 overflow-auto rounded bg-gray-900 p-3 text-xs text-green-400"
									style="white-space: pre-wrap; word-break: break-all;"
								>{{ selectedLog.output || selectedLog.error_message || '-' }}</pre>
							</div>
						</div>
					</template>
					<template #actions>
						<Button @click="logDialogOpen = false">{{ 'Close' }}</Button>
					</template>
				</Dialog>
			</div>

			<!-- Tab: Servers -->
			<div v-if="activeTab === 'servers'">
				<div v-if="!portalServers.length" class="py-8 text-center text-sm text-gray-400">
					{{ 'No servers associated with this client' }}
				</div>
				<div v-else class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b text-left text-gray-500">
								<th class="py-2 pr-3 text-xs">{{ 'Server Name' }}</th>
								<th class="py-2 pr-3 text-xs">{{ 'Type' }}</th>
								<th class="py-2 pr-3 text-xs">{{ 'Host' }}</th>
								<th class="py-2 pr-3 text-xs">{{ 'Storage Type' }}</th>
								<th class="py-2 pr-3 text-xs">{{ 'Status' }}</th>
								<th class="py-2 text-xs">{{ 'Enabled' }}</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="srv in portalServers"
								:key="srv.name"
								class="border-b last:border-0"
							>
								<td class="py-2 pr-3 font-medium">{{ srv.server_name || srv.name }}</td>
								<td class="py-2 pr-3">{{ srv.server_type || '-' }}</td>
								<td class="py-2 pr-3 font-mono text-xs">{{ srv.host || '-' }}</td>
								<td class="py-2 pr-3">{{ srv.storage_type || '-' }}</td>
								<td class="py-2 pr-3">
									<Badge v-if="srv.connection_status" :label="srv.connection_status" size="sm" />
									<span v-else>-</span>
								</td>
								<td class="py-2">{{ srv.enabled ? 'Yes' : 'No' }}</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>

			<!-- Tab: Alerts -->
			<div v-if="activeTab === 'alerts'">
				<!-- Alert Rules -->
				<div class="mb-6">
					<h3 class="mb-3 text-sm font-medium text-gray-700">{{ 'Alert Rules' }}</h3>
					<div v-if="!portalAlertRules.length" class="py-4 text-center text-sm text-gray-400">
						{{ 'No alert rules configured' }}
					</div>
					<div v-else class="overflow-x-auto">
						<table class="w-full text-sm">
							<thead>
								<tr class="border-b text-left text-gray-500">
									<th class="py-2 pr-3 text-xs">{{ 'Rule Name' }}</th>
									<th class="py-2 pr-3 text-xs">{{ 'Condition' }}</th>
									<th class="py-2 pr-3 text-xs">{{ 'Severity' }}</th>
									<th class="py-2 pr-3 text-xs">{{ 'Channel' }}</th>
									<th class="py-2 text-xs">{{ 'Enabled' }}</th>
								</tr>
							</thead>
							<tbody>
								<tr
									v-for="rule in portalAlertRules"
									:key="rule.name"
									class="border-b last:border-0"
								>
									<td class="py-2 pr-3 font-medium">{{ rule.rule_name || rule.name }}</td>
									<td class="py-2 pr-3">{{ rule.condition || '-' }}</td>
									<td class="py-2 pr-3">
										<Badge v-if="rule.severity" :label="rule.severity" size="sm" />
										<span v-else>-</span>
									</td>
									<td class="py-2 pr-3">{{ rule.channel || '-' }}</td>
									<td class="py-2">{{ rule.enabled ? 'Yes' : 'No' }}</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>

				<!-- Triggered Alerts -->
				<div>
					<h3 class="mb-3 text-sm font-medium text-gray-700">{{ 'Triggered Alerts' }}</h3>
					<div v-if="!portalTriggeredAlerts.length" class="py-4 text-center text-sm text-gray-400">
						{{ 'No triggered alerts' }}
					</div>
					<div v-else class="overflow-x-auto">
						<table class="w-full text-sm">
							<thead>
								<tr class="border-b text-left text-gray-500">
									<th class="py-2 pr-3 text-xs">{{ 'Alert' }}</th>
									<th class="py-2 pr-3 text-xs">{{ 'Rule' }}</th>
									<th class="py-2 pr-3 text-xs">{{ 'Severity' }}</th>
									<th class="py-2 pr-3 text-xs">{{ 'Triggered At' }}</th>
									<th class="py-2 pr-3 text-xs">{{ 'Status' }}</th>
									<th class="py-2 text-xs">{{ 'Message' }}</th>
								</tr>
							</thead>
							<tbody>
								<tr
									v-for="alert in portalTriggeredAlerts"
									:key="alert.name"
									class="border-b last:border-0"
								>
									<td class="py-2 pr-3 font-mono text-xs">{{ alert.name }}</td>
									<td class="py-2 pr-3">{{ alert.rule_name || alert.alert_rule || '-' }}</td>
									<td class="py-2 pr-3">
										<Badge v-if="alert.severity" :label="alert.severity" size="sm" />
										<span v-else>-</span>
									</td>
									<td class="py-2 pr-3 text-xs">{{ formatDate(alert.triggered_at || alert.creation) }}</td>
									<td class="py-2 pr-3">
										<Badge v-if="alert.status" :label="alert.status" size="sm" />
										<span v-else>-</span>
									</td>
									<td class="py-2 max-w-[300px] truncate">{{ alert.message || '-' }}</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script>
import { Button, Dialog, Badge } from 'frappe-ui';
import { date } from '../../utils/format';

const BASE_API = 'daman_backup.daman_backup.press_api';

async function call(method, args = {}) {
	const res = await fetch(`/api/method/${method}`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			'X-Frappe-CSRF-Token': window.csrf_token || '',
		},
		body: JSON.stringify(args),
	});
	if (!res.ok) throw new Error(`HTTP ${res.status}`);
	const data = await res.json();
	if (data.exc) {
		let msg = 'Unknown error';
		try { msg = JSON.parse(data.exc)[0]; } catch (e) { /* ignore */ }
		throw new Error(msg);
	}
	return data.message || data;
}

export default {
	name: 'BackupClientDetail',
	components: { Button, Dialog, Badge },
	props: {
		clientName: {
			type: String,
			required: true,
		},
	},
	data() {
		return {
			loading: true,
			error: null,
			portal: null,
			activeTab: 'overview',
			jobDialogOpen: false,
			selectedJob: null,
			logDialogOpen: false,
			selectedLog: null,
		};
	},
	computed: {
		tabs() {
			return [
				{ key: 'overview', label: 'Overview' },
				{ key: 'jobs', label: 'Jobs' },
				{ key: 'history', label: 'History' },
				{ key: 'servers', label: 'Servers' },
				{ key: 'alerts', label: 'Alerts' },
			];
		},
		portalJobs() {
			return this.portal?.jobs || [];
		},
		portalLogs() {
			return this.portal?.logs || [];
		},
		portalServers() {
			return this.portal?.servers || [];
		},
		portalAlertRules() {
			return this.portal?.alert_rules || [];
		},
		portalTriggeredAlerts() {
			return this.portal?.triggered_alerts || [];
		},
		storagePercent() {
			const used = parseFloat(this.portal?.storage_used_gb) || 0;
			const allowed = parseFloat(this.portal?.storage_allowed_gb) || 0;
			if (!allowed) return null;
			return Math.min((used / allowed) * 100, 100);
		},
		storageLabel() {
			const used = parseFloat(this.portal?.storage_used_gb) || 0;
			const allowed = parseFloat(this.portal?.storage_allowed_gb) || 0;
			if (!used && !allowed) return '-';
			return `${used.toFixed(1)} / ${allowed.toFixed(1)} GB`;
		},
	},
	mounted() {
		this.fetchPortal();
	},
	methods: {
		async fetchPortal() {
			this.loading = true;
			this.error = null;
			try {
				this.portal = await call(`${BASE_API}.get_client_portal`, {
					client_name: this.clientName,
				});
			} catch (e) {
				this.error = `${'Failed to load client details'}: ${e.message}`;
			} finally {
				this.loading = false;
			}
		},
		formatDate(value) {
			if (!value) return '-';
			return date(value, 'lll');
		},
		formatDuration(seconds) {
			if (!seconds) return '-';
			if (seconds < 60) return `${seconds}s`;
			if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
			const h = Math.floor(seconds / 3600);
			const m = Math.floor((seconds % 3600) / 60);
			return `${h}h ${m}m`;
		},
		healthTheme(status) {
			const map = { Healthy: 'green', Warning: 'orange', Critical: 'red', Unknown: 'gray' };
			return map[status] || 'gray';
		},
		statusTheme(status) {
			const map = { Active: 'green', Deactivate: 'red', Hold: 'orange' };
			return map[status] || 'gray';
		},
		successRateColor(rate) {
			if (rate == null) return '';
			if (rate >= 90) return 'text-green-600';
			if (rate >= 70) return 'text-yellow-600';
			return 'text-red-600';
		},
		openJobDetail(job) {
			this.selectedJob = job;
			this.jobDialogOpen = true;
		},
		openLogDetail(log) {
			this.selectedLog = log;
			this.logDialogOpen = true;
		},
	},
};
</script>
