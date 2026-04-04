<template>
	<div>
		<!-- Code Graph -->
		<div v-if="tab === 'codegraph'">
			<div v-if="!apps.length" class="text-center text-sm text-gray-400 py-8">Run scan first to discover apps</div>
			<div v-else>
				<div class="mb-3 flex items-center gap-3">
					<span class="text-xs text-gray-500">Select app:</span>
					<button v-for="app in apps" :key="app" @click="loadGraph(app)"
						class="rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors"
						:class="graphSelectedApp === app
							? 'border-blue-500 bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400'
							: 'border-gray-200 text-gray-600 hover:border-blue-300 dark:border-gray-600 dark:text-gray-400'">
						{{ app }}
						<span v-if="graphCache[app]" class="ml-1 text-green-500">&#10003;</span>
					</button>
				</div>
				<div v-if="graphLoading" class="flex h-32 items-center justify-center text-gray-400 text-sm">
					<div class="text-center">
						<div class="mx-auto mb-2 h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent"></div>
						Building graph for {{ graphLoading }}...
					</div>
				</div>
				<div v-else-if="graphSelectedApp && graphCache[graphSelectedApp]" class="relative overflow-hidden rounded-lg border border-gray-200 bg-gray-950 dark:border-gray-700" style="height:500px">
					<svg ref="codeGraph" class="h-full w-full"></svg>
					<div ref="graphBreadcrumb" class="absolute left-3 top-2 z-10 text-[11px] text-blue-400 cursor-pointer"></div>
					<div ref="graphTooltip" class="pointer-events-none absolute z-50 hidden rounded-lg border border-gray-600 bg-gray-800 px-3 py-2 text-xs shadow-lg" style="max-width:260px"></div>
					<div ref="graphSidebar" class="absolute right-0 top-0 z-40 hidden h-full w-64 overflow-y-auto border-l border-gray-700 bg-gray-900 p-3"></div>
					<div class="absolute bottom-3 left-3 flex gap-3 text-[10px] text-gray-500 z-10">
						<span><span class="inline-block h-2 w-2 rounded-full" style="background:#3b82f6"></span> Module</span>
						<span><span class="inline-block h-2 w-2 rounded-full" style="background:#eab308"></span> Class</span>
						<span><span class="inline-block h-2 w-2 rounded-full" style="background:#22c55e"></span> Function</span>
					</div>
				</div>
				<div v-else-if="!graphLoading" class="text-center text-sm text-gray-400 py-8">Select an app above to build its code graph</div>
			</div>
		</div>

		<!-- Deep Analysis -->
		<div v-if="tab === 'deep'">
			<div v-if="!deepApps.length" class="text-center text-sm text-gray-400 py-8">Run scan first to discover apps with git remotes</div>
			<div v-else>
				<div class="mb-4 flex items-center gap-3">
					<span class="text-xs text-gray-500">Select app:</span>
					<button v-for="app in deepApps" :key="app.app" @click="runDeepAnalysis(app)"
						class="rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors"
						:class="deepSelectedApp === app.app
							? 'border-blue-500 bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400'
							: 'border-gray-200 text-gray-600 hover:border-blue-300 dark:border-gray-600 dark:text-gray-400'">
						{{ app.app }}
						<span v-if="deepCache[app.app]" class="ml-1 text-green-500">&#10003;</span>
					</button>
				</div>
				<div v-if="deepLoading" class="flex h-32 items-center justify-center text-gray-400 text-sm">
					<div class="text-center">
						<div class="mx-auto mb-2 h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent"></div>
						Analyzing {{ deepLoading }}...
					</div>
				</div>
				<div v-else-if="deepSelectedApp && deepCache[deepSelectedApp]?.error"
					class="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-600 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
					{{ deepCache[deepSelectedApp].error }}
				</div>
				<div v-else-if="deepSelectedApp && deepCache[deepSelectedApp]?.html"
					class="rounded-lg border border-gray-200 overflow-hidden dark:border-gray-700">
					<div class="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-2 dark:border-gray-700 dark:bg-gray-800">
						<span class="text-xs font-semibold text-gray-500">{{ deepSelectedApp }} — Deep Analysis</span>
						<div class="flex items-center gap-3 text-[10px] text-gray-400">
							<span>{{ deepCache[deepSelectedApp].meta?.file_count || 0 }} files</span>
							<span>{{ deepCache[deepSelectedApp].meta?.symbol_count || 0 }} symbols</span>
							<span>{{ deepCache[deepSelectedApp].meta?.analyzed_at?.slice(0, 19) || '' }}</span>
						</div>
					</div>
					<iframe :srcdoc="deepCache[deepSelectedApp].html" sandbox="" class="w-full border-0" style="min-height:400px" @load="$event.target.style.height = $event.target.contentDocument?.body?.scrollHeight + 'px'"></iframe>
				</div>
				<div v-else-if="!deepLoading" class="text-center text-sm text-gray-400 py-8">Select an app above to run deep analysis</div>
			</div>
		</div>
	</div>
</template>

<script>
import { call } from 'frappe-ui';
import { renderCodeGraph } from './health-d3.js';

const API = 'press.press.doctype.bench.bench_code_health';

export default {
	name: 'HealthAdvanced',
	props: {
		tab: { type: String, required: true },
		benchName: { type: String, required: true },
		apps: { type: Array, default: () => [] },
		deepApps: { type: Array, default: () => [] },
	},
	data() {
		return {
			graphCache: {}, graphLoading: '', graphSelectedApp: '',
			deepCache: {}, deepLoading: '', deepSelectedApp: '',
			_graphInstance: null,
		};
	},
	beforeUnmount() {
		if (this._graphInstance) { this._graphInstance.destroy(); this._graphInstance = null; }
	},
	methods: {
		async loadGraph(appName) {
			this.graphSelectedApp = appName;
			if (this.graphCache[appName]) {
				this.$nextTick(() => this.renderGraph(appName));
				return;
			}
			this.graphLoading = appName;
			try {
				const result = await call(`${API}.scan_app_graph`, { bench_name: this.benchName, app_name: appName });
				this.graphCache = { ...this.graphCache, [appName]: result };
				this.$nextTick(() => this.renderGraph(appName));
			} catch (e) {
				console.error(`Graph failed for ${appName}:`, e);
			} finally {
				this.graphLoading = '';
			}
		},
		renderGraph(appName) {
			if (appName !== this.graphSelectedApp) return;
			const el = this.$refs.codeGraph;
			if (!el || el.clientWidth === 0 || !this.graphCache[appName]) return;
			if (this._graphInstance) this._graphInstance.destroy();
			this._graphInstance = renderCodeGraph(el, this.graphCache[appName], {
				tooltip: this.$refs.graphTooltip, sidebar: this.$refs.graphSidebar, breadcrumb: this.$refs.graphBreadcrumb,
			});
		},
		async runDeepAnalysis(app) {
			const gitUrl = app.repository ? `https://github.com/${app.repository}` : '';
			if (!gitUrl) {
				this.deepCache = { ...this.deepCache, [app.app]: { error: 'No git remote found for this app' } };
				this.deepSelectedApp = app.app;
				return;
			}
			this.deepSelectedApp = app.app;
			this.deepLoading = app.app;
			try {
				const result = await call('press.press.doctype.bench.health_analysis.analyze_app_code', {
					git_url: gitUrl, commit_hash: app.commit_hash || 'HEAD', output_format: 'both',
				});
				this.deepCache = { ...this.deepCache, [app.app]: result };
			} catch (e) {
				this.deepCache = { ...this.deepCache, [app.app]: { error: e?.messages?.[0] || String(e) } };
			} finally {
				this.deepLoading = '';
			}
		},
	},
};
</script>
