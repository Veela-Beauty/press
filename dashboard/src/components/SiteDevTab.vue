<template>
	<div class="mx-auto max-w-4xl space-y-4 p-4">

		<!-- Status-Action Cards -->
		<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">

			<!-- Developer Mode -->
			<div class="flex flex-col justify-between rounded-lg border border-gray-200 p-4">
				<div>
					<p class="text-xs font-medium uppercase tracking-wide text-gray-500">Developer Mode</p>
					<div class="mt-1 flex items-center gap-1.5">
						<span
							:class="devModeOn ? 'bg-green-500' : 'bg-gray-300'"
							class="inline-block h-2 w-2 rounded-full"
						></span>
						<span class="text-sm font-medium">{{ devModeOn ? 'Enabled' : 'Disabled' }}</span>
					</div>
				</div>
				<Button
					class="mt-3 w-full"
					size="sm"
					:variant="devModeOn ? 'outline' : 'solid'"
					:loading="devModeLoading"
					@click="toggleDevMode"
				>
					{{ devModeOn ? 'Disable Dev Mode' : 'Enable Dev Mode' }}
				</Button>
			</div>

			<!-- Scheduler -->
			<div class="flex flex-col justify-between rounded-lg border border-gray-200 p-4">
				<div>
					<p class="text-xs font-medium uppercase tracking-wide text-gray-500">Scheduler</p>
					<div class="mt-1 flex items-center gap-1.5">
						<span
							:class="schedulerEnabled ? 'bg-green-500' : 'bg-yellow-400'"
							class="inline-block h-2 w-2 rounded-full"
						></span>
						<span class="text-sm font-medium">
							{{ statusLoading ? '…' : (schedulerEnabled ? 'Running' : 'Paused') }}
						</span>
					</div>
				</div>
				<p class="mt-3 text-xs text-gray-400">Read-only</p>
			</div>

			<!-- Migration -->
			<div class="flex flex-col justify-between rounded-lg border border-gray-200 p-4">
				<div>
					<p class="text-xs font-medium uppercase tracking-wide text-gray-500">Migration</p>
					<p class="mt-1 text-sm font-medium">
						{{ statusLoading ? '…' : migrationLabel }}
					</p>
				</div>
				<Button
					class="mt-3 w-full"
					size="sm"
					variant="outline"
					:loading="migrateLoading"
					@click="triggerMigrate"
				>
					Migrate Now
				</Button>
			</div>

			<!-- Cache -->
			<div class="flex flex-col justify-between rounded-lg border border-gray-200 p-4">
				<div>
					<p class="text-xs font-medium uppercase tracking-wide text-gray-500">Cache</p>
					<p class="mt-1 text-sm text-gray-400">—</p>
				</div>
				<Button
					class="mt-3 w-full"
					size="sm"
					variant="outline"
					:loading="clearCacheLoading"
					@click="triggerClearCache"
				>
					Clear Cache
				</Button>
			</div>

		</div>

		<!-- Push to GitHub -->
		<div class="rounded-lg border border-gray-200">
			<div class="flex items-center justify-between px-4 py-3">
				<p class="text-sm font-medium text-gray-700">Push to GitHub</p>
				<Button size="sm" variant="outline" @click="showPushDialog = !showPushDialog">
					{{ showPushDialog ? 'Cancel' : 'Push to GitHub' }}
				</Button>
			</div>

			<!-- Inline push form -->
			<div v-if="showPushDialog" class="border-t border-gray-100 bg-gray-50 px-4 py-3">
				<div class="flex items-end gap-2">
					<div class="min-w-0 flex-1">
						<label class="mb-1 block text-xs font-medium text-gray-600">App</label>
						<select
							v-model="pushApp"
							class="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
						>
							<option value="">Select app…</option>
							<option v-for="app in benchApps" :key="app" :value="app">{{ app }}</option>
						</select>
					</div>
					<div class="min-w-0 flex-1">
						<label class="mb-1 block text-xs font-medium text-gray-600">Commit message</label>
						<input
							v-model="pushMessage"
							type="text"
							class="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
							placeholder="WIP"
						/>
					</div>
					<Button
						size="sm"
						variant="solid"
						:loading="pushLoading"
						:disabled="!pushApp"
						@click="doPush"
					>
						Push
					</Button>
				</div>
				<pre
					v-if="pushOutput"
					class="mt-2 whitespace-pre-wrap rounded bg-gray-100 p-2 text-xs leading-relaxed text-gray-700"
				>{{ pushOutput }}</pre>
			</div>
		</div>

		<!-- Recent Errors -->
		<div class="rounded-lg border border-gray-200">
			<div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
				<p class="text-sm font-semibold">Recent Errors</p>
				<Button size="sm" variant="ghost" @click="loadErrors">Refresh</Button>
			</div>
			<div v-if="errorsLoading" class="p-4 text-center text-sm text-gray-400">Loading…</div>
			<div v-else-if="!errorList.length" class="p-4 text-center text-sm text-gray-400">
				No recent errors
			</div>
			<table v-else class="w-full text-sm">
				<thead class="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
					<tr>
						<th class="px-4 py-2 text-left">Time</th>
						<th class="px-4 py-2 text-left">Job Type</th>
						<th class="px-4 py-2 text-left"></th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="err in errorList"
						:key="err.name"
						class="border-b border-gray-50 last:border-0"
					>
						<td class="px-4 py-2 text-gray-500">{{ relativeTime(err.creation) }}</td>
						<td class="px-4 py-2">{{ err.job_type }}</td>
						<td class="px-4 py-2">
							<a
								:href="`/dashboard/sites/${site}/jobs/${err.name}`"
								class="text-blue-600 hover:underline"
							>View</a>
						</td>
					</tr>
				</tbody>
			</table>
		</div>

	</div>
</template>

<script>
import { call, getCachedDocumentResource } from 'frappe-ui';
import { toast } from 'vue-sonner';

export default {
	name: 'SiteDevTab',
	props: {
		site: { type: String, required: true },
	},
	data() {
		return {
			devModeLoading: false,
			migrateLoading: false,
			clearCacheLoading: false,
			statusLoading: false,
			errorsLoading: false,
			schedulerEnabled: true,
			migrationData: null,
			errorList: [],
			showPushDialog: false,
			pushApp: '',
			pushMessage: 'WIP',
			pushLoading: false,
			pushOutput: '',
			benchApps: [],
		};
	},
	computed: {
		$site() {
			return getCachedDocumentResource('Site', this.site);
		},
		devModeOn() {
			return !!this.$site?.doc?.is_development_site;
		},
		migrationLabel() {
			if (!this.migrationData || !this.migrationData.last_run) return 'Never';
			return 'Last: ' + this.relativeTime(this.migrationData.last_run);
		},
	},
	watch: {
		'$site.doc.bench': {
			immediate: true,
			handler(benchName) {
				if (benchName) this.loadBenchApps(benchName);
			},
		},
	},
	mounted() {
		this.loadStatus();
		this.loadErrors();
	},
	methods: {
		async loadStatus() {
			this.statusLoading = true;
			try {
				const [sched, migr] = await Promise.all([
					this.$site.getSchedulerStatus.submit(),
					this.$site.getMigrationStatus.submit(),
				]);
				this.schedulerEnabled = sched?.enabled !== false;
				this.migrationData = migr;
			} catch (e) {
				// Fail silently — status cards show defaults
			} finally {
				this.statusLoading = false;
			}
		},
		async loadErrors() {
			this.errorsLoading = true;
			try {
				const res = await this.$site.getRecentErrors.submit({ limit: 10 });
				this.errorList = res?.errors || [];
			} catch (e) {
				this.errorList = [];
			} finally {
				this.errorsLoading = false;
			}
		},
		async loadBenchApps(benchName) {
			try {
				const result = await call(
					'press.press.doctype.bench.bench_dev_overview.get_bench_app_names',
					{ bench_name: benchName },
				);
				this.benchApps = Array.isArray(result) ? result : [];
			} catch (e) {
				this.benchApps = [];
			}
		},
		async toggleDevMode() {
			const enabling = !this.devModeOn;
			this.devModeLoading = true;
			try {
				await this.$site.setDevelopmentMode.submit({ enable: enabling ? 1 : 0 });
				toast.success(enabling ? 'Developer mode enabled' : 'Developer mode disabled');
				this.$site.reload();
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed');
			} finally {
				this.devModeLoading = false;
			}
		},
		async triggerMigrate() {
			this.migrateLoading = true;
			try {
				await this.$site.migrate.submit();
				toast.success('Migration started');
				this.loadStatus();
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to start migration');
			} finally {
				this.migrateLoading = false;
			}
		},
		async triggerClearCache() {
			this.clearCacheLoading = true;
			try {
				await this.$site.clearSiteCache.submit();
				toast.success('Cache cleared');
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to clear cache');
			} finally {
				this.clearCacheLoading = false;
			}
		},
		async doPush() {
			if (!this.pushApp) return;
			this.pushLoading = true;
			this.pushOutput = '';
			const benchName = this.$site?.doc?.bench;
			try {
				const result = await call(
					'press.press.doctype.bench.bench_dev_overview.push_app_to_github',
					{
						bench_name: benchName,
						app: this.pushApp,
						message: this.pushMessage || 'WIP',
					},
				);
				this.pushOutput = result?.output || 'Done';
				toast.success('Pushed to GitHub');
				this.loadErrors();
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Push failed');
			} finally {
				this.pushLoading = false;
			}
		},
		relativeTime(ts) {
			if (!ts) return '';
			const now = new Date();
			const then = new Date(ts);
			const diffMs = now - then;
			const diffMin = Math.floor(diffMs / 60000);
			if (diffMin < 1) return 'just now';
			if (diffMin < 60) return `${diffMin}m ago`;
			const diffH = Math.floor(diffMin / 60);
			if (diffH < 24) return `${diffH}h ago`;
			return `${Math.floor(diffH / 24)}d ago`;
		},
	},
};
</script>
