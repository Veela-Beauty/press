<template>
	<div class="mx-auto max-w-4xl space-y-4 p-4">

		<!-- 1. Status Cards -->
		<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
			<!-- Developer Mode -->
			<div class="flex flex-col justify-between rounded-lg border border-gray-200 p-4">
				<div>
					<p class="text-xs font-medium uppercase tracking-wide text-gray-500">Developer Mode</p>
					<div class="mt-1 flex items-center gap-1.5">
						<span :class="devModeOn ? 'bg-green-500' : 'bg-gray-300'" class="inline-block h-2 w-2 rounded-full"></span>
						<span class="text-sm font-medium">{{ devModeOn ? 'Enabled' : 'Disabled' }}</span>
					</div>
				</div>
				<Button class="mt-3 w-full" size="sm" :variant="devModeOn ? 'outline' : 'solid'" :loading="devModeLoading" @click="toggleDevMode">
					{{ devModeOn ? 'Disable Dev Mode' : 'Enable Dev Mode' }}
				</Button>
			</div>
			<!-- Scheduler -->
			<div class="flex flex-col justify-between rounded-lg border border-gray-200 p-4">
				<div>
					<p class="text-xs font-medium uppercase tracking-wide text-gray-500">Scheduler</p>
					<div class="mt-1 flex items-center gap-1.5">
						<span :class="schedulerEnabled ? 'bg-green-500' : 'bg-yellow-400'" class="inline-block h-2 w-2 rounded-full"></span>
						<span class="text-sm font-medium">{{ statusLoading ? '…' : (schedulerEnabled ? 'Running' : 'Paused') }}</span>
					</div>
				</div>
				<p class="mt-3 text-xs text-gray-400">Read-only</p>
			</div>
			<!-- Migration -->
			<div class="flex flex-col justify-between rounded-lg border border-gray-200 p-4">
				<div>
					<p class="text-xs font-medium uppercase tracking-wide text-gray-500">Migration</p>
					<p class="mt-1 text-sm font-medium">{{ statusLoading ? '…' : migrationLabel }}</p>
				</div>
				<Button class="mt-3 w-full" size="sm" variant="outline" :loading="migrateLoading" @click="triggerMigrate">Migrate Now</Button>
			</div>
			<!-- Cache -->
			<div class="flex flex-col justify-between rounded-lg border border-gray-200 p-4">
				<div>
					<p class="text-xs font-medium uppercase tracking-wide text-gray-500">Cache</p>
					<p class="mt-1 text-sm text-gray-400">Clears Redis + assets</p>
				</div>
				<Button class="mt-3 w-full" size="sm" variant="outline" :loading="clearCacheLoading" @click="triggerClearCache">Clear Cache</Button>
			</div>
		</div>

		<!-- 2. Quick Actions -->
		<div class="flex flex-wrap gap-3">
			<!-- Code Server (Web VS Code) -->
			<a v-if="codeServer.status === 'Running'" :href="codeServer.url" target="_blank"
				class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm font-medium text-green-700 shadow-sm transition-colors hover:border-green-400">
				<svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
					<path d="M16.5 3L21 7.5 9 19.5 3 15l13.5-12z"/><path d="M12 7.5L16.5 12"/><path d="M3 15l4.5-4.5"/>
				</svg>
				<span>
					<span class="block text-sm font-semibold">Open Code Server</span>
					<span class="block text-xs text-green-500">{{ codeServer.name }} · Running</span>
				</span>
				<svg class="ml-auto h-3.5 w-3.5 text-green-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
					<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
				</svg>
			</a>
			<button v-else-if="codeServer.enabled && !codeServer.exists" @click="launchCodeServer"
				:disabled="codeServerLaunching"
				class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700 shadow-sm transition-colors hover:border-blue-400 disabled:opacity-50">
				<svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
					<path d="M16.5 3L21 7.5 9 19.5 3 15l13.5-12z"/><path d="M12 7.5L16.5 12"/><path d="M3 15l4.5-4.5"/>
				</svg>
				<span>
					<span class="block text-sm font-semibold">{{ codeServerLaunching ? 'Setting up…' : 'Launch Code Server' }}</span>
					<span class="block text-xs text-blue-400">Per-user web VS Code for this bench</span>
				</span>
			</button>
			<div v-else-if="codeServer.exists && codeServer.status === 'Pending'"
				class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm font-medium text-yellow-700">
				<svg class="h-5 w-5 flex-shrink-0 animate-spin" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
					<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>
				</svg>
				<span>
					<span class="block text-sm font-semibold">Code Server Starting…</span>
					<span class="block text-xs text-yellow-500">{{ codeServer.name }}</span>
				</span>
			</div>
			<a v-else :href="webVscodeUrl" target="_blank"
				class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:border-blue-400 hover:text-blue-600">
				<svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
					<path d="M16.5 3L21 7.5 9 19.5 3 15l13.5-12z"/><path d="M12 7.5L16.5 12"/><path d="M3 15l4.5-4.5"/>
				</svg>
				<span>
					<span class="block text-sm font-semibold">Web VS Code</span>
					<span class="block text-xs text-gray-400">Fallback · code.sandbox.mvpstorm.com</span>
				</span>
			</a>
			<!-- Local VS Code (SSH Remote) -->
			<a v-if="devInfo" :href="localVscodeUrl"
				class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:border-purple-400 hover:text-purple-600">
				<svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
					<rect x="2" y="3" width="20" height="18" rx="2"/><path d="M8 10l3 3-3 3"/><line x1="14" y1="16" x2="18" y2="16"/>
				</svg>
				<span>
					<span class="block text-sm font-semibold">Local VS Code</span>
					<span class="block text-xs text-gray-400">SSH Remote → {{ devInfo.server_ip }}:{{ devInfo.ssh_port }}</span>
				</span>
			</a>
			<!-- Restart Bench -->
			<button @click="restartBench"
				class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:border-orange-400 hover:text-orange-600"
				:class="{ 'cursor-not-allowed opacity-60': restartLoading }">
				<svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
					<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>
				</svg>
				<span>
					<span class="block text-sm font-semibold">{{ restartLoading ? 'Restarting…' : 'Restart Bench' }}</span>
					<span class="block text-xs text-gray-400">Restart all bench workers</span>
				</span>
			</button>
		</div>

		<!-- Code Health Dashboard -->
		<div class="rounded-lg border border-gray-200 bg-white shadow-sm">
			<div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
				<p class="text-sm font-semibold">Code Health</p>
				<Button size="sm" :variant="showHealth ? 'solid' : 'outline'" @click="showHealth = !showHealth">
					{{ showHealth ? 'Hide' : 'Show' }} Health Dashboard
				</Button>
			</div>
			<BenchCodeHealth v-if="showHealth && $site?.doc?.bench" :bench-name="$site.doc.bench" />
		</div>

		<!-- 3. App Git Status -->
		<div class="rounded-lg border border-gray-200 bg-white shadow-sm">
			<div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
				<div class="flex items-center gap-2">
					<p class="text-sm font-semibold">App Status</p>
					<span v-if="appsNeedingPush > 0" class="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700">
						{{ appsNeedingPush }} need push
					</span>
				</div>
				<div class="flex items-center gap-2">
					<span class="text-xs text-gray-400">{{ gitStatusAge }}</span>
					<Button size="sm" variant="ghost" :loading="gitStatusLoading" @click="loadGitStatus">Refresh</Button>
					<Button v-if="isDevBench" size="sm" variant="solid" @click="showCreateApp = true">
						<template #prefix><lucide-plus class="h-3.5 w-3.5" /></template>
						New App
					</Button>
				</div>
			</div>
			<div v-if="gitStatusLoading && !appGitStatus.length" class="space-y-2 p-4">
				<div v-for="i in 3" :key="i" class="h-9 animate-pulse rounded bg-gray-100"></div>
			</div>
			<div v-else-if="!appGitStatus.length" class="p-4 text-center text-sm text-gray-400">No apps found or bench unavailable</div>
			<table v-else class="w-full text-sm">
				<thead class="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
					<tr><th class="px-4 py-2 text-left">App</th><th class="px-4 py-2 text-left">Branch</th><th class="px-4 py-2 text-left">Status</th><th class="px-4 py-2 text-left">Last Commit</th><th class="px-4 py-2 text-right"></th></tr>
				</thead>
				<tbody>
					<template v-for="item in appGitStatus" :key="item.app">
						<tr :class="{ 'bg-blue-50': openPushApp === item.app }" class="border-b border-gray-50 last:border-0">
							<td class="px-4 py-2.5 font-medium">
								<div class="flex items-center gap-2">
									<span class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded bg-gray-100 text-[10px] font-bold text-gray-600">{{ item.app.charAt(0).toUpperCase() }}</span>
									{{ item.app }}
								</div>
							</td>
							<td class="px-4 py-2.5"><code class="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">{{ item.branch }}</code></td>
							<td class="px-4 py-2.5">
								<div class="flex flex-wrap gap-1">
									<span v-if="item.ahead > 0" class="inline-flex items-center gap-1 rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-semibold text-yellow-700">↑ {{ item.ahead }} ahead</span>
									<span v-if="item.dirty > 0" class="inline-flex items-center gap-1 rounded-full bg-orange-100 px-2 py-0.5 text-xs font-semibold text-orange-600">● {{ item.dirty }} dirty</span>
									<span v-if="item.ahead === 0 && item.dirty === 0" class="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">✓ Clean</span>
								</div>
							</td>
							<td class="max-w-[180px] truncate px-4 py-2.5 text-xs text-gray-500">{{ item.last_msg }}</td>
							<td class="px-4 py-2.5 text-right">
								<div class="flex justify-end gap-1">
									<Button v-if="item.ahead > 0 || item.dirty > 0" size="sm" variant="outline" @click="togglePushRow(item.app)">
										{{ openPushApp === item.app ? 'Cancel' : 'Push ↓' }}
									</Button>
									<Button v-if="!item.has_remote" size="sm" variant="outline" @click="openInitGithub(item.app)">
										<template #prefix><lucide-github class="h-3.5 w-3.5" /></template>
										GitHub
									</Button>
								</div>
							</td>
						</tr>
						<tr v-if="openPushApp === item.app" :key="item.app + '-push'">
							<td colspan="5" class="border-b border-blue-100 bg-blue-50 px-4 py-3">
								<div class="flex items-end gap-2">
									<div class="min-w-0 flex-1">
										<label class="mb-1 block text-xs font-medium text-gray-600">Commit message</label>
										<input v-model="pushMessages[item.app]" type="text" placeholder="WIP"
											class="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none" />
									</div>
									<Button size="sm" variant="solid" :loading="pushingApp === item.app" @click="doPush(item.app)">Push to GitHub</Button>
								</div>
								<pre v-if="pushOutputs[item.app]" class="mt-2 whitespace-pre-wrap rounded bg-gray-900 p-2 text-xs leading-relaxed text-green-300">{{ pushOutputs[item.app] }}</pre>
							</td>
						</tr>
					</template>
				</tbody>
			</table>
		</div>

		<!-- 4. Dev Tools Quick Launch -->
		<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
			<a v-for="tool in devTools" :key="tool.label" :href="tool.href" target="_blank"
				class="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-colors hover:border-blue-400">
				<p class="text-[11px] font-semibold uppercase tracking-wide text-gray-400">{{ tool.label }}</p>
				<div class="flex items-center gap-2">
					<span :class="tool.iconColor" class="text-lg">{{ tool.icon }}</span>
					<span class="text-sm font-medium text-gray-900">{{ tool.desc }}</span>
				</div>
				<span class="text-xs text-gray-400">Opens in new tab ↗</span>
			</a>
		</div>

		<!-- 5. Inline Console -->
		<div class="rounded-lg border border-gray-200 bg-white shadow-sm">
			<div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
				<div class="flex items-center gap-2">
					<p class="text-sm font-semibold">Console</p>
					<div class="flex overflow-hidden rounded border border-gray-200">
						<button v-for="tab in ['SQL', 'Python']" :key="tab" @click="consoleTab = tab"
							:class="consoleTab === tab ? 'bg-blue-50 text-blue-600' : 'bg-white text-gray-500'"
							class="px-3 py-0.5 text-[11px] font-semibold">{{ tab }}</button>
					</div>
				</div>
				<div class="flex items-center gap-2">
					<label class="flex cursor-pointer items-center gap-1 text-[11px] text-gray-400">
						<input v-model="consoleCommit" type="checkbox" class="accent-blue-600" /> Commit
					</label>
					<button @click="runConsole" :disabled="consoleRunning || !consoleInput.trim()"
						class="inline-flex items-center gap-1.5 rounded-md border border-green-300 bg-green-50 px-3 py-1 text-xs font-semibold text-green-700 transition-colors hover:bg-green-100 disabled:cursor-not-allowed disabled:opacity-40">
						<svg class="h-3 w-3" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
						{{ consoleRunning ? 'Running…' : 'Run' }}
					</button>
				</div>
			</div>
			<textarea v-model="consoleInput" :placeholder="consolePlaceholder"
				class="w-full resize-y border-b border-gray-100 bg-gray-50 px-4 py-3 font-mono text-xs leading-relaxed text-gray-900 outline-none" rows="3"></textarea>
			<div v-if="consoleOutput !== null" class="border-t border-gray-200 bg-gray-50">
				<div class="flex items-center justify-between border-b border-gray-100 px-4 py-1.5">
					<span class="text-[11px] font-semibold text-gray-500">{{ consoleOutputMeta }}</span>
					<button @click="consoleOutput = null" class="text-[11px] text-gray-400 hover:text-gray-600">Clear</button>
				</div>
				<pre class="max-h-[200px] overflow-auto px-4 py-3 font-mono text-[11px] leading-relaxed text-gray-900">{{ consoleOutput }}</pre>
			</div>
		</div>

		<!-- 6. Recent Logs -->
		<div class="rounded-lg border border-gray-200 bg-white shadow-sm">
			<div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
				<div class="flex items-center gap-2">
					<p class="text-sm font-semibold">Recent Logs</p>
					<div class="flex overflow-hidden rounded border border-gray-200">
						<button v-for="f in logFilters" :key="f" @click="logFilter = f"
							:class="logFilter === f ? 'bg-gray-100 text-gray-900' : 'bg-white text-gray-500'"
							class="px-2.5 py-0.5 text-[11px] font-medium capitalize">{{ f }}</button>
					</div>
				</div>
				<Button size="sm" variant="ghost" :loading="logsLoading" @click="loadLogs">Refresh</Button>
			</div>
			<div v-if="logsLoading" class="p-4 text-center text-sm text-gray-400">Loading…</div>
			<div v-else-if="!filteredLogs.length" class="p-4 text-center text-sm text-gray-400">No logs found</div>
			<div v-else class="max-h-[260px] overflow-y-auto">
				<div v-for="(entry, i) in filteredLogs" :key="i" class="flex items-start gap-2.5 border-b border-gray-100 px-4 py-2 last:border-0 hover:bg-gray-50">
					<span :class="logDotColor(entry.level)" class="mt-1.5 inline-block h-1.5 w-1.5 flex-shrink-0 rounded-full"></span>
					<div class="min-w-0 flex-1">
						<div class="flex items-center justify-between gap-2">
							<span :class="logTextColor(entry.level)" class="text-xs font-semibold">{{ entry.source }}</span>
							<span class="flex-shrink-0 text-[10px] text-gray-400">{{ entry.timestamp }}</span>
						</div>
						<p class="truncate font-mono text-[11px] text-gray-500">{{ entry.message }}</p>
					</div>
				</div>
			</div>
		</div>

		<!-- 7. DB Process List -->
		<div class="rounded-lg border border-gray-200 bg-white shadow-sm">
			<div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
				<div class="flex items-center gap-2">
					<p class="text-sm font-semibold">Active DB Processes</p>
					<span v-if="processList.length" class="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">{{ processList.length }} active</span>
				</div>
				<Button size="sm" variant="ghost" :loading="processLoading" @click="loadProcessList">Refresh</Button>
			</div>
			<div v-if="processLoading" class="p-4 text-center text-sm text-gray-400">Loading…</div>
			<div v-else-if="!processList.length" class="p-4 text-center text-sm text-gray-400">No active processes</div>
			<table v-else class="w-full text-xs">
				<thead class="border-b border-gray-100 bg-gray-50 text-[10px] uppercase text-gray-500">
					<tr><th class="px-3 py-1.5 text-left">ID</th><th class="px-3 py-1.5 text-left">User</th><th class="px-3 py-1.5 text-left">Time</th><th class="px-3 py-1.5 text-left">State</th><th class="px-3 py-1.5 text-left">Query</th><th class="px-3 py-1.5 text-right"></th></tr>
				</thead>
				<tbody>
					<tr v-for="proc in processList" :key="proc.id" class="border-b border-gray-50 last:border-0">
						<td class="px-3 py-1.5 font-mono">{{ proc.id }}</td>
						<td class="px-3 py-1.5">{{ proc.user }}</td>
						<td class="px-3 py-1.5" :class="proc.time > 3 ? 'font-semibold text-orange-600' : ''">{{ proc.time }}s</td>
						<td class="px-3 py-1.5">
							<span :class="stateColor(proc.state)" class="rounded-full px-2 py-0.5 text-[10px] font-medium">{{ proc.state }}</span>
						</td>
						<td class="max-w-[200px] truncate px-3 py-1.5 font-mono text-[10px]">{{ proc.query || '—' }}</td>
						<td class="px-3 py-1.5 text-right">
							<button @click="killProcess(proc.id)" :disabled="killingProcess === proc.id"
								class="rounded border border-red-200 px-2 py-0.5 text-[10px] text-red-600 hover:bg-red-50 disabled:opacity-40">
								{{ killingProcess === proc.id ? 'Killed' : 'Kill' }}
							</button>
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<!-- 8. Recent Errors -->
		<div class="rounded-lg border border-gray-200">
			<div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
				<div class="flex items-center gap-2">
					<p class="text-sm font-semibold">Recent Errors</p>
					<span v-if="errorList.length" class="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-600">{{ errorList.length }} failures</span>
				</div>
				<Button size="sm" variant="ghost" @click="loadErrors">Refresh</Button>
			</div>
			<div v-if="errorsLoading" class="p-4 text-center text-sm text-gray-400">Loading…</div>
			<div v-else-if="!errorList.length" class="p-4 text-center text-sm text-gray-400">No recent errors</div>
			<table v-else class="w-full text-sm">
				<thead class="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
					<tr><th class="px-4 py-2 text-left">Time</th><th class="px-4 py-2 text-left">Job Type</th><th class="px-4 py-2 text-left"></th></tr>
				</thead>
				<tbody>
					<tr v-for="err in errorList" :key="err.name" class="border-b border-gray-50 last:border-0">
						<td class="px-4 py-2 text-gray-500">{{ relativeTime(err.creation) }}</td>
						<td class="px-4 py-2">{{ err.job_type }}</td>
						<td class="px-4 py-2"><a :href="`/dashboard/sites/${site}/insights/jobs/${err.name}`" class="text-blue-600 hover:underline">View</a></td>
					</tr>
				</tbody>
			</table>
		</div>

		<!-- Create App Dialog -->
		<Dialog :options="{ title: 'Create App Locally', size: 'md' }" v-model="showCreateApp">
			<template #body-content>
				<div class="space-y-4">
					<FormControl label="App Name" v-model="newAppName" placeholder="my_custom_app"
						description="Lowercase, underscores. Becomes the Python module."
						@input="newAppName = $event.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_')" />
					<FormControl label="App Title" v-model="newAppTitle" placeholder="My Custom App"
						description="Human-readable title." />
					<div v-if="createAppOutput" class="rounded bg-gray-900 p-3">
						<pre class="whitespace-pre-wrap text-xs text-green-300">{{ createAppOutput }}</pre>
					</div>
				</div>
			</template>
			<template #actions>
				<Button variant="solid" :loading="creatingApp" :disabled="!newAppName || !newAppTitle" @click="doCreateApp">
					<template #prefix><lucide-plus class="h-4 w-4" /></template>
					Create App
				</Button>
			</template>
		</Dialog>

		<!-- Push to GitHub Dialog -->
		<Dialog :options="{ title: 'Push to GitHub', size: 'md' }" v-model="showInitGithub">
			<template #body-content>
				<div class="space-y-4">
					<p class="text-sm text-gray-600">Push <strong>{{ initGithubApp }}</strong> to GitHub and register in Press.</p>
					<div v-if="loadingAccounts" class="text-sm text-gray-400">Loading GitHub accounts...</div>
					<div v-else-if="!githubAccounts.length" class="text-sm text-red-600">No GitHub accounts found.</div>
					<div v-else class="flex flex-col gap-2">
						<button v-for="acc in githubAccounts" :key="acc.login"
							class="flex items-center gap-3 rounded-lg border px-3 py-2 text-left text-sm"
							:class="selectedGithubOwner === acc.login ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'"
							@click="selectedGithubOwner = acc.login">
							<img v-if="acc.avatar" :src="acc.avatar" class="h-5 w-5 rounded-full" />
							<span class="font-medium">{{ acc.login }}</span>
						</button>
					</div>
					<div v-if="initGithubOutput" class="rounded bg-gray-900 p-3">
						<pre class="whitespace-pre-wrap text-xs text-green-300">{{ initGithubOutput }}</pre>
					</div>
				</div>
			</template>
			<template #actions>
				<Button variant="solid" :loading="pushingToGithub" :disabled="!selectedGithubOwner" @click="doInitGithub">Push to GitHub</Button>
			</template>
		</Dialog>

	</div>
</template>

<script>
import { call, getCachedDocumentResource } from 'frappe-ui';
import { toast } from 'vue-sonner';
import BenchCodeHealth from './BenchCodeHealth.vue';

const API = 'press.press.doctype.bench.bench_dev_overview';

export default {
	name: 'SiteDevTab',
	props: { site: { type: String, required: true } },
	data() {
		return {
			devModeLoading: false, migrateLoading: false, clearCacheLoading: false,
			restartLoading: false, statusLoading: false, errorsLoading: false,
			gitStatusLoading: false, logsLoading: false, processLoading: false,
			consoleRunning: false,
			schedulerEnabled: true, migrationData: null,
			errorList: [], appGitStatus: [], gitStatusAge: '',
			openPushApp: null, pushMessages: {}, pushOutputs: {}, pushingApp: null,
			// Console
			consoleTab: 'SQL', consoleInput: '', consoleCommit: false,
			consoleOutput: null, consoleOutputMeta: '',
			// Logs
			logFilter: 'all', logEntries: [],
			// Process List
			processList: [], killingProcess: null,
			// Dev info (VS Code links)
			devInfo: null,
			// Code Server
			codeServer: { enabled: false, exists: false, status: null, url: null, name: null },
			codeServerLaunching: false,
			showHealth: false,
			showCreateApp: false, newAppName: '', newAppTitle: '', creatingApp: false, createAppOutput: '',
			showInitGithub: false, initGithubApp: '', githubAccounts: [], loadingAccounts: false,
			selectedGithubOwner: '', pushingToGithub: false, initGithubOutput: '',
		};
	},
	computed: {
		$site() { return getCachedDocumentResource('Site', this.site); },
		isDevBench() { return this.devInfo?.is_development_bench; },
		devModeOn() { return true; },
		migrationLabel() {
			if (!this.migrationData?.last_run) return 'Never';
			return 'Last: ' + this.relativeTime(this.migrationData.last_run);
		},
		appsNeedingPush() { return this.appGitStatus.filter(a => a.ahead > 0 || a.dirty > 0).length; },
		devTools() {
			return [
				{ label: 'Dev Overview', desc: 'All benches at a glance', icon: '⊞', iconColor: 'text-gray-700', href: '/dashboard/dev-overview' },
				{ label: 'Code Health', desc: 'File sizes & quality', icon: '♥', iconColor: 'text-red-500', href: `/dashboard/code-health?bench=${this.$site?.doc?.bench || ''}` },
				{ label: 'DB Analyzer', desc: 'Table schemas & indexes', icon: '⛁', iconColor: 'text-blue-500', href: '/dashboard/database-analyzer' },
				{ label: 'SQL Playground', desc: 'Full SQL editor', icon: '⌨', iconColor: 'text-purple-500', href: '/dashboard/sql-playground' },
				{ label: 'Log Browser', desc: 'All server logs', icon: '📄', iconColor: 'text-green-500', href: '/dashboard/log-browser' },
				{ label: 'Binlog Browser', desc: 'DB change timeline', icon: '⏱', iconColor: 'text-orange-500', href: '/dashboard/binlog-browser' },
			];
		},
		webVscodeUrl() {
			const path = this.devInfo?.bench_path || '/home/frappe/frappe-bench';
			return `https://code.sandbox.mvpstorm.com/?folder=${path}/apps`;
		},
		localVscodeUrl() {
			if (!this.devInfo) return '#';
			const { server_ip, ssh_port, bench_path } = this.devInfo;
			return `vscode://vscode-remote/ssh-remote+frappe@${server_ip}:${ssh_port}${bench_path}/apps`;
		},
		consolePlaceholder() {
			return this.consoleTab === 'SQL' ? 'SELECT name FROM tabUser LIMIT 5' : 'import frappe\nprint(frappe.get_all("User", limit=5))';
		},
		logFilters() { return ['all', 'error', 'info']; },
		filteredLogs() {
			if (this.logFilter === 'all') return this.logEntries;
			return this.logEntries.filter(e => e.level.toUpperCase() === this.logFilter.toUpperCase());
		},
	},
	watch: {
		'$site.doc.bench': { immediate: true, handler(b) { if (b) { this.loadGitStatus(); this.loadLogs(); this.loadProcessList(); this.loadDevInfo(); this.loadCodeServerStatus(); } } },
	},
	mounted() { this.loadStatus(); this.loadErrors(); },
	methods: {
		async loadStatus() {
			this.statusLoading = true;
			try {
				const [sched, migr] = await Promise.all([this.$site.getSchedulerStatus.submit(), this.$site.getMigrationStatus.submit()]);
				this.schedulerEnabled = sched?.enabled !== false;
				this.migrationData = migr;
			} catch (e) { /* defaults */ } finally { this.statusLoading = false; }
		},
		async loadErrors() {
			this.errorsLoading = true;
			try { const res = await this.$site.getRecentErrors.submit({ limit: 10 }); this.errorList = res?.errors || []; }
			catch (e) { this.errorList = []; } finally { this.errorsLoading = false; }
		},
		async loadGitStatus() {
			const b = this.$site?.doc?.bench; if (!b) return;
			this.gitStatusLoading = true;
			try {
				const result = await call(`${API}.get_app_git_status`, { bench_name: b, site_name: this.site });
				this.appGitStatus = Array.isArray(result) ? result : [];
				this.gitStatusAge = 'Updated just now';
				this.appGitStatus.forEach(a => { if (!this.pushMessages[a.app]) this.pushMessages[a.app] = 'WIP'; });
			} catch (e) { this.appGitStatus = []; } finally { this.gitStatusLoading = false; }
		},
		async loadLogs() {
			const b = this.$site?.doc?.bench; if (!b) return;
			this.logsLoading = true;
			try { this.logEntries = await call(`${API}.get_recent_logs`, { bench_name: b }) || []; }
			catch (e) { this.logEntries = []; } finally { this.logsLoading = false; }
		},
		async loadCodeServerStatus() {
			const b = this.$site?.doc?.bench; if (!b) return;
			try {
				const res = await call(`${API}.get_code_server_status`, { bench_name: b });
				this.codeServer = res || this.codeServer;
			} catch (e) { /* keep defaults */ }
		},
		async launchCodeServer() {
			const b = this.$site?.doc?.bench; if (!b) return;
			this.codeServerLaunching = true;
			const subdomain = `code-${b.replace(/[^a-z0-9]/g, '-').slice(0, 30)}`;
			try {
				const res = await call(`${API}.setup_code_server`, { bench_name: b, subdomain });
				if (res?.error) { toast.error(res.error); }
				else { toast.success('Code Server setup started'); this.loadCodeServerStatus(); }
			} catch (e) { toast.error(e?.messages?.join(', ') || 'Failed to setup Code Server'); }
			finally { this.codeServerLaunching = false; }
		},
		async loadDevInfo() {
			const b = this.$site?.doc?.bench; if (!b) return;
			try { this.devInfo = await call(`${API}.get_bench_dev_info`, { bench_name: b }); }
			catch (e) { this.devInfo = null; }
		},
		async loadProcessList() {
			this.processLoading = true;
			try { this.processList = await call(`${API}.get_db_processlist`, { site_name: this.site }) || []; }
			catch (e) { this.processList = []; } finally { this.processLoading = false; }
		},
		async runConsole() {
			this.consoleRunning = true; this.consoleOutput = null;
			const method = this.consoleTab === 'SQL' ? 'run_sql_on_site' : 'run_python_on_site';
			const params = this.consoleTab === 'SQL'
				? { site_name: this.site, query: this.consoleInput, commit: this.consoleCommit }
				: { site_name: this.site, code: this.consoleInput };
			try {
				const res = await call(`${API}.${method}`, params);
				if (res?.error) { toast.error(res.error); this.consoleOutput = res.error; }
				else { this.consoleOutput = res?.output || '(no output)'; }
				this.consoleOutputMeta = `${this.consoleTab} · just now`;
			} catch (e) { toast.error(e?.messages?.join(', ') || 'Execution failed'); }
			finally { this.consoleRunning = false; }
		},
		async killProcess(pid) {
			this.killingProcess = pid;
			try { await call(`${API}.kill_db_process`, { site_name: this.site, process_id: pid }); toast.success(`Process ${pid} killed`); this.loadProcessList(); }
			catch (e) { toast.error('Failed to kill process'); }
			finally { setTimeout(() => { this.killingProcess = null; }, 1500); }
		},
		togglePushRow(app) { this.openPushApp = this.openPushApp === app ? null : app; this.pushOutputs = { ...this.pushOutputs, [app]: '' }; },
		async toggleDevMode() {
			const enabling = !this.devModeOn; this.devModeLoading = true;
			try { await this.$site.setDevelopmentMode.submit({ enable: enabling ? 1 : 0 }); toast.success(enabling ? 'Developer mode enabled' : 'Developer mode disabled'); this.$site.reload(); }
			catch (e) { toast.error(e?.messages?.join(', ') || 'Failed'); } finally { this.devModeLoading = false; }
		},
		async triggerMigrate() {
			this.migrateLoading = true;
			try { await this.$site.migrate.submit(); toast.success('Migration started'); this.loadStatus(); }
			catch (e) { toast.error(e?.messages?.join(', ') || 'Failed to start migration'); } finally { this.migrateLoading = false; }
		},
		async triggerClearCache() {
			this.clearCacheLoading = true;
			try { await this.$site.clearSiteCache.submit(); toast.success('Cache cleared'); }
			catch (e) { toast.error(e?.messages?.join(', ') || 'Failed to clear cache'); } finally { this.clearCacheLoading = false; }
		},
		async restartBench() {
			const b = this.$site?.doc?.bench; if (!b || this.restartLoading) return;
			this.restartLoading = true;
			try { await call(`${API}.restart_bench_for_site`, { bench_name: b }); toast.success('Bench restarted'); }
			catch (e) { toast.error(e?.messages?.join(', ') || 'Failed to restart bench'); } finally { this.restartLoading = false; }
		},
		async doPush(app) {
			const b = this.$site?.doc?.bench; if (!b) return;
			this.pushingApp = app; this.pushOutputs = { ...this.pushOutputs, [app]: '' };
			try {
				const result = await call(`${API}.push_app_to_github`, { bench_name: b, app, message: this.pushMessages[app] || 'WIP' });
				this.pushOutputs = { ...this.pushOutputs, [app]: result?.output || 'Done' }; toast.success('Pushed to GitHub'); this.loadGitStatus();
			} catch (e) { toast.error(e?.messages?.join(', ') || 'Push failed'); } finally { this.pushingApp = null; }
		},
		logDotColor(level) { return level === 'ERROR' ? 'bg-red-500' : level === 'WARNING' ? 'bg-yellow-500' : 'bg-blue-500'; },
		logTextColor(level) { return level === 'ERROR' ? 'text-red-600' : level === 'WARNING' ? 'text-yellow-600' : 'text-blue-600'; },
		stateColor(state) {
			const s = (state || '').toLowerCase();
			if (s === 'execute' || s === 'query') return 'bg-green-100 text-green-700';
			if (s === 'sending data') return 'bg-yellow-100 text-yellow-700';
			return 'bg-gray-100 text-gray-600';
		},
		relativeTime(ts) {
			if (!ts) return '';
			const diffMin = Math.floor((new Date() - new Date(ts)) / 60000);
			if (diffMin < 1) return 'just now';
			if (diffMin < 60) return `${diffMin}m ago`;
			const h = Math.floor(diffMin / 60);
			return h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`;
		},
		async doCreateApp() {
			this.creatingApp = true; this.createAppOutput = '';
			try {
				const b = this.$site?.doc?.bench;
				if (!b) { toast.error('No bench found'); return; }
				const result = await call('press.press.doctype.bench.bench_app_management.create_app_locally', {
					bench_name: b, app_name: this.newAppName, app_title: this.newAppTitle,
				});
				this.createAppOutput = result?.output || 'App created';
				toast.success(`App "${this.newAppTitle}" created`);
				this.loadGitStatus();
				setTimeout(() => { this.showCreateApp = false; this.newAppName = ''; this.newAppTitle = ''; this.createAppOutput = ''; }, 2000);
			} catch (e) { toast.error(e.messages?.[0] || 'Failed'); } finally { this.creatingApp = false; }
		},
		openInitGithub(appName) {
			this.initGithubApp = appName; this.initGithubOutput = ''; this.showInitGithub = true; this.loadingAccounts = true;
			call('press.press.doctype.bench.bench_app_management.get_github_accounts')
				.then(accs => { this.githubAccounts = accs; if (accs.length) this.selectedGithubOwner = accs[0].login; })
				.catch(() => toast.error('Failed to load accounts'))
				.finally(() => { this.loadingAccounts = false; });
		},
		async doInitGithub() {
			this.pushingToGithub = true; this.initGithubOutput = '';
			try {
				const b = this.$site?.doc?.bench;
				const result = await call('press.press.doctype.bench.bench_app_management.init_github_for_app', {
					bench_name: b, app_name: this.initGithubApp, github_owner: this.selectedGithubOwner,
				});
				this.initGithubOutput = result?.push_result?.output || 'Pushed';
				toast.success(`Pushed to ${result.repository_url}`);
				this.loadGitStatus();
			} catch (e) { toast.error(e.messages?.[0] || 'Failed'); } finally { this.pushingToGithub = false; }
		},
	},
};
</script>
