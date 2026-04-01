<template>
	<div class="mx-auto max-w-4xl space-y-4 p-4">

		<!-- Status Cards -->
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
					<p class="mt-1 text-sm text-gray-400">Clears Redis + assets</p>
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

		<!-- Quick Actions -->
		<div class="flex flex-wrap gap-3">

			<!-- VS Code -->
			<a
				href="https://code.sandbox.mvpstorm.com"
				target="_blank"
				class="flex min-w-[180px] flex-1 items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:border-blue-400 hover:text-blue-600"
			>
				<svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
					<path d="M16.5 3L21 7.5 9 19.5 3 15l13.5-12z" />
					<path d="M12 7.5L16.5 12" />
					<path d="M3 15l4.5-4.5" />
				</svg>
				<span>
					<span class="block text-sm font-semibold">Open VS Code</span>
					<span class="block text-xs text-gray-400">code.sandbox.mvpstorm.com</span>
				</span>
				<svg class="ml-auto h-3.5 w-3.5 text-gray-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
					<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
					<polyline points="15 3 21 3 21 9" />
					<line x1="10" y1="14" x2="21" y2="3" />
				</svg>
			</a>

			<!-- Restart Bench -->
			<button
				class="flex min-w-[180px] flex-1 items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:border-orange-400 hover:text-orange-600"
				:class="{ 'cursor-not-allowed opacity-60': restartLoading }"
				@click="restartBench"
			>
				<svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
					<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
					<path d="M3 3v5h5" />
				</svg>
				<span>
					<span class="block text-sm font-semibold">{{ restartLoading ? 'Restarting…' : 'Restart Bench' }}</span>
					<span class="block text-xs text-gray-400">Restart all bench workers</span>
				</span>
			</button>

		</div>

		<!-- App Git Status -->
		<div class="rounded-lg border border-gray-200 bg-white shadow-sm">
			<div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
				<div class="flex items-center gap-2">
					<p class="text-sm font-semibold">App Status</p>
					<span
						v-if="appsNeedingPush > 0"
						class="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700"
					>
						{{ appsNeedingPush }} need push
					</span>
				</div>
				<div class="flex items-center gap-2">
					<span class="text-xs text-gray-400">{{ gitStatusAge }}</span>
					<Button size="sm" variant="ghost" :loading="gitStatusLoading" @click="loadGitStatus">
						Refresh
					</Button>
				</div>
			</div>

			<!-- Loading skeleton -->
			<div v-if="gitStatusLoading && !appGitStatus.length" class="space-y-2 p-4">
				<div v-for="i in 3" :key="i" class="h-9 animate-pulse rounded bg-gray-100"></div>
			</div>

			<!-- Empty -->
			<div v-else-if="!appGitStatus.length" class="p-4 text-center text-sm text-gray-400">
				No apps found or bench unavailable
			</div>

			<!-- Table -->
			<table v-else class="w-full text-sm">
				<thead class="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
					<tr>
						<th class="px-4 py-2 text-left">App</th>
						<th class="px-4 py-2 text-left">Branch</th>
						<th class="px-4 py-2 text-left">Status</th>
						<th class="px-4 py-2 text-left">Last Commit</th>
						<th class="px-4 py-2 text-right"></th>
					</tr>
				</thead>
				<tbody>
					<template v-for="item in appGitStatus" :key="item.app">
						<tr
							:class="{ 'bg-blue-50': openPushApp === item.app }"
							class="border-b border-gray-50 last:border-0"
						>
							<td class="px-4 py-2.5 font-medium">{{ item.app }}</td>
							<td class="px-4 py-2.5">
								<code class="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">{{ item.branch }}</code>
							</td>
							<td class="px-4 py-2.5">
								<div class="flex flex-wrap gap-1">
									<span
										v-if="item.ahead > 0"
										class="inline-flex items-center gap-1 rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-semibold text-yellow-700"
									>
										↑ {{ item.ahead }} ahead
									</span>
									<span
										v-if="item.dirty > 0"
										class="inline-flex items-center gap-1 rounded-full bg-orange-100 px-2 py-0.5 text-xs font-semibold text-orange-600"
									>
										● {{ item.dirty }} dirty
									</span>
									<span
										v-if="item.ahead === 0 && item.dirty === 0"
										class="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700"
									>
										✓ Clean
									</span>
								</div>
							</td>
							<td class="max-w-[180px] truncate px-4 py-2.5 text-xs text-gray-500">{{ item.last_msg }}</td>
							<td class="px-4 py-2.5 text-right">
								<Button
									v-if="item.ahead > 0 || item.dirty > 0"
									size="sm"
									variant="outline"
									@click="togglePushRow(item.app)"
								>
									{{ openPushApp === item.app ? 'Cancel' : 'Push ↓' }}
								</Button>
							</td>
						</tr>
						<!-- Inline push form -->
						<tr v-if="openPushApp === item.app" :key="item.app + '-push'">
							<td colspan="5" class="border-b border-blue-100 bg-blue-50 px-4 py-3">
								<div class="flex items-end gap-2">
									<div class="min-w-0 flex-1">
										<label class="mb-1 block text-xs font-medium text-gray-600">Commit message</label>
										<input
											v-model="pushMessages[item.app]"
											type="text"
											placeholder="WIP"
											class="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
										/>
									</div>
									<Button
										size="sm"
										variant="solid"
										:loading="pushingApp === item.app"
										@click="doPush(item.app)"
									>
										Push to GitHub
									</Button>
								</div>
								<pre
									v-if="pushOutputs[item.app]"
									class="mt-2 whitespace-pre-wrap rounded bg-gray-900 p-2 text-xs leading-relaxed text-green-300"
								>{{ pushOutputs[item.app] }}</pre>
							</td>
						</tr>
					</template>
				</tbody>
			</table>
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
			restartLoading: false,
			statusLoading: false,
			errorsLoading: false,
			gitStatusLoading: false,
			schedulerEnabled: true,
			migrationData: null,
			errorList: [],
			appGitStatus: [],
			gitStatusAge: '',
			openPushApp: null,
			pushMessages: {},
			pushOutputs: {},
			pushingApp: null,
		};
	},
	computed: {
		$site() {
			return getCachedDocumentResource('Site', this.site);
		},
		devModeOn() {
			// Dev tab only renders when bench is_development_bench=1,
			// so if we're here, dev mode is already on.
			// The field lives on Bench doc, not Site doc.
			return true;
		},
		migrationLabel() {
			if (!this.migrationData?.last_run) return 'Never';
			return 'Last: ' + this.relativeTime(this.migrationData.last_run);
		},
		appsNeedingPush() {
			return this.appGitStatus.filter(a => a.ahead > 0 || a.dirty > 0).length;
		},
	},
	watch: {
		'$site.doc.bench': {
			immediate: true,
			handler(benchName) {
				if (benchName) this.loadGitStatus();
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
		async loadGitStatus() {
			const benchName = this.$site?.doc?.bench;
			if (!benchName) return;
			this.gitStatusLoading = true;
			try {
				const result = await call(
					'press.press.doctype.bench.bench_dev_overview.get_app_git_status',
					{ bench_name: benchName },
				);
				this.appGitStatus = Array.isArray(result) ? result : [];
				this.gitStatusAge = 'Updated just now';
				this.appGitStatus.forEach(a => {
					if (!this.pushMessages[a.app]) this.pushMessages[a.app] = 'WIP';
				});
			} catch (e) {
				this.appGitStatus = [];
			} finally {
				this.gitStatusLoading = false;
			}
		},
		togglePushRow(app) {
			this.openPushApp = this.openPushApp === app ? null : app;
			this.pushOutputs = { ...this.pushOutputs, [app]: '' };
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
		async restartBench() {
			const benchName = this.$site?.doc?.bench;
			if (!benchName || this.restartLoading) return;
			this.restartLoading = true;
			try {
				await call(
					'press.press.doctype.bench.bench_dev_overview.restart_bench_for_site',
					{ bench_name: benchName },
				);
				toast.success('Bench restarted');
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to restart bench');
			} finally {
				this.restartLoading = false;
			}
		},
		async doPush(app) {
			const benchName = this.$site?.doc?.bench;
			if (!benchName) return;
			this.pushingApp = app;
			this.pushOutputs = { ...this.pushOutputs, [app]: '' };
			try {
				const result = await call(
					'press.press.doctype.bench.bench_dev_overview.push_app_to_github',
					{ bench_name: benchName, app, message: this.pushMessages[app] || 'WIP' },
				);
				this.pushOutputs = { ...this.pushOutputs, [app]: result?.output || 'Done' };
				toast.success('Pushed to GitHub');
				this.loadGitStatus();
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Push failed');
			} finally {
				this.pushingApp = null;
			}
		},
		relativeTime(ts) {
			if (!ts) return '';
			const diffMin = Math.floor((new Date() - new Date(ts)) / 60000);
			if (diffMin < 1) return 'just now';
			if (diffMin < 60) return `${diffMin}m ago`;
			const h = Math.floor(diffMin / 60);
			return h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`;
		},
	},
};
</script>
