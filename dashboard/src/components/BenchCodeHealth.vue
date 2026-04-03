<template>
	<div class="space-y-4">
		<!-- Header: scan time + buttons -->
		<div class="flex items-center justify-between">
			<span class="text-xs text-gray-400">{{ lastScanAge || 'Not scanned yet' }}</span>
			<div class="flex gap-2">
				<a v-if="summary" :href="'/dashboard/code-health?bench=' + benchName" target="_blank"
					class="rounded border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:border-blue-400 hover:text-blue-600 dark:border-gray-600 dark:text-gray-400">
					Open Full Page ↗
				</a>
				<button @click="scan" :disabled="scanning"
					class="rounded bg-green-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-50">
					{{ scanning ? 'Scanning…' : '⟳ Scan Now' }}
				</button>
			</div>
		</div>

		<!-- Summary cards (6) -->
		<div class="grid grid-cols-6 gap-3" v-if="summary">
			<div class="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
				<p class="text-[10px] font-medium uppercase text-gray-500">Health Score</p>
				<p class="mt-1 text-2xl font-bold" :style="{ color: hc(summary.health_pct) }">{{ summary.health_pct }}%</p>
				<div class="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
					<div class="h-full rounded-full" :style="{ width: summary.health_pct + '%', background: hc(summary.health_pct) }"></div>
				</div>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
				<p class="text-[10px] font-medium uppercase text-gray-500">Files</p>
				<p class="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{{ summary.total_files?.toLocaleString() }}</p>
				<p class="text-[10px] text-gray-400">{{ summary.total_lines?.toLocaleString() }} lines</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
				<p class="text-[10px] font-medium uppercase text-gray-500">Clean</p>
				<p class="mt-1 text-2xl font-bold text-green-500">{{ summary.clean }}</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
				<p class="text-[10px] font-medium uppercase text-gray-500">Warnings</p>
				<p class="mt-1 text-2xl font-bold text-yellow-500">{{ summary.warning }}</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
				<p class="text-[10px] font-medium uppercase text-gray-500">Violations</p>
				<p class="mt-1 text-2xl font-bold text-red-500">{{ summary.violation }}</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
				<p class="text-[10px] font-medium uppercase text-gray-500">Security Alerts</p>
				<p class="mt-1 text-2xl font-bold" :class="summary.security_alerts > 0 ? 'text-red-500' : 'text-green-500'">{{ summary.security_alerts || 0 }}</p>
				<p v-if="summary.security_alerts > 0" class="text-[10px] font-semibold text-red-400">HIGH RISK</p>
			</div>
		</div>

		<!-- Security alert banner -->
		<div v-if="summary && summary.security_alerts > 0"
			class="flex items-start gap-3 rounded-lg border border-red-300 bg-red-50 px-4 py-3 dark:border-red-800 dark:bg-red-900/20">
			<span class="text-lg text-red-500 flex-shrink-0">&#9888;</span>
			<div>
				<p class="text-sm font-semibold text-red-600 dark:text-red-400">{{ summary.security_alerts }} Security Issues Found — HIGH RISK</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Files with potential hardcoded secrets detected. Review the Compliance tab for details.</p>
			</div>
		</div>

		<!-- Tabs -->
		<div class="flex border-b border-gray-200 dark:border-gray-700" v-if="summary">
			<button v-for="t in tabs" :key="t.id" @click="activeTab = t.id"
				class="px-4 py-2 text-sm font-semibold border-b-2 transition-colors"
				:class="activeTab === t.id ? 'text-blue-500 border-blue-500' : 'text-gray-500 border-transparent hover:text-gray-700'">
				{{ t.label }}
			</button>
		</div>

		<!-- Loading -->
		<div v-if="scanning" class="flex h-64 items-center justify-center">
			<div class="text-center text-gray-500">
				<div class="mx-auto mb-3 h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent"></div>
				Scanning {{ scanStep }}…
			</div>
		</div>

		<!-- Not scanned — prominent CTA -->
		<div v-if="!scanning && !summary" class="flex h-64 items-center justify-center">
			<div class="text-center">
				<div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-blue-50 dark:bg-blue-900/20">
					<svg class="h-8 w-8 text-blue-500" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
						<path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0 1 12 2.944a11.955 11.955 0 0 1-8.618 3.04A12.02 12.02 0 0 0 3 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
					</svg>
				</div>
				<h3 class="text-lg font-semibold text-gray-900 dark:text-white">No scan data yet</h3>
				<p class="mt-1 text-sm text-gray-500">Analyze file sizes, code quality, and security patterns</p>
				<button @click="scan" class="mt-4 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700">
					Scan This Bench
				</button>
			</div>
		</div>

		<!-- TAB: Overview -->
		<div v-show="activeTab === 'overview' && !scanning && summary" class="grid grid-cols-2 gap-4">
			<div class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
				<div class="mb-2 flex items-center justify-between">
					<h3 class="text-sm font-semibold text-gray-900 dark:text-white">Overall Score</h3>
					<Badge size="sm" :label="overallScore + '%'" :theme="overallScore >= 80 ? 'green' : overallScore >= 50 ? 'orange' : 'red'" />
				</div>
				<svg ref="radarOverall" width="280" height="280" class="mx-auto block"></svg>
				<div class="mt-2 grid grid-cols-2 gap-x-4 gap-y-0.5 px-4 text-xs">
					<template v-for="(dim, i) in DIMS" :key="dim">
						<span class="text-gray-500">{{ dim }}</span>
						<span class="text-right">
							<span :style="{ color: hc(avgDimScore(i)) }">{{ avgDimScore(i) }}%</span>
							<span class="text-[10px] text-gray-400 ml-1">{{ dimAppCount(i) }}/{{ appScores.length }}</span>
						</span>
					</template>
				</div>
			</div>
			<div class="flex flex-col gap-3">
				<!-- App ranking -->
				<div class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900 flex-1">
					<h3 class="mb-3 text-sm font-semibold text-gray-900 dark:text-white">App Ranking</h3>
					<div class="flex flex-col gap-2">
						<div v-for="(app, i) in sortedApps" :key="app.app" class="flex items-center gap-2">
							<span class="w-4 text-xs text-gray-400">{{ i + 1 }}.</span>
							<span class="flex-1 text-sm font-medium text-gray-900 dark:text-white truncate">{{ app.app }}</span>
							<div class="h-1.5 w-24 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
								<div class="h-full rounded-full" :style="{ width: app.scores.overall + '%', background: hc(app.scores.overall) }"></div>
							</div>
							<Badge size="sm" :label="app.scores.overall + '%'" :theme="app.scores.overall >= 80 ? 'green' : app.scores.overall >= 50 ? 'orange' : 'red'" />
						</div>
					</div>
				</div>
				<!-- Action required -->
				<div class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
					<div class="mb-2 flex items-center justify-between">
						<h3 class="text-sm font-semibold text-gray-900 dark:text-white">Action Required</h3>
						<Badge v-if="actionItems.length" size="sm" :label="actionItems.length + ' items'" theme="red" />
					</div>
					<div class="flex flex-col gap-1.5 text-xs max-h-48 overflow-y-auto">
						<div v-for="(item, i) in actionItems" :key="i"
							class="flex items-center gap-2 rounded px-2 py-1.5"
							:class="item.sev === 'high' ? 'bg-red-50 dark:bg-red-900/10' : 'bg-yellow-50 dark:bg-yellow-900/10'">
							<span :class="item.sev === 'high' ? 'text-red-500' : 'text-yellow-500'" class="font-bold">{{ item.sev === 'high' ? '⚠' : '!' }}</span>
							<span class="flex-1 text-gray-700 dark:text-gray-300">{{ item.text }}</span>
							<Badge v-if="item.sev === 'high'" size="sm" label="HIGH RISK" theme="red" class="ml-auto flex-shrink-0" />
						</div>
						<div v-if="!actionItems.length" class="text-gray-400 py-2 text-center">All clear</div>
					</div>
				</div>
			</div>
		</div>

		<!-- TAB: Health Map -->
		<div v-show="activeTab === 'health' && !scanning && healthData">
			<!-- Mini stat cards -->
			<div class="mb-3 grid grid-cols-4 gap-3" v-if="summary">
				<div class="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
					<p class="text-[10px] font-medium uppercase text-gray-500">Clean Files</p>
					<p class="mt-1 text-xl font-bold text-green-500">{{ summary.clean?.toLocaleString() }}</p>
				</div>
				<div class="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
					<p class="text-[10px] font-medium uppercase text-gray-500">Warnings (500-700)</p>
					<p class="mt-1 text-xl font-bold text-yellow-500">{{ summary.warning }}</p>
				</div>
				<div class="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
					<p class="text-[10px] font-medium uppercase text-gray-500">Violations (&gt;700)</p>
					<p class="mt-1 text-xl font-bold text-red-500">{{ summary.violation }}</p>
				</div>
				<div class="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
					<p class="text-[10px] font-medium uppercase text-gray-500">Health Score</p>
					<p class="mt-1 text-xl font-bold" :style="{ color: hc(summary.health_pct) }">{{ summary.health_pct }}%</p>
					<div class="mt-1 h-1 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
						<div class="h-full rounded-full" :style="{ width: summary.health_pct + '%', background: hc(summary.health_pct) }"></div>
					</div>
				</div>
			</div>
			<!-- Filter toolbar -->
			<div class="mb-3 flex flex-wrap items-center gap-1.5 text-[11px]">
				<span class="text-gray-500 mr-1">Show:</span>
				<button v-for="f in healthFilters" :key="f.key" @click="toggleFilter(f)"
					class="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 font-semibold cursor-pointer"
					:style="{ borderColor: f.color, color: f.color, background: f.active ? f.bg : 'transparent', opacity: f.active ? 1 : 0.35 }">
					<span class="inline-block h-1.5 w-1.5 rounded-full" :style="{ background: f.color }"></span>
					{{ f.label }} {{ f.count }}
				</button>
				<span class="mx-1 h-4 w-px bg-gray-200 dark:bg-gray-700"></span>
				<span class="text-gray-500 mr-1">Type:</span>
				<button v-for="f in extFilters" :key="f.ext" @click="toggleFilter(f)"
					class="rounded-full border px-2 py-0.5 font-semibold cursor-pointer"
					:style="{ borderColor: f.color, color: f.color, background: f.active ? f.bg : 'transparent', opacity: f.active ? 1 : 0.35 }">
					{{ f.ext }} {{ f.count }}
				</button>
				<span class="mx-1 h-4 w-px bg-gray-200 dark:bg-gray-700"></span>
				<span class="text-gray-500">Showing: <strong class="text-gray-900 dark:text-white">{{ visibleFiles }}</strong> / {{ totalFiles }}</span>
			</div>
			<!-- Circle pack -->
			<div class="relative overflow-hidden rounded-lg border border-gray-200 bg-gray-950 dark:border-gray-700" style="height:500px">
				<svg ref="circlePack" class="h-full w-full"></svg>
				<!-- Breadcrumb -->
				<div ref="breadcrumb" class="absolute left-3 top-2 z-10 text-[11px] text-blue-400 cursor-pointer"></div>
				<div ref="tooltip" class="pointer-events-none absolute z-50 hidden rounded-lg border border-gray-600 bg-gray-800 px-3 py-2 text-xs shadow-lg" style="max-width:260px"></div>
				<div ref="sidebar" class="absolute right-0 top-0 z-40 hidden h-full w-64 overflow-y-auto border-l border-gray-700 bg-gray-900 p-3"></div>
				<div class="absolute bottom-3 left-3 flex gap-3 text-[10px] text-gray-500 z-10">
					<span><span class="inline-block h-2 w-2 rounded-full bg-green-500"></span> Clean (&lt;500)</span>
					<span><span class="inline-block h-2 w-2 rounded-full bg-yellow-500"></span> Warning (500-700)</span>
					<span><span class="inline-block h-2 w-2 rounded-full bg-red-500"></span> Violation (&gt;700)</span>
					<span><span class="inline-block h-2 w-2 rounded-full" style="background:#484f58"></span> Non-code</span>
				</div>
				<div class="absolute right-3 top-3 flex flex-col gap-1 z-20">
					<button @click="zoomIn" class="h-7 w-7 rounded border border-gray-600 bg-gray-800 text-white text-sm">+</button>
					<button @click="zoomOut" class="h-7 w-7 rounded border border-gray-600 bg-gray-800 text-white text-sm">&minus;</button>
					<button @click="zoomReset" class="h-7 w-7 rounded border border-gray-600 bg-gray-800 text-gray-400 text-[10px]">&#8634;</button>
				</div>
			</div>
		</div>

		<!-- TAB: Radar Scores -->
		<div v-show="activeTab === 'radar' && !scanning" class="grid grid-cols-3 gap-4">
			<div v-for="app in appScores" :key="app.app" class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
				<div class="mb-2 flex items-center justify-between">
					<h3 class="text-sm font-semibold text-gray-900 dark:text-white">{{ app.app }}</h3>
					<Badge size="sm" :label="app.scores.overall + '%'" :theme="app.scores.overall >= 80 ? 'green' : app.scores.overall >= 50 ? 'orange' : 'red'" />
				</div>
				<svg :ref="'radar-' + app.app" width="220" height="220" class="mx-auto block"></svg>
				<div class="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]">
					<template v-for="(dim, i) in DIMS" :key="dim">
						<span class="text-gray-500">{{ dim }}</span>
						<span class="text-right" :style="{ color: hc(app.scores[DIM_KEYS[i]] || 0) }">{{ app.scores[DIM_KEYS[i]] || 0 }}%</span>
					</template>
				</div>
			</div>
		</div>

		<!-- TAB: Stack Info -->
		<div v-show="activeTab === 'stack' && !scanning" class="grid grid-cols-3 gap-4">
			<div v-for="app in stackInfo" :key="app.app" class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
				<div class="mb-2 flex items-center justify-between">
					<h3 class="text-sm font-semibold text-gray-900 dark:text-white">{{ app.app }}</h3>
					<Badge size="sm" :label="app.framework" theme="blue" />
				</div>
				<div class="grid grid-cols-2 gap-1 text-xs">
					<span class="text-gray-500">Version</span><span class="text-gray-900 dark:text-white">{{ app.version || '—' }}</span>
					<span class="text-gray-500">Python files</span><span class="text-gray-900 dark:text-white">{{ app.py_files }}</span>
					<span class="text-gray-500">JS files</span><span class="text-gray-900 dark:text-white">{{ app.js_files }}</span>
					<span class="text-gray-500">Total lines</span><span class="text-gray-900 dark:text-white">{{ (app.total_lines || 0).toLocaleString() }}</span>
					<span class="text-gray-500">Branch</span><span class="text-gray-900 dark:text-white truncate">{{ app.branch || '—' }}</span>
					<span v-if="app.repository" class="text-gray-500">Repository</span>
					<span v-if="app.repository" class="text-blue-500 truncate">{{ app.repository }}</span>
				</div>
			</div>
			<div v-if="!stackInfo.length" class="col-span-3 text-center text-sm text-gray-400 py-8">No stack data — run scan first</div>
		</div>

		<!-- TAB: Compliance -->
		<div v-show="activeTab === 'compliance' && !scanning">
			<table class="w-full text-sm" v-if="compliance.length">
				<thead><tr class="border-b border-gray-200 bg-gray-50 text-xs uppercase text-gray-500 dark:border-gray-700 dark:bg-gray-800">
					<th class="px-3 py-2 text-left">App</th>
					<th v-for="c in complianceHeaders" :key="c" class="px-2 py-2 text-center">{{ c }}</th>
					<th class="px-3 py-2 text-right">Score</th>
				</tr></thead>
				<tbody>
					<tr v-for="app in compliance" :key="app.app" class="border-b border-gray-100 dark:border-gray-800"
						:class="app.compliance_pct < 40 ? 'bg-red-50 dark:bg-red-900/10' : ''">
						<td class="px-3 py-2 font-semibold text-gray-900 dark:text-white">{{ app.app }}</td>
						<td v-for="ch in app.checks" :key="ch.name" class="px-2 py-2 text-center">
							<template v-if="ch.name === 'Security' && !ch.status">
								<span class="text-red-500 font-semibold text-[10px]">&#9888; HIGH RISK</span>
							</template>
							<template v-else>
								<span v-if="ch.status" class="text-green-500">&#10003;</span>
								<span v-else class="text-red-500">&#10007;</span>
							</template>
						</td>
						<td class="px-3 py-2 text-right">
							<Badge size="sm" :label="app.compliance_pct + '%'" :theme="app.compliance_pct >= 80 ? 'green' : app.compliance_pct >= 50 ? 'orange' : 'red'" />
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<!-- TAB: App Interactions -->
		<div v-show="activeTab === 'interactions' && !scanning">
			<div v-if="!interactions.length" class="text-center text-sm text-gray-400 py-8">No interaction data — run scan first</div>
			<div v-else class="space-y-3">
				<div v-for="app in interactions" :key="app.app" class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
					<div class="mb-2 flex items-center gap-3">
						<h3 class="text-sm font-semibold text-gray-900 dark:text-white">{{ app.app }}</h3>
						<Badge v-if="app.has_boot_session" size="sm" label="boot_session" theme="blue" />
						<Badge v-if="app.overrides.length" size="sm" :label="app.overrides.length + ' overrides'" theme="orange" />
					</div>
					<div class="grid grid-cols-2 gap-4 text-xs">
						<div v-if="app.doc_events.length">
							<p class="font-semibold text-gray-500 mb-1">doc_events ({{ app.doc_events.length }})</p>
							<div class="flex flex-wrap gap-1">
								<span v-for="dt in app.doc_events" :key="dt"
									class="rounded bg-blue-50 px-1.5 py-0.5 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400">{{ dt }}</span>
							</div>
						</div>
						<div v-if="app.scheduler_events.length">
							<p class="font-semibold text-gray-500 mb-1">scheduler_events</p>
							<div class="flex flex-wrap gap-1">
								<span v-for="freq in app.scheduler_events" :key="freq"
									class="rounded bg-purple-50 px-1.5 py-0.5 text-purple-600 dark:bg-purple-900/20 dark:text-purple-400">{{ freq }}</span>
							</div>
						</div>
						<div v-if="app.overrides.length">
							<p class="font-semibold text-gray-500 mb-1">overrides</p>
							<div class="flex flex-wrap gap-1">
								<span v-for="o in app.overrides" :key="o"
									class="rounded bg-orange-50 px-1.5 py-0.5 text-orange-600 dark:bg-orange-900/20 dark:text-orange-400 truncate max-w-[200px]">{{ o }}</span>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- TAB: Deep Analysis -->
		<div v-show="activeTab === 'deep' && !scanning">
			<div v-if="!deepApps.length" class="text-center text-sm text-gray-400 py-8">
				Run scan first to discover apps with git remotes
			</div>
			<div v-else>
				<!-- App selector -->
				<div class="mb-4 flex items-center gap-3">
					<span class="text-xs text-gray-500">Select app:</span>
					<button v-for="app in deepApps" :key="app.app" @click="runDeepAnalysis(app)"
						class="rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors"
						:class="deepSelectedApp === app.app
							? 'border-blue-500 bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400'
							: 'border-gray-200 text-gray-600 hover:border-blue-300 dark:border-gray-600 dark:text-gray-400'">
						{{ app.app }}
						<span v-if="deepAnalysis[app.app]" class="ml-1 text-green-500">&#10003;</span>
					</button>
				</div>
				<!-- Loading -->
				<div v-if="deepLoading" class="flex h-32 items-center justify-center text-gray-400 text-sm">
					<div class="text-center">
						<div class="mx-auto mb-2 h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent"></div>
						Analyzing {{ deepLoading }}…
					</div>
				</div>
				<!-- Error -->
				<div v-else-if="deepSelectedApp && deepAnalysis[deepSelectedApp]?.error"
					class="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-600 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
					{{ deepAnalysis[deepSelectedApp].error }}
				</div>
				<!-- HTML render -->
				<div v-else-if="deepSelectedApp && deepAnalysis[deepSelectedApp]?.html"
					class="rounded-lg border border-gray-200 overflow-hidden dark:border-gray-700">
					<div class="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-2 dark:border-gray-700 dark:bg-gray-800">
						<span class="text-xs font-semibold text-gray-500">{{ deepSelectedApp }} — Deep Analysis</span>
						<div class="flex items-center gap-3 text-[10px] text-gray-400">
							<span>{{ deepAnalysis[deepSelectedApp].meta?.file_count || 0 }} files</span>
							<span>{{ deepAnalysis[deepSelectedApp].meta?.symbol_count || 0 }} symbols</span>
							<span>{{ deepAnalysis[deepSelectedApp].meta?.analyzed_at?.slice(0, 19) || '' }}</span>
						</div>
					</div>
					<iframe :srcdoc="deepAnalysis[deepSelectedApp].html" sandbox="" class="w-full border-0" style="min-height:400px" @load="$event.target.style.height = $event.target.contentDocument?.body?.scrollHeight + 'px'"></iframe>
				</div>
				<!-- Empty state -->
				<div v-else-if="!deepLoading" class="text-center text-sm text-gray-400 py-8">
					Select an app above to run deep analysis
				</div>
			</div>
		</div>

		<!-- TAB: Scripts -->
		<div v-show="activeTab === 'scripts' && !scanning">
			<div v-if="!scriptsInventory.length" class="text-center text-sm text-gray-400 py-8">No scripts data — run scan first</div>
			<table v-else class="w-full text-sm">
				<thead><tr class="border-b border-gray-200 bg-gray-50 text-xs uppercase text-gray-500 dark:border-gray-700 dark:bg-gray-800">
					<th class="px-3 py-2 text-left">App</th>
					<th class="px-3 py-2 text-center">Client Scripts</th>
					<th class="px-3 py-2 text-center">Controllers</th>
					<th class="px-3 py-2 text-center">Whitelisted</th>
					<th class="px-3 py-2 text-center">Reports</th>
					<th class="px-3 py-2 text-center">Fixtures</th>
				</tr></thead>
				<tbody>
					<tr v-for="app in scriptsInventory" :key="app.app" class="border-b border-gray-100 dark:border-gray-800">
						<td class="px-3 py-2 font-semibold text-gray-900 dark:text-white">{{ app.app }}</td>
						<td class="px-3 py-2 text-center">{{ app.client_scripts }}</td>
						<td class="px-3 py-2 text-center">{{ app.controllers }}</td>
						<td class="px-3 py-2 text-center">{{ app.whitelisted }}</td>
						<td class="px-3 py-2 text-center">{{ app.reports }}</td>
						<td class="px-3 py-2 text-center">{{ app.fixtures }}</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

<script>
import { call } from 'frappe-ui';
import * as d3 from 'd3';
import { renderCirclePack, drawRadar } from './health-d3.js';

const API = 'press.press.doctype.bench.bench_code_health';
const DIMS = ['CLAUDE', 'README', 'Docs', 'Tests', 'Clean', 'Patterns', 'Lessons', 'Security'];
const DIM_KEYS = ['claude_md', 'readme', 'documentation', 'tests', 'clean_code', 'code_patterns', 'lessons', 'security'];

export default {
	name: 'BenchCodeHealth',
	props: {
		benchName: { type: String, required: true },
		autoScan: { type: Boolean, default: false },
	},
	data() {
		return {
			scanning: false, scanStep: '', activeTab: 'overview', lastScanAge: '',
			summary: null, healthData: null, appScores: [], compliance: [],
			stackInfo: [], interactions: [], scriptsInventory: [],
			deepAnalysis: {}, deepLoading: '', deepSelectedApp: '',
			tabs: [
				{ id: 'overview', label: 'Overview' },
				{ id: 'health', label: 'Health Map' },
				{ id: 'radar', label: 'Radar Scores' },
				{ id: 'stack', label: 'Stack Info' },
				{ id: 'compliance', label: 'Compliance' },
				{ id: 'interactions', label: 'App Interactions' },
				{ id: 'scripts', label: 'Scripts' },
				{ id: 'deep', label: 'Deep Analysis' },
			],
			healthFilters: [
				{ key: 'violation', label: 'Violations', color: '#f85149', bg: 'rgba(248,81,73,0.15)', active: true, count: 0 },
				{ key: 'warning', label: 'Warnings', color: '#d29922', bg: 'rgba(210,153,34,0.15)', active: true, count: 0 },
				{ key: 'clean', label: 'Clean', color: '#3fb950', bg: 'rgba(63,185,80,0.15)', active: true, count: 0 },
				{ key: 'non-code', label: 'Non-code', color: '#8b949e', bg: 'rgba(139,148,158,0.1)', active: false, count: 0 },
			],
			extFilters: [
				{ ext: '.py', color: '#3572A5', bg: 'rgba(53,114,165,0.2)', active: true, count: 0 },
				{ ext: '.js', color: '#f1e05a', bg: 'rgba(241,224,90,0.15)', active: true, count: 0 },
				{ ext: '.vue', color: '#41b883', bg: 'rgba(65,184,131,0.15)', active: true, count: 0 },
				{ ext: '.ts', color: '#3178c6', bg: 'rgba(49,120,198,0.15)', active: true, count: 0 },
				{ ext: '.json', color: '#8b949e', bg: 'rgba(139,148,158,0.1)', active: false, count: 0 },
				{ ext: '.md', color: '#8b949e', bg: 'rgba(139,148,158,0.1)', active: false, count: 0 },
			],
			visibleFiles: 0, totalFiles: 0,
			_cpInstance: null,
			DIMS, DIM_KEYS,
		};
	},
	async mounted() {
		// Try loading cached summary first (fast — no docker calls)
		try {
			const cached = await call(`${API}.get_health_summary`, { bench_name: this.benchName });
			if (cached && cached.total_files > 0) {
				this.summary = cached;
				this.lastScanAge = 'From cache';
				return; // data exists, don't re-scan
			}
		} catch (e) { /* no cache, proceed to scan */ }
		if (this.autoScan) this.scan();
	},
	beforeUnmount() {
		if (this._cpInstance) { this._cpInstance.destroy(); this._cpInstance = null; }
	},
	watch: {
		activeTab(tab) {
			// Lazy render: D3 needs visible container with real dimensions
			if (tab === 'health' && this.healthData && !this._cpInstance) {
				this.$nextTick(() => this.initCirclePack());
			}
			if (tab === 'radar' && this.appScores.length) {
				this.$nextTick(() => this.renderRadars());
			}
			if (tab === 'overview' && this.appScores.length) {
				this.$nextTick(() => this.renderOverallRadar());
			}
		},
	},
	computed: {
		complianceHeaders() {
			if (!this.compliance.length) return [];
			return this.compliance[0].checks.map(c => c.name);
		},
		overallScore() {
			if (!this.appScores.length) return 0;
			return Math.round(this.appScores.reduce((s, a) => s + a.scores.overall, 0) / this.appScores.length);
		},
		sortedApps() {
			return [...this.appScores].sort((a, b) => b.scores.overall - a.scores.overall);
		},
		deepApps() {
			return this.stackInfo.filter(a => a.repository || a.commit_hash);
		},
		actionItems() {
			const items = [];
			if (this.summary?.security_alerts > 0)
				items.push({ sev: 'high', text: `${this.summary.security_alerts} files with potential hardcoded secrets` });
			if (this.summary?.violation > 0)
				items.push({ sev: 'high', text: `${this.summary.violation} files exceed 700 lines` });
			if (this.summary?.warning > 0)
				items.push({ sev: 'warn', text: `${this.summary.warning} files in warning zone (500-700)` });
			for (const app of this.compliance) {
				const missing = app.checks.filter(c => !c.status).map(c => c.name);
				if (missing.length > 0)
					items.push({ sev: app.compliance_pct < 40 ? 'high' : 'warn', text: `${app.app}: missing ${missing.join(', ')}` });
			}
			return items;
		},
	},
	methods: {
		hc(pct) { return pct >= 80 ? '#3fb950' : pct >= 50 ? '#d29922' : '#f85149'; },
		avgDimScore(dimIdx) {
			if (!this.appScores.length) return 0;
			return Math.round(this.appScores.reduce((s, a) => s + (a.scores[DIM_KEYS[dimIdx]] || 0), 0) / this.appScores.length);
		},
		dimAppCount(dimIdx) {
			return this.appScores.filter(a => (a.scores[DIM_KEYS[dimIdx]] || 0) >= 50).length;
		},
		toggleFilter(f) {
			f.active = !f.active;
			this.applyFilters();
		},
		applyFilters() {
			if (!this._cpInstance) return;
			this.visibleFiles = this._cpInstance.applyFilters(this.healthFilters, this.extFilters);
		},
		async scan() {
			if (this.scanning) return;
			this.scanning = true;
			try {
				// Step 1: Quick summary (fast — single docker command)
				this.scanStep = '1/4 — health summary';
				this.summary = await call(`${API}.get_health_summary`, { bench_name: this.benchName });

				// Step 2: File tree (moderate — single find+wc)
				this.scanStep = '2/4 — file health map';
				this.healthData = await call(`${API}.scan_bench_health`, { bench_name: this.benchName });

				// Step 3: Scores + compliance (heavy — many docker calls, sequential)
				this.scanStep = '3/4 — app scores + compliance';
				const [scores, comp] = await Promise.all([
					call(`${API}.get_app_scores`, { bench_name: this.benchName, include_all: true }),
					call(`${API}.get_docs_compliance`, { bench_name: this.benchName }),
				]);
				this.appScores = scores;
				this.compliance = comp;

				// Step 4: Stack + interactions + scripts
				this.scanStep = '4/4 — stack info + interactions';
				const [stack, inter, scripts] = await Promise.all([
					call(`${API}.get_app_stack_info`, { bench_name: this.benchName }),
					call(`${API}.get_app_interactions`, { bench_name: this.benchName }),
					call(`${API}.get_scripts_inventory`, { bench_name: this.benchName }),
				]);
				this.stackInfo = stack;
				this.interactions = inter;
				this.scriptsInventory = scripts;
				this.lastScanAge = 'Scanned just now';
				// Trigger D3 render for the currently active tab
				this.$nextTick(() => {
					if (this.activeTab === 'health') this.initCirclePack();
					if (this.activeTab === 'overview') this.renderOverallRadar();
					if (this.activeTab === 'radar') this.renderRadars();
				});
			} catch (e) {
				console.error('Scan failed:', e);
				this.scanStep = 'Error: ' + (e?.messages?.[0] || String(e));
			} finally {
				this.scanning = false;
			}
		},
		initCirclePack() {
			const el = this.$refs.circlePack;
			if (!this.healthData || !el || el.clientWidth === 0) return;
			if (this._cpInstance) this._cpInstance.destroy();
			// Build app→repo map for GitHub links in sidebar
			const appRepos = {};
			for (const s of this.stackInfo) { if (s.repository) appRepos[s.app] = s.repository; }
			this._cpInstance = renderCirclePack(this.$refs.circlePack, this.healthData, {
				tooltip: this.$refs.tooltip, sidebar: this.$refs.sidebar, breadcrumb: this.$refs.breadcrumb, appRepos,
			});
			// Update filter counts from leaves
			const hCounts = { clean: 0, warning: 0, violation: 0, 'non-code': 0 };
			const eCounts = {};
			this._cpInstance.leaves.forEach(d => {
				hCounts[d.data.health || 'non-code'] = (hCounts[d.data.health || 'non-code'] || 0) + 1;
				eCounts[d.data.ext || ''] = (eCounts[d.data.ext || ''] || 0) + 1;
			});
			this.healthFilters.forEach(f => { f.count = hCounts[f.key] || 0; });
			this.extFilters.forEach(f => { f.count = eCounts[f.ext] || 0; });
			this.totalFiles = this._cpInstance.leaves.length;
			this.applyFilters();
		},
		zoomIn() { this._cpInstance?.zoomIn(); },
		zoomOut() { this._cpInstance?.zoomOut(); },
		zoomReset() { this._cpInstance?.zoomReset(); },
		renderRadars() {
			for (const app of this.appScores) {
				const ref = this.$refs['radar-' + app.app];
				const el = Array.isArray(ref) ? ref[0] : ref;
				if (!el) continue;
				drawRadar(d3.select(el), DIM_KEYS.map(k => app.scores[k] || 0), 220, 220, DIMS);
			}
		},
		renderOverallRadar() {
			const el = this.$refs.radarOverall;
			if (!el || !this.appScores.length) return;
			drawRadar(d3.select(el), DIM_KEYS.map((_, i) => this.avgDimScore(i)), 280, 280, DIMS);
		},
		async runDeepAnalysis(app) {
			const gitUrl = app.repository ? `https://github.com/${app.repository}` : '';
			if (!gitUrl) {
				this.deepAnalysis = { ...this.deepAnalysis, [app.app]: { error: 'No git remote found for this app' } };
				this.deepSelectedApp = app.app;
				return;
			}
			this.deepSelectedApp = app.app;
			this.deepLoading = app.app;
			try {
				const result = await call('press.press.doctype.bench.health_analysis.analyze_app_code', {
					git_url: gitUrl, commit_hash: app.commit_hash || 'HEAD', output_format: 'both',
				});
				this.deepAnalysis = { ...this.deepAnalysis, [app.app]: result };
			} catch (e) {
				this.deepAnalysis = { ...this.deepAnalysis, [app.app]: { error: e?.messages?.[0] || String(e) } };
			} finally {
				this.deepLoading = '';
			}
		},
	},
};
</script>
