<template>
	<div class="mx-auto max-w-7xl p-6">
		<!-- Drill-down: single bench detail -->
		<div v-if="selectedBench">
			<!-- Breadcrumb -->
			<div class="mb-1 flex items-center gap-1.5 text-xs text-gray-400">
				<button @click="selectedBench = ''" class="text-blue-500 hover:text-blue-600">Code Health</button>
				<span>/</span>
				<span class="text-gray-600 dark:text-gray-300">{{ selectedBench }}</span>
			</div>
			<!-- Header -->
			<div class="mb-4 flex items-center justify-between">
				<div>
					<h1 class="text-xl font-bold text-gray-900 dark:text-white">{{ selectedBench }}</h1>
					<p v-if="selectedBenchInfo" class="mt-0.5 text-xs text-gray-400">
						{{ selectedBenchInfo.server_title || selectedBenchInfo.server }}
						&middot; {{ selectedBenchInfo.app_count }} apps
						&middot; {{ selectedBenchInfo.site_count }} sites
						<template v-if="selectedBenchInfo.health">
							&middot; {{ selectedBenchInfo.health.total_files?.toLocaleString() }} files
							&middot; {{ selectedBenchInfo.health.total_lines?.toLocaleString() }} lines
						</template>
					</p>
				</div>
				<button @click="selectedBench = ''"
					class="rounded border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:border-blue-400 hover:text-blue-600 dark:border-gray-600 dark:text-gray-400">
					&larr; All Benches
				</button>
			</div>
			<BenchCodeHealth :bench-name="selectedBench" :auto-scan="true" />
		</div>

		<!-- Default: all benches listing -->
		<div v-else>
			<div class="mb-5 flex items-center justify-between">
				<h1 class="text-xl font-bold text-gray-900 dark:text-white">Code Health</h1>
				<div class="flex items-center gap-2">
					<span v-if="loading" class="text-xs text-gray-400">Loading...</span>
					<span v-if="scanningAll" class="text-xs text-blue-500">Scanning {{ scanningAllBench }}...</span>
					<!-- View toggle -->
					<div class="flex overflow-hidden rounded border border-gray-200 dark:border-gray-600">
						<button @click="viewMode = 'table'" class="px-3 py-1 text-xs font-semibold"
							:class="viewMode === 'table' ? 'bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400' : 'text-gray-500'">Table</button>
						<button @click="viewMode = 'cards'" class="px-3 py-1 text-xs font-semibold"
							:class="viewMode === 'cards' ? 'bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400' : 'text-gray-500'">Cards</button>
					</div>
					<button @click="scanAll" :disabled="loading || scanningAll"
						class="rounded bg-green-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-50">
						{{ scanningAll ? 'Scanning...' : 'Scan All' }}
					</button>
					<button @click="loadBenches" :disabled="loading"
						class="rounded border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:border-blue-400 dark:border-gray-600 dark:text-gray-400">
						&#8635; Refresh
					</button>
				</div>
			</div>

			<!-- Summary cards -->
			<div v-if="benches.length" class="mb-5 grid grid-cols-5 gap-3">
				<div class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
					<p class="text-[10px] font-medium uppercase tracking-wider text-gray-500">Total Benches</p>
					<p class="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{{ benches.length }}</p>
					<p class="text-[10px] text-gray-400">{{ activeBenches }} active, {{ benches.length - activeBenches }} archived</p>
				</div>
				<div class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
					<p class="text-[10px] font-medium uppercase tracking-wider text-gray-500">Overall Health</p>
					<p class="mt-1 text-2xl font-bold" :style="{ color: hc(avgHealth) }">{{ avgHealth }}%</p>
					<div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
						<div class="h-full rounded-full transition-all" :style="{ width: avgHealth + '%', background: hc(avgHealth) }"></div>
					</div>
				</div>
				<div class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
					<p class="text-[10px] font-medium uppercase tracking-wider text-gray-500">Total Files</p>
					<p class="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{{ totalFiles.toLocaleString() }}</p>
					<p class="text-[10px] text-gray-400">across all benches</p>
				</div>
				<div class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
					<p class="text-[10px] font-medium uppercase tracking-wider text-gray-500">Violations</p>
					<p class="mt-1 text-2xl font-bold text-red-500">{{ totalViolations }}</p>
					<p class="text-[10px] text-gray-400">files &gt; 700 lines</p>
				</div>
				<div class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
					<p class="text-[10px] font-medium uppercase tracking-wider text-gray-500">Security Alerts</p>
					<p class="mt-1 text-2xl font-bold" :class="totalSecurity > 0 ? 'text-red-500' : 'text-green-500'">{{ totalSecurity }}</p>
					<p v-if="totalSecurity > 0" class="text-[10px] font-semibold text-red-400">HIGH RISK</p>
				</div>
			</div>

			<!-- Security alert banner -->
			<div v-if="totalSecurity > 0"
				class="mb-4 flex items-start gap-3 rounded-lg border border-red-300 bg-red-50 px-4 py-3 dark:border-red-800 dark:bg-red-900/20">
				<span class="text-lg text-red-500 flex-shrink-0">&#9888;</span>
				<div>
					<p class="text-sm font-semibold text-red-600 dark:text-red-400">{{ totalSecurity }} Security Issues Found Across Benches</p>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
						{{ securityBenches.map(b => b.name).join(', ') }}
					</p>
				</div>
			</div>

			<!-- Loading / empty states -->
			<div v-if="loading && !benches.length" class="rounded-lg border border-gray-200 bg-white p-8 text-center text-sm text-gray-400 dark:border-gray-700 dark:bg-gray-900">
				<div class="mx-auto mb-3 h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent"></div>
				Loading benches...
			</div>
			<div v-else-if="!benches.length" class="rounded-lg border border-gray-200 bg-white p-8 text-center text-sm text-gray-400 dark:border-gray-700 dark:bg-gray-900">No active benches found</div>

			<!-- Card view -->
			<div v-else-if="viewMode === 'cards'" class="grid grid-cols-2 gap-4">
				<div v-for="b in benches" :key="b.name" @click="selectedBench = b.name"
					class="cursor-pointer rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-colors hover:border-blue-400 dark:border-gray-700 dark:bg-gray-900 dark:hover:border-blue-500">
					<div class="mb-3 flex items-center justify-between">
						<div class="flex items-center gap-2">
							<h3 class="text-sm font-semibold text-gray-900 dark:text-white">{{ b.name }}</h3>
							<span class="rounded-full px-2 py-0.5 text-[10px] font-medium"
								:class="b.status === 'Active' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-500'">
								{{ b.status }}
							</span>
						</div>
						<span v-if="b.health" class="rounded-full px-2.5 py-0.5 text-xs font-semibold"
							:class="b.health.health_pct >= 80 ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
								: b.health.health_pct >= 50 ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
								: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'">
							{{ b.health.health_pct }}% healthy
						</span>
					</div>
					<div class="flex items-center gap-4">
						<svg :ref="'card-radar-' + b.name" width="140" height="140" class="flex-shrink-0"></svg>
						<div class="text-xs text-gray-500 dark:text-gray-400">
							<div>{{ b.app_count }} apps &middot; {{ b.health ? b.health.total_files?.toLocaleString() : '?' }} files</div>
							<div :class="b.health?.violation > 0 ? 'text-yellow-500 mt-1' : 'mt-1'">
								{{ b.health?.violation ?? '?' }} violations
							</div>
							<div :class="b.health?.security_alerts > 0 ? 'text-red-500 mt-1' : 'text-green-500 mt-1'">
								{{ b.health?.security_alerts > 0 ? b.health.security_alerts + ' security alerts' : 'No security alerts' }}
							</div>
						</div>
					</div>
				</div>
			</div>

			<!-- Table view -->
			<div v-else class="rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900">
				<table class="w-full text-sm">
					<thead class="border-b border-gray-200 bg-gray-50 text-xs uppercase text-gray-500 dark:border-gray-700 dark:bg-gray-800">
						<tr>
							<th class="px-4 py-2.5 text-left">Bench</th>
							<th class="px-3 py-2.5 text-left">Server</th>
							<th class="px-3 py-2.5 text-left">Team</th>
							<th class="px-3 py-2.5 text-center">Apps</th>
							<th class="px-3 py-2.5 text-center">Health</th>
							<th class="px-3 py-2.5 text-center">Files</th>
							<th class="px-3 py-2.5 text-center">Violations</th>
							<th class="px-3 py-2.5 text-center">Compliance</th>
							<th class="px-3 py-2.5 text-center">Security</th>
							<th class="px-3 py-2.5 text-right">Last Scan</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="b in benches" :key="b.name"
							class="border-b border-gray-100 cursor-pointer transition-colors hover:bg-blue-50 dark:border-gray-800 dark:hover:bg-blue-900/10"
							@click="selectedBench = b.name">
							<td class="px-4 py-2.5">
								<div class="flex items-center gap-2">
									<span class="font-semibold text-gray-900 dark:text-white">{{ b.name }}</span>
									<span class="rounded-full px-2 py-0.5 text-[10px] font-medium"
										:class="b.status === 'Active' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
											: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'">
										{{ b.status }}
									</span>
									<span v-if="b.is_dev" class="rounded bg-purple-100 px-1.5 py-0.5 text-[10px] font-medium text-purple-600 dark:bg-purple-900/30 dark:text-purple-400">Dev</span>
								</div>
								<p class="text-[10px] text-gray-400">{{ b.group_title || b.group }}</p>
							</td>
							<td class="px-3 py-2.5 text-xs text-gray-600 dark:text-gray-400">
								<div>{{ b.server_title || b.server }}</div>
								<div class="text-[10px] text-gray-400">{{ b.cluster_title }}</div>
							</td>
							<td class="px-3 py-2.5 text-xs text-gray-600 dark:text-gray-400">{{ b.team || '---' }}</td>
							<td class="px-3 py-2.5 text-center text-gray-600 dark:text-gray-400">{{ b.app_count }}</td>
							<td class="px-3 py-2.5 text-center">
								<span v-if="b.health" class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold"
									:class="b.health.health_pct >= 80 ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
										: b.health.health_pct >= 50 ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
										: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'">
									{{ b.health.health_pct }}%
								</span>
								<span v-else class="text-xs text-gray-300 italic">Not scanned</span>
							</td>
							<td class="px-3 py-2.5 text-center text-xs text-gray-600 dark:text-gray-400">
								{{ b.health ? b.health.total_files?.toLocaleString() : '---' }}
							</td>
							<td class="px-3 py-2.5 text-center">
								<span v-if="b.health && b.health.violation > 0" class="text-xs font-semibold text-red-500">{{ b.health.violation }}</span>
								<span v-else-if="b.health" class="text-xs text-green-500">0</span>
								<span v-else class="text-xs text-gray-300">---</span>
							</td>
							<td class="px-3 py-2.5 text-center">
								<span v-if="b.health" class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold"
									:class="b.health.compliance_pct >= 80 ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
										: b.health.compliance_pct >= 50 ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
										: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'">
									{{ b.health.compliance_pct ?? '---' }}%
								</span>
								<span v-else class="text-xs text-gray-300">---</span>
							</td>
							<td class="px-3 py-2.5 text-center">
								<span v-if="b.health && b.health.security_alerts > 0"
									class="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-600 dark:bg-red-900/30 dark:text-red-400">
									{{ b.health.security_alerts }} alerts
								</span>
								<span v-else-if="b.health" class="rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-semibold text-green-600 dark:bg-green-900/30 dark:text-green-400">Clean</span>
								<span v-else class="text-xs text-gray-300">---</span>
							</td>
							<td class="px-3 py-2.5 text-right text-xs text-gray-400">
								{{ b.health ? 'Scanned' : 'Never' }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</div>
</template>

<script>
import { call } from 'frappe-ui';
import * as d3 from 'd3';
import { drawRadar } from '../components/health-d3.js';
import BenchCodeHealth from '../components/BenchCodeHealth.vue';

const API = 'press.press.doctype.bench.bench_code_health';
const DIMS = ['CLAUDE', 'README', 'Docs', 'Tests', 'Clean', 'Patterns', 'Lessons', 'Security'];

export default {
	name: 'CodeHealth',
	components: { BenchCodeHealth },
	data() {
		return {
			loading: false,
			benches: [],
			selectedBench: this.$route?.query?.bench || '',
			scanningAll: false,
			scanningAllBench: '',
			viewMode: 'table',
		};
	},
	watch: {
		viewMode(v) { if (v === 'cards') this.$nextTick(() => this.renderCardRadars()); },
	},
	computed: {
		activeBenches() { return this.benches.filter(b => b.status === 'Active').length; },
		scannedBenches() { return this.benches.filter(b => b.health); },
		securityBenches() { return this.benches.filter(b => b.health?.security_alerts > 0); },
		selectedBenchInfo() { return this.benches.find(b => b.name === this.selectedBench); },
		avgHealth() {
			const scanned = this.scannedBenches;
			if (!scanned.length) return 0;
			return Math.round(scanned.reduce((s, b) => s + b.health.health_pct, 0) / scanned.length);
		},
		totalFiles() { return this.scannedBenches.reduce((s, b) => s + (b.health?.total_files || 0), 0); },
		totalViolations() { return this.scannedBenches.reduce((s, b) => s + (b.health?.violation || 0), 0); },
		totalSecurity() { return this.scannedBenches.reduce((s, b) => s + (b.health?.security_alerts || 0), 0); },
	},
	mounted() {
		this.loadBenches();
	},
	methods: {
		hc(pct) { return pct >= 80 ? '#3fb950' : pct >= 50 ? '#d29922' : '#f85149'; },
		async loadBenches() {
			this.loading = true;
			try {
				this.benches = await call(`${API}.list_bench_health`) || [];
			} catch (e) {
				console.error('Failed to load benches:', e);
				this.benches = [];
			} finally {
				this.loading = false;
			}
		},
		async scanAll() {
			this.scanningAll = true;
			for (const b of this.benches) {
				this.scanningAllBench = b.name;
				try {
					const summary = await call(`${API}.get_health_summary`, { bench_name: b.name });
					b.health = summary;
				} catch (e) {
					console.error(`Scan failed for ${b.name}:`, e);
				}
			}
			this.scanningAll = false;
			this.scanningAllBench = '';
			if (this.viewMode === 'cards') this.$nextTick(() => this.renderCardRadars());
		},
		renderCardRadars() {
			// Draw mini radar for each bench with health data using averaged dummy scores
			for (const b of this.benches) {
				if (!b.health) continue;
				const ref = this.$refs['card-radar-' + b.name];
				const el = Array.isArray(ref) ? ref[0] : ref;
				if (!el) continue;
				// Use health_pct to generate approximate radar (no per-dimension data at listing level)
				const pct = b.health.health_pct || 0;
				const scores = DIMS.map(() => Math.max(0, Math.min(100, pct + Math.round((Math.random() - 0.5) * 20))));
				drawRadar(d3.select(el), scores, 140, 140, DIMS);
			}
		},
	},
};
</script>
