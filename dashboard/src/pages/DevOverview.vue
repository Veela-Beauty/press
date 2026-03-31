<template>
	<div>
		<!-- Topbar -->
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs :items="[{ label: 'Dev Overview', route: '/dev-overview' }]">
					<template #suffix>
						<span class="live-badge">
							<span class="live-dot"></span> Live
						</span>
					</template>
				</Breadcrumbs>
				<template #actions>
					<Button variant="outline" :loading="overviewRes.loading" @click="reload()">
						↻ Refresh All
					</Button>
				</template>
			</Header>
		</div>

		<div class="content-wrap">
			<!-- Summary Cards -->
			<div class="summary-grid">
				<div class="summary-card">
					<div class="s-label">ACTIVE BENCHES</div>
					<div class="s-value">{{ activeBenchCount }}</div>
					<div class="s-sub">across {{ serverCount }} server{{ serverCount !== 1 ? 's' : '' }}</div>
				</div>
				<div class="summary-card warn">
					<div class="s-label">SITES PENDING UPDATE</div>
					<div class="s-value">{{ pendingUpdateCount }}</div>
					<div class="s-sub">across {{ pendingUpdateBenchCount }} bench{{ pendingUpdateBenchCount !== 1 ? 'es' : '' }}</div>
				</div>
				<div class="summary-card danger">
					<div class="s-label">UNDEPLOYED COMMITS</div>
					<div class="s-value">{{ totalUndeployedCommits }}</div>
					<div class="s-sub">in release groups</div>
				</div>
				<div class="summary-card ok">
					<div class="s-label">LAST SUCCESSFUL BUILD</div>
					<div class="s-value">{{ lastBuildAge }}</div>
					<div class="s-sub">{{ lastBuildSub }}</div>
				</div>
			</div>

			<!-- Filter Bar -->
			<div class="filter-bar">
				<input
					v-model="searchQuery"
					type="text"
					class="search-input"
					placeholder="Search benches or apps…"
				/>
				<button
					v-for="f in filterOptions"
					:key="f.key"
					class="fbtn"
					:class="{ active: filterMode === f.key }"
					@click="filterMode = f.key"
				>
					{{ f.label }}
				</button>
			</div>

			<!-- Bench Table -->
			<div v-if="filteredBenches.length === 0 && !overviewRes.loading" class="empty-state">
				No benches found.
			</div>
			<div v-else class="bench-table">
				<div class="bench-table-header">
					<div>Bench</div>
					<div>Last Commit</div>
					<div>Build Status</div>
					<div>Sites</div>
					<div>Undeployed Gap</div>
					<div></div>
				</div>

				<div
					v-for="bench in filteredBenches"
					:key="bench.name"
					class="bench-row"
					:class="{
						'dev-bench': bench.is_development_bench,
						'has-errors': bs(bench.name).data?.errors?.count > 0,
						open: expanded === bench.name,
					}"
				>
					<!-- Main Row -->
					<div class="bench-row-main" @click="toggleExpand(bench.name)">
						<!-- Bench Name + Sub -->
						<div class="bench-name">
							<div style="display:flex;align-items:center;gap:8px">
								<strong>{{ bench.group_title || bench.name }}</strong>
								<span v-if="bench.is_development_bench" class="bench-dev-tag">DEV</span>
							</div>
							<div style="display:flex;align-items:center;gap:8px;margin-top:3px">
								<small>{{ bench.name }} · {{ bench.server_title || bench.server }}</small>
								<label class="dev-toggle" @click.stop>
									<input
										type="checkbox"
										:checked="!!bench.is_development_bench"
										@change="toggleDevBench(bench, $event)"
									/>
									<span class="dev-track"></span>
									<span class="dev-label">Dev Bench</span>
								</label>
							</div>
						</div>

						<!-- Last Commit -->
						<div class="commit-info">
							<template v-if="bench.last_commit">
								<a class="commit-msg" :title="bench.last_commit.message" @click.stop>
									{{ bench.last_commit.message }}
								</a>
								<div class="commit-meta">
									<span class="hash-chip">{{ bench.last_commit.hash }}</span>
									<span class="app-chip">{{ bench.last_commit.app }}</span>
									<span>{{ bench.last_commit.author }} · {{ formatDate(bench.last_commit.timestamp) }}</span>
								</div>
							</template>
							<span v-else class="text-gray-400 text-xs">—</span>
						</div>

						<!-- Build Status -->
						<div>
							<span :class="buildBadgeClass(bench.status)">
								<span class="badge-dot"></span>
								{{ bench.status }}
							</span>
						</div>

						<!-- Sites -->
						<div class="sites-col">
							<div class="count">{{ bench.site_count || 0 }} site{{ bench.site_count !== 1 ? 's' : '' }}</div>
							<div
								v-if="bench.pending_update_count > 0"
								class="note note-warn"
							>⚠ {{ bench.pending_update_count }} pending update</div>
							<div v-else class="note note-ok">✓ all up to date</div>
						</div>

						<!-- Undeployed Gap -->
						<div class="gap-col">
							<div v-if="bench.undeployed_count > 0" class="gap-warn">
								⚠ {{ bench.undeployed_count }} commit{{ bench.undeployed_count !== 1 ? 's' : '' }}
							</div>
							<div v-else class="gap-ok">✓ All deployed</div>
							<div class="gap-sub">{{ bench.status === 'Active' ? 'last push = last build' : bench.status.toLowerCase() }}</div>
						</div>

						<!-- Action Buttons -->
						<div class="row-btns" @click.stop>
							<!-- Deploy -->
							<div class="icon-btn" title="Deploy Now" @click="deployBench(bench)">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<path d="M5 3l14 9-14 9V3z"/>
								</svg>
							</div>
							<!-- GitHub -->
							<div class="icon-btn" title="View on GitHub" @click="openGitHub(bench)">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 00-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0020 4.77 5.07 5.07 0 0019.91 1S18.73.65 16 2.48a13.38 13.38 0 00-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 005 4.77a5.44 5.44 0 00-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 009 18.13V22"/>
								</svg>
							</div>
							<!-- VS Code -->
							<div class="icon-btn vscode-btn" title="Open in VS Code" @click="openVSCode(bench)">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
								</svg>
							</div>
							<!-- Restart -->
							<div class="icon-btn" title="Restart Bench" @click="restartBench(bench)">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<polyline points="1 4 1 10 7 10"/>
									<path d="M3.51 15a9 9 0 102.13-9.36L1 10"/>
								</svg>
							</div>
						</div>
					</div>

					<!-- Expanded Panel -->
					<div v-if="expanded === bench.name" class="bench-panel">
						<div class="panel-tabs">
							<div
								v-for="tab in panelTabs(bench)"
								:key="tab.key"
								class="ptab"
								:class="{ active: bs(bench.name).tab === tab.key }"
								@click="setTab(bench.name, tab.key)"
							>
								{{ tab.label }}
								<span v-if="tab.count > 0" class="err-badge">{{ tab.count }}</span>
							</div>
						</div>
						<div v-if="bs(bench.name).loading" class="panel-loading">Loading…</div>
						<template v-else-if="bs(bench.name).data">
							<!-- Tab: Undeployed Gap -->
							<div v-if="bs(bench.name).tab === 'gap'" class="panel-section">
								<template v-if="bench.undeployed_count > 0">
									<div class="gap-box">
										<div class="gap-box-title">⚠ {{ bench.undeployed_count }} commit{{ bench.undeployed_count !== 1 ? 's' : '' }} pushed but not yet built</div>
										<div v-for="c in bs(bench.name).data.recent_commits" :key="c.hash" class="gap-item">
											<span class="ghash">{{ c.hash }}</span>
											<span>{{ c.message }}</span>
											<span class="gtime">{{ c.author }} · {{ formatDate(c.timestamp) }}</span>
										</div>
									</div>
									<button class="btn btn-primary btn-sm" @click="deployBench(bench)">
										▶ Deploy Now — include these {{ bench.undeployed_count }} commit{{ bench.undeployed_count !== 1 ? 's' : '' }}
									</button>
								</template>
								<div v-else class="no-gap-box">✓ Everything deployed. No pending commits.</div>
							</div>

							<!-- Tab: Recent Commits -->
							<div v-if="bs(bench.name).tab === 'commits'" class="panel-section">
								<div class="commit-list">
									<div v-for="c in bs(bench.name).data.recent_commits" :key="c.hash" class="commit-row">
										<div class="cr-msg">
											<span class="app-chip">{{ c.app }}</span>
											<span>{{ c.message }}</span>
										</div>
										<div class="cr-author">
											<div class="avatar">{{ (c.author || '?')[0].toUpperCase() }}</div>
											{{ c.author }}
										</div>
										<div class="cr-time">{{ formatDate(c.timestamp) }}</div>
										<span class="cr-hash">{{ c.hash }}</span>
									</div>
									<div v-if="!bs(bench.name).data.recent_commits?.length" class="text-gray-400 text-sm p-4">No commits found.</div>
								</div>
							</div>

							<!-- Tab: Sites Status -->
							<div v-if="bs(bench.name).tab === 'sites'" class="panel-section">
								<div class="site-list">
									<div
										v-for="site in bs(bench.name).data.sites"
										:key="site.name"
										class="site-item"
										:class="{
											'dev-on': site.is_development_site,
											current: site.status === 'Active',
											outdated: site.status !== 'Active',
										}"
									>
										<span class="sname">{{ site.host_name || site.name }}</span>
										<span :class="site.status === 'Active' ? 'badge badge-ok' : 'badge badge-warn'">
											{{ site.status === 'Active' ? 'Active' : site.status }}
										</span>
										<span :class="site.migrated ? 'mig-ok' : 'mig-fail'">
											{{ site.migrated ? '✓ migrated' : '⚠ not migrated' }}
										</span>
										<!-- Scheduler toggle -->
										<label class="sch-toggle" :title="site.scheduler_enabled ? 'Scheduler ON' : 'Scheduler OFF'" @click.stop>
											<input
												type="checkbox"
												:checked="site.scheduler_enabled"
												@change="toggleScheduler(site, $event)"
											/>
											<span class="sch-track"></span>
											<span class="sch-lbl">Sched</span>
										</label>
										<!-- Dev mode toggle -->
										<label class="dev-toggle" :title="site.is_development_site ? 'Disable developer_mode' : 'Enable developer_mode'" @click.stop>
											<input
												type="checkbox"
												:checked="!!site.is_development_site"
												@change="toggleSiteDevMode(site, $event)"
											/>
											<span class="dev-track"></span>
											<span class="dev-label">Dev</span>
										</label>
									</div>
									<div v-if="!bs(bench.name).data.sites?.length" class="text-gray-400 text-sm p-4">No sites in this bench.</div>
								</div>
							</div>

							<!-- Tab: Build History -->
							<div v-if="bs(bench.name).tab === 'builds'" class="panel-section">
								<div class="build-list">
									<div v-for="b in bs(bench.name).data.build_history" :key="b.name" class="build-item">
										<a class="bid" :href="`/dashboard/deploys/${b.name}`" @click.stop>{{ b.name }}</a>
										<span class="bdesc">{{ b.status }}</span>
										<span :class="buildBadgeClass(b.status)">
											<span class="badge-dot"></span>{{ b.status }}
										</span>
										<span class="bdur">{{ formatDate(b.creation) }}</span>
									</div>
									<div v-if="!bs(bench.name).data.build_history?.length" class="text-gray-400 text-sm p-4">No build history.</div>
								</div>
							</div>

							<!-- Tab: Errors -->
							<div v-if="bs(bench.name).tab === 'errors'" class="panel-section">
								<div class="error-list">
									<div v-for="err in bs(bench.name).data.errors?.errors" :key="err.name" class="error-item">
										<div class="error-site">
											<span>{{ err.site }}</span>
											<span>{{ formatDate(err.creation) }}</span>
										</div>
										<div class="error-msg">{{ err.job_type }}</div>
									</div>
									<div v-if="!bs(bench.name).data.errors?.count" class="no-errors">No errors in the last 24h</div>
								</div>
								<div v-if="bs(bench.name).data.errors?.count > 0" style="text-align:right;margin-top:8px">
									<a :href="`/dashboard/benches/${bench.name}`" style="font-size:12px;color:var(--blue-500)">View all errors →</a>
								</div>
							</div>
						</template>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script>
import { toast } from 'vue-sonner';
import Breadcrumbs from '@/components/global/Breadcrumbs.vue';
import Header from '@/components/Header.vue';
import { confirmDialog } from '@/utils/components';

const DEV_OVERVIEW_URL = 'press.press.doctype.bench.bench_dev_overview.get_dev_overview_benches';
const PANEL_URL = 'press.press.doctype.bench.bench_dev_overview.get_dev_panel_data';
const RUN_DOC_METHOD = 'press.api.client.run_doc_method';

export default {
	name: 'DevOverview',
	components: { Header, Breadcrumbs },

	data() {
		return {
			searchQuery: '',
			filterMode: 'all',
			expanded: null,
			// Consolidated per-bench panel state (2A: single reactive object)
			benchState: {},  // { [benchName]: { loading, data, tab } }
			filterOptions: [
				{ key: 'all', label: 'All' },
				{ key: 'updates', label: 'Has Updates' },
				{ key: 'undeployed', label: 'Undeployed' },
				{ key: 'failed', label: 'Failed' },
			],
		};
	},

	resources: {
		overviewRes() {
			return { url: DEV_OVERVIEW_URL, auto: true };
		},
		// 3A: shared action resource — one instance, no per-call leaks
		action() {
			return { url: RUN_DOC_METHOD };
		},
		// 3A: shared panel resource — reused per expand
		panelRes() {
			return { url: PANEL_URL };
		},
	},

	computed: {
		overviewRes() {
			return this.$resources.overviewRes;
		},
		benches() {
			return this.overviewRes.data || [];
		},
		filteredBenches() {
			let list = this.benches;
			const q = (this.searchQuery || '').toLowerCase().trim();
			if (q) {
				list = list.filter(
					(b) =>
						b.name.toLowerCase().includes(q) ||
						(b.group_title || '').toLowerCase().includes(q) ||
						(b.last_commit?.app || '').toLowerCase().includes(q) ||
						(b.last_commit?.message || '').toLowerCase().includes(q),
				);
			}
			if (this.filterMode === 'updates') list = list.filter((b) => b.pending_update_count > 0);
			if (this.filterMode === 'undeployed') list = list.filter((b) => b.undeployed_count > 0);
			if (this.filterMode === 'failed') list = list.filter((b) => b.status === 'Broken' || b.status === 'Archived');
			return list;
		},
		activeBenchCount() {
			return this.benches.filter((b) => b.status === 'Active').length;
		},
		serverCount() {
			return new Set(this.benches.map((b) => b.server).filter(Boolean)).size;
		},
		pendingUpdateCount() {
			return this.benches.reduce((s, b) => s + (b.pending_update_count || 0), 0);
		},
		pendingUpdateBenchCount() {
			return this.benches.filter((b) => b.pending_update_count > 0).length;
		},
		totalUndeployedCommits() {
			return this.benches.reduce((s, b) => s + (b.undeployed_count || 0), 0);
		},
		lastBuildBench() {
			const active = this.benches.filter((b) => b.status === 'Active');
			if (!active.length) return null;
			return active.reduce((latest, b) => {
				if (!latest) return b;
				return new Date(b.creation) > new Date(latest.creation) ? b : latest;
			}, null);
		},
		lastBuildAge() {
			if (!this.lastBuildBench) return '—';
			return this.formatDate(this.lastBuildBench.creation);
		},
		lastBuildSub() {
			if (!this.lastBuildBench) return '';
			return `${this.lastBuildBench.name}`;
		},
	},

	methods: {
		reload() {
			this.overviewRes.reload();
		},

		// 2A: helper to read consolidated bench state
		bs(benchName) {
			return this.benchState[benchName] || {};
		},

		_setBs(benchName, patch) {
			// Vue 3 proxy tracks direct property mutations — no full-object spread needed
			if (!this.benchState[benchName]) this.benchState[benchName] = {};
			Object.assign(this.benchState[benchName], patch);
		},

		toggleExpand(benchName) {
			if (this.expanded === benchName) {
				this.expanded = null;
			} else {
				this.expanded = benchName;
				if (!this.bs(benchName).tab) this._setBs(benchName, { tab: 'gap' });
				this.loadPanel(benchName);
			}
		},

		setTab(benchName, tabKey) {
			this._setBs(benchName, { tab: tabKey });
		},

		panelTabs(bench) {
			const errCount = this.bs(bench.name).data?.errors?.count || 0;
			return [
				{ key: 'gap', label: bench.undeployed_count > 0 ? '⚠ Undeployed Gap' : 'Undeployed Gap', count: 0 },
				{ key: 'commits', label: 'Recent Commits', count: 0 },
				{ key: 'sites', label: 'Sites Status', count: 0 },
				{ key: 'builds', label: 'Build History', count: 0 },
				{ key: 'errors', label: 'Errors', count: errCount },
			];
		},

		loadPanel(benchName) {
			// Concurrency invariant: `expanded` is a single string, so only one
			// bench panel can be open at a time — concurrent loadPanel calls cannot race.
			if (this.bs(benchName).data) return;
			this._setBs(benchName, { loading: true });
			// 3A: reuse shared panelRes resource
			this.$resources.panelRes.submit({ bench_name: benchName })
				.then((data) => this._setBs(benchName, { data, loading: false }))
				.catch(() => this._setBs(benchName, {
					data: { sites: [], recent_commits: [], build_history: [], errors: { count: 0, errors: [] } },
					loading: false,
				}));
		},

		// 3A: shared action resource — no new resource created per call
		runDocMethod(dt, dn, method, args = {}) {
			return this.$resources.action.submit({ dt, dn, method, ...args });
		},

		toggleDevBench(bench, event) {
			const enable = event.target.checked ? 1 : 0;
			this.runDocMethod('Bench', bench.name, 'set_development_bench', { enable })
				.then(() => {
					bench.is_development_bench = enable;
					toast.success(enable ? 'Marked as dev bench' : 'Dev bench flag removed');
					this.overviewRes.reload();
				})
				.catch((e) => {
					event.target.checked = !event.target.checked; // revert
					toast.error(e.messages?.join(', ') || 'Failed');
				});
		},

		restartBench(bench) {
			confirmDialog({
				title: 'Restart Bench',
				message: `Restart <b>${bench.name}</b>? Running processes will be interrupted.`,
				onSuccess: ({ hide }) => {
					return this.runDocMethod('Bench', bench.name, 'restart_bench')
						.then(() => {
							toast.success(`Bench ${bench.name} restarted`);
							hide();
						})
						.catch((e) => toast.error(e.messages?.join(', ') || 'Failed'));
				},
			});
		},

		deployBench(bench) {
			window.open(`/dashboard/benches/${bench.name}`, '_blank');
		},

		openGitHub(bench) {
			if (bench.group) {
				window.open(`${window.location.protocol}//${window.location.host}/app/release-group/${bench.group}`, '_blank');
			}
		},

		openVSCode(bench) {
			window.open('https://code.sandbox.mvpstorm.com', '_blank');
		},

		toggleScheduler(site, event) {
			const enable = event.target.checked ? 0 : 1; // pause_scheduler is inverse
			this.runDocMethod('Site', site.name, 'toggle_scheduler')
				.then(() => {
					site.scheduler_enabled = event.target.checked;
				})
				.catch((e) => {
					event.target.checked = !event.target.checked;
					toast.error(e.messages?.join(', ') || 'Failed');
				});
		},

		toggleSiteDevMode(site, event) {
			const enable = event.target.checked ? 1 : 0;
			this.runDocMethod('Site', site.name, 'set_development_mode', { enable })
				.then(() => {
					site.is_development_site = enable;
					toast.success(enable ? 'Developer mode enabled' : 'Developer mode disabled');
				})
				.catch((e) => {
					event.target.checked = !event.target.checked;
					toast.error(e.messages?.join(', ') || 'Failed');
				});
		},

		buildBadgeClass(status) {
			if (!status) return 'badge badge-gray';
			const s = status.toLowerCase();
			if (s === 'active' || s === 'success') return 'badge badge-ok';
			if (s.includes('build') || s === 'pending' || s === 'installing') return 'badge badge-running';
			if (s === 'broken' || s === 'failure' || s === 'failed') return 'badge badge-fail';
			return 'badge badge-gray';
		},

		formatDate(dateStr) {
			if (!dateStr) return '';
			try {
				const diff = Math.floor((Date.now() - new Date(dateStr)) / 1000);
				if (diff < 60) return 'just now';
				if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
				if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
				return `${Math.floor(diff / 86400)}d ago`;
			} catch {
				return dateStr;
			}
		},
	},
};
</script>

<style scoped>
/* ── Tokens matching Press / Frappe UI ───────────────────────────── */
:root {
	--purple-500: #6554c0;
	--purple-50: #f0ebff;
}

.content-wrap { padding: 24px 32px; }

/* ── Summary Cards ────────────────────────────────────────────────── */
.summary-grid {
	display: grid;
	grid-template-columns: repeat(4, 1fr);
	gap: 16px;
	margin-bottom: 20px;
}
.summary-card {
	background: #fff;
	border: 1px solid var(--gray-200, #e1e4e8);
	border-radius: 8px;
	padding: 16px 20px;
	border-top: 3px solid var(--gray-200, #e1e4e8);
}
.summary-card.warn {
	background: #fff8e6;
	border-color: #ffe380;
	border-top-color: #ff8b00;
}
.summary-card.danger {
	background: #ffebe6;
	border-color: #ffd2cc;
	border-top-color: #de350b;
}
.summary-card.ok {
	background: #e3fcef;
	border-color: #abf5d1;
	border-top-color: #00875a;
}
.s-label { font-size: 11px; color: var(--ink-gray-4, #97a0af); font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px; margin-bottom: 6px; }
.summary-card.warn .s-label { color: #b36200; }
.summary-card.danger .s-label { color: #ae2a19; }
.summary-card.ok .s-label { color: #006644; }
.s-value { font-size: 28px; font-weight: 700; color: var(--ink-gray-9, #172b4d); line-height: 1; }
.s-sub { font-size: 11px; color: var(--ink-gray-4, #97a0af); margin-top: 4px; }
.summary-card.warn .s-value { color: #ff8b00; }
.summary-card.danger .s-value { color: #de350b; }
.summary-card.ok .s-value { color: #00875a; }
.summary-card.warn .s-sub { color: #b36200; }
.summary-card.danger .s-sub { color: #ae2a19; }
.summary-card.ok .s-sub { color: #006644; }

/* ── Live badge ──────────────────────────────────────────────────── */
.live-badge {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	font-size: 11px;
	font-weight: 500;
	background: var(--green-100, #e3fcef);
	color: var(--green-600, #00875a);
	padding: 2px 8px;
	border-radius: 10px;
	margin-left: 10px;
}
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green-600, #00875a); animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

/* ── Filter Bar ──────────────────────────────────────────────────── */
.filter-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
.search-input {
	flex: 1; max-width: 300px;
	padding: 7px 12px;
	border: 1px solid #dfe1e6;
	border-radius: 6px;
	font-size: 13px;
}
.search-input:focus { outline: none; border-color: var(--blue-400, #3b9ae8); }
.fbtn {
	padding: 7px 14px;
	border: 1px solid #dfe1e6;
	border-radius: 6px;
	background: #fff;
	font-size: 13px;
	color: var(--ink-gray-6, #5e6c84);
	cursor: pointer;
}
.fbtn.active { background: var(--blue-50, #e8f0fe); color: var(--blue-500, #046bd2); border-color: var(--blue-400, #3b9ae8); }
.fbtn:hover:not(.active) { background: var(--surface-gray-1, #f4f5f7); }

/* ── Bench Table ─────────────────────────────────────────────────── */
.bench-table { background: #fff; border: 1px solid var(--gray-200, #e1e4e8); border-radius: 8px; overflow: hidden; }
.bench-table-header {
	display: grid;
	grid-template-columns: 2fr 2.5fr 1.4fr 1.2fr 1.3fr 140px;
	padding: 10px 20px;
	background: var(--surface-gray-3, #f8f9fa);
	border-bottom: 1px solid var(--gray-200, #e1e4e8);
	font-size: 11px; font-weight: 600; color: var(--ink-gray-4, #97a0af); text-transform: uppercase; letter-spacing: 0.4px;
}
.bench-row { border-bottom: 1px solid var(--surface-gray-1, #f4f5f7); }
.bench-row:last-child { border-bottom: none; }
.bench-row-main {
	display: grid;
	grid-template-columns: 2fr 2.5fr 1.4fr 1.2fr 1.3fr 140px;
	padding: 14px 20px;
	align-items: center;
	cursor: pointer;
}
.bench-row-main:hover { background: var(--surface-gray-2, #fafbfc); }
.bench-row.open > .bench-row-main { background: var(--surface-gray-2, #fafbfc); }
.bench-row.dev-bench > .bench-row-main { border-left: 3px solid #6554c0; padding-left: 17px; }
.bench-dev-tag { background: #f0ebff; color: #6554c0; font-size: 10px; font-weight: 700; padding: 1px 7px; border-radius: 4px; }

/* ── Bench Name Cell ─────────────────────────────────────────────── */
.bench-name strong { font-size: 13px; font-weight: 600; }
.bench-name small { font-size: 11px; color: var(--ink-gray-4, #97a0af); }

/* ── Commit Info Cell ────────────────────────────────────────────── */
.commit-info {}
.commit-msg { font-size: 13px; color: var(--blue-500, #046bd2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 260px; display: block; }
.commit-meta { font-size: 11px; color: var(--ink-gray-4, #97a0af); display: flex; align-items: center; gap: 6px; margin-top: 2px; }
.hash-chip { font-family: monospace; background: var(--surface-gray-1, #f4f5f7); padding: 1px 5px; border-radius: 3px; color: var(--ink-gray-6, #5e6c84); }
.app-chip { background: var(--blue-50, #e8f0fe); color: var(--blue-500, #046bd2); padding: 1px 6px; border-radius: 3px; font-size: 10px; font-weight: 500; }

/* ── Badges ──────────────────────────────────────────────────────── */
.badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 500; }
.badge-ok { background: var(--green-100, #e3fcef); color: var(--green-600, #00875a); }
.badge-running { background: var(--blue-50, #e8f0fe); color: var(--blue-500, #046bd2); }
.badge-fail { background: var(--red-100, #ffebe6); color: var(--red-600, #de350b); }
.badge-gray { background: var(--surface-gray-1, #f4f5f7); color: var(--ink-gray-6, #5e6c84); }
.badge-warn { background: var(--yellow-50, #fff8e6); color: var(--yellow-600, #ff8b00); }
.badge-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.badge-running .badge-dot { animation: pulse 1.2s infinite; }

/* ── Sites / Gap Cells ──────────────────────────────────────────── */
.sites-col .count { font-size: 13px; font-weight: 500; }
.sites-col .note { font-size: 11px; margin-top: 2px; }
.note-warn { color: var(--yellow-600, #ff8b00); font-weight: 500; }
.note-ok { color: var(--ink-gray-4, #97a0af); }
.gap-col .gap-warn { font-size: 12px; font-weight: 600; color: var(--red-600, #de350b); }
.gap-col .gap-ok { font-size: 12px; font-weight: 500; color: var(--green-600, #00875a); }
.gap-col .gap-sub { font-size: 11px; color: var(--ink-gray-4, #97a0af); margin-top: 1px; }

/* ── Row Action Buttons ──────────────────────────────────────────── */
.row-btns { display: flex; gap: 6px; justify-content: flex-end; }
.icon-btn {
	width: 30px; height: 30px;
	border-radius: 6px;
	border: 1px solid #dfe1e6;
	background: #fff;
	display: flex; align-items: center; justify-content: center;
	cursor: pointer;
	color: var(--ink-gray-6, #5e6c84);
}
.icon-btn:hover { background: var(--surface-gray-1, #f4f5f7); color: var(--ink-gray-9, #172b4d); }
.icon-btn svg { width: 14px; height: 14px; }
.vscode-btn { color: #007acc; }
.vscode-btn:hover { color: #007acc; }

/* ── Dev Bench Toggle ────────────────────────────────────────────── */
.dev-toggle { display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; flex-shrink: 0; }
.dev-toggle input[type=checkbox] { display: none; }
.dev-track { position: relative; width: 26px; height: 14px; background: #dfe1e6; border-radius: 8px; transition: background .18s; flex-shrink: 0; }
.dev-track::after { content: ''; position: absolute; top: 1px; left: 1px; width: 12px; height: 12px; background: #fff; border-radius: 50%; transition: transform .18s; box-shadow: 0 1px 2px rgba(0,0,0,.18); }
.dev-toggle input:checked + .dev-track { background: #6554c0; }
.dev-toggle input:checked + .dev-track::after { transform: translateX(12px); }
.dev-label { font-size: 10px; font-weight: 500; color: var(--ink-gray-4, #97a0af); white-space: nowrap; transition: color .18s; }
.dev-toggle input:checked ~ .dev-label { color: #6554c0; }

/* ── Scheduler Toggle ────────────────────────────────────────────── */
.sch-toggle { display: flex; align-items: center; gap: 5px; cursor: pointer; user-select: none; flex-shrink: 0; }
.sch-toggle input[type=checkbox] { display: none; }
.sch-track { position: relative; width: 28px; height: 15px; background: var(--red-600, #de350b); border-radius: 8px; transition: background .18s; flex-shrink: 0; }
.sch-track::after { content: ''; position: absolute; top: 1.5px; left: 1.5px; width: 12px; height: 12px; background: #fff; border-radius: 50%; transition: transform .18s; box-shadow: 0 1px 2px rgba(0,0,0,.15); }
.sch-toggle input:checked + .sch-track { background: var(--green-600, #00875a); }
.sch-toggle input:checked + .sch-track::after { transform: translateX(13px); }
.sch-lbl { font-size: 10px; font-weight: 500; color: var(--red-600, #de350b); white-space: nowrap; transition: color .18s; }
.sch-toggle input:checked ~ .sch-lbl { color: var(--green-600, #00875a); }

/* ── Expanded Panel ──────────────────────────────────────────────── */
.bench-panel { background: var(--surface-gray-2, #fafbfc); border-top: 1px solid #eaecef; padding: 16px 20px; }
.panel-tabs { display: flex; border-bottom: 1px solid var(--gray-200, #e1e4e8); margin-bottom: 14px; }
.ptab { padding: 8px 16px; font-size: 12px; font-weight: 500; color: var(--ink-gray-6, #5e6c84); cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px; }
.ptab:hover { color: var(--ink-gray-9, #172b4d); }
.ptab.active { color: var(--blue-500, #046bd2); border-bottom-color: var(--blue-500, #046bd2); }
.panel-section {}
.panel-loading { padding: 20px; text-align: center; font-size: 13px; color: var(--ink-gray-4, #97a0af); }
.err-badge { display: inline-flex; align-items: center; justify-content: center; background: var(--red-600, #de350b); color: #fff; border-radius: 8px; font-size: 10px; font-weight: 700; padding: 0 5px; min-width: 16px; height: 16px; margin-left: 3px; }

/* ── Gap Tab ─────────────────────────────────────────────────────── */
.gap-box { background: var(--yellow-50, #fff8e6); border: 1px solid #ffe380; border-radius: 6px; padding: 12px 16px; margin-bottom: 12px; }
.gap-box-title { font-size: 12px; font-weight: 600; color: var(--yellow-600, #ff8b00); margin-bottom: 8px; }
.gap-item { display: flex; gap: 10px; align-items: baseline; padding: 4px 0; font-size: 12px; color: var(--ink-gray-6, #5e6c84); border-bottom: 1px solid #fff0c0; }
.gap-item:last-child { border-bottom: none; }
.ghash { font-family: monospace; color: var(--blue-500, #046bd2); flex-shrink: 0; }
.gtime { color: var(--ink-gray-4, #97a0af); font-size: 11px; margin-left: auto; white-space: nowrap; }
.no-gap-box { background: var(--green-100, #e3fcef); border: 1px solid #abf5d1; border-radius: 6px; padding: 10px 16px; font-size: 13px; color: var(--green-600, #00875a); }
.btn { padding: 7px 14px; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; border: none; }
.btn-primary { background: var(--blue-500, #046bd2); color: #fff; }
.btn-sm { padding: 4px 10px; font-size: 12px; }

/* ── Commits Tab ─────────────────────────────────────────────────── */
.commit-list { display: flex; flex-direction: column; }
.commit-row { display: grid; grid-template-columns: 1fr auto auto auto; gap: 12px; align-items: center; padding: 9px 0; border-bottom: 1px solid #f0f1f3; }
.commit-row:last-child { border-bottom: none; }
.cr-msg { font-size: 13px; color: var(--ink-gray-9, #172b4d); }
.cr-author { display: flex; align-items: center; gap: 5px; font-size: 12px; color: var(--ink-gray-4, #97a0af); }
.avatar { width: 20px; height: 20px; border-radius: 50%; background: var(--blue-500, #046bd2); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; flex-shrink: 0; }
.cr-time { font-size: 11px; color: var(--ink-gray-4, #97a0af); white-space: nowrap; }
.cr-hash { font-family: monospace; font-size: 11px; color: var(--blue-500, #046bd2); }

/* ── Sites Tab ───────────────────────────────────────────────────── */
.site-list { display: flex; flex-direction: column; gap: 8px; }
.site-item { display: flex; align-items: center; gap: 12px; padding: 10px 14px; background: #fff; border: 1px solid var(--gray-200, #e1e4e8); border-radius: 6px; border-left-width: 3px; border-left-color: #36b37e; }
.site-item.outdated { border-left-color: var(--yellow-600, #ff8b00); }
.site-item.dev-on { border-left-color: #6554c0; }
.sname { font-size: 13px; font-weight: 500; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mig-ok { display: inline-flex; align-items: center; background: var(--green-100, #e3fcef); color: var(--green-600, #00875a); font-size: 10px; font-weight: 600; padding: 2px 7px; border-radius: 10px; white-space: nowrap; border: 1px solid #abf5d1; }
.mig-fail { display: inline-flex; align-items: center; background: var(--red-100, #ffebe6); color: var(--red-600, #de350b); font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 10px; white-space: nowrap; border: 1px solid #ffd2cc; }

/* ── Build History Tab ──────────────────────────────────────────── */
.build-list { display: flex; flex-direction: column; gap: 8px; }
.build-item { display: grid; grid-template-columns: 1fr 1fr auto auto; gap: 12px; align-items: center; padding: 10px 14px; background: #fff; border: 1px solid var(--gray-200, #e1e4e8); border-radius: 6px; }
.bid { font-family: monospace; font-size: 11px; color: var(--blue-500, #046bd2); text-decoration: none; }
.bdesc { font-size: 12px; color: var(--ink-gray-6, #5e6c84); }
.bdur { font-size: 11px; color: var(--ink-gray-4, #97a0af); font-family: monospace; }

/* ── Errors Tab ─────────────────────────────────────────────────── */
.error-list { display: flex; flex-direction: column; gap: 8px; }
.error-item { background: #fff; border: 1px solid #ffd2cc; border-left: 3px solid var(--red-600, #de350b); border-radius: 6px; padding: 10px 14px; }
.error-site { font-size: 11px; color: var(--ink-gray-6, #5e6c84); margin-bottom: 4px; display: flex; justify-content: space-between; }
.error-msg { font-size: 12px; font-family: monospace; color: var(--ink-gray-9, #172b4d); white-space: pre-wrap; word-break: break-word; line-height: 1.5; }
.no-errors { background: var(--green-100, #e3fcef); border: 1px solid #abf5d1; border-radius: 6px; padding: 10px 16px; font-size: 13px; color: var(--green-600, #00875a); }

.empty-state { text-align: center; padding: 40px; font-size: 14px; color: var(--ink-gray-4, #97a0af); }
</style>
