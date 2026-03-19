<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[
						{ label: 'Daman Backup', route: '/backups/overview' },
						{ label: 'Run Log' },
					]"
				/>
			</Header>
		</div>
		<div class="p-5">
			<!-- Tabs -->
			<div class="mb-4 flex gap-2 border-b">
				<button
					v-for="tab in tabs"
					:key="tab.value"
					class="border-b-2 px-4 py-2 text-sm font-medium transition-colors"
					:class="activeTab === tab.value
						? 'border-blue-500 text-blue-600'
						: 'border-transparent text-gray-500 hover:text-gray-700'"
					@click="activeTab = tab.value"
				>
					{{ tab.label }}
				</button>
			</div>

			<!-- Tab 1: History -->
			<div v-show="activeTab === 'history'">
				<ObjectList ref="runLogList" :options="listOptions" />
			</div>

			<!-- Tab 2: Analytics -->
			<div v-show="activeTab === 'analytics'">
				<!-- Summary Cards -->
				<div class="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-4">
					<div class="rounded-lg border bg-white p-4">
						<div class="text-sm text-gray-500">{{ 'Total Runs (30d)' }}</div>
						<div class="text-2xl font-semibold">{{ analytics.total_runs || 0 }}</div>
					</div>
					<div class="rounded-lg border bg-white p-4">
						<div class="text-sm text-gray-500">{{ 'Success Rate' }}</div>
						<div
							class="text-2xl font-semibold"
							:class="successRateColor"
						>
							{{ analytics.success_rate != null ? analytics.success_rate + '%' : '-' }}
						</div>
					</div>
					<div class="rounded-lg border bg-white p-4">
						<div class="text-sm text-gray-500">{{ 'Avg Duration' }}</div>
						<div class="text-2xl font-semibold">{{ formatDuration(analytics.avg_duration) }}</div>
					</div>
					<div class="rounded-lg border bg-white p-4">
						<div class="text-sm text-gray-500">{{ 'Total Data (MB)' }}</div>
						<div class="text-2xl font-semibold">{{ formatNumber(analytics.total_data_mb) }}</div>
					</div>
				</div>

				<!-- Charts 2x2 Grid -->
				<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
					<!-- Chart 1: Success/Fail Trend -->
					<div class="rounded-lg border bg-white p-4">
						<div class="mb-3 text-sm font-medium text-gray-700">{{ 'Success / Fail Trend (30d)' }}</div>
						<div ref="chartSuccessFail" class="chart-container"></div>
						<div v-if="!hasChartData('success_fail')" class="flex h-48 items-center justify-center text-sm text-gray-400">
							{{ 'No data available' }}
						</div>
					</div>

					<!-- Chart 2: Avg Duration Trend -->
					<div class="rounded-lg border bg-white p-4">
						<div class="mb-3 text-sm font-medium text-gray-700">{{ 'Avg Duration Trend (30d)' }}</div>
						<div ref="chartDuration" class="chart-container"></div>
						<div v-if="!hasChartData('duration')" class="flex h-48 items-center justify-center text-sm text-gray-400">
							{{ 'No data available' }}
						</div>
					</div>

					<!-- Chart 3: Total Data Backed Up -->
					<div class="rounded-lg border bg-white p-4">
						<div class="mb-3 text-sm font-medium text-gray-700">{{ 'Total Data Backed Up (30d)' }}</div>
						<div ref="chartData" class="chart-container"></div>
						<div v-if="!hasChartData('data_backed_up')" class="flex h-48 items-center justify-center text-sm text-gray-400">
							{{ 'No data available' }}
						</div>
					</div>

					<!-- Chart 4: Avg Compression Ratio -->
					<div class="rounded-lg border bg-white p-4">
						<div class="mb-3 text-sm font-medium text-gray-700">{{ 'Avg Compression Ratio (30d)' }}</div>
						<div ref="chartCompression" class="chart-container"></div>
						<div v-if="!hasChartData('compression')" class="flex h-48 items-center justify-center text-sm text-gray-400">
							{{ 'No data available' }}
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- Run Log Detail Dialog -->
		<Dialog v-model="detailDialogOpen" :options="{ title: selectedLog?.name || 'Run Log Details', size: 'xl' }">
			<template #body-content>
				<div v-if="selectedLog" class="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
					<!-- Section 1: Run Info -->
					<div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
						<div>
							<div class="text-xs text-gray-500">{{ 'Name' }}</div>
							<div class="text-sm font-medium font-mono">{{ selectedLog.name || '-' }}</div>
						</div>
						<div>
							<div class="text-xs text-gray-500">{{ 'Client' }}</div>
							<div class="text-sm font-medium">{{ selectedLog.client || '-' }}</div>
						</div>
						<div>
							<div class="text-xs text-gray-500">{{ 'Mode' }}</div>
							<Badge :label="selectedLog.mode || '-'" />
						</div>
						<div>
							<div class="text-xs text-gray-500">{{ 'Status' }}</div>
							<Badge :label="selectedLog.status || '-'" :theme="statusTheme(selectedLog.status)" />
						</div>
					</div>
					<div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
						<div>
							<div class="text-xs text-gray-500">{{ 'Exit Code' }}</div>
							<div class="text-sm font-medium">{{ selectedLog.exit_code ?? '-' }}</div>
						</div>
						<div>
							<div class="text-xs text-gray-500">{{ 'Job Queue' }}</div>
							<div class="text-sm font-medium">{{ selectedLog.job_queue || '-' }}</div>
						</div>
					</div>

					<!-- Section 2: Timing -->
					<div class="rounded border p-3">
						<div class="mb-2 text-sm font-medium text-gray-700">{{ 'Timing' }}</div>
						<div class="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
							<div>
								<div class="text-xs text-gray-500">{{ 'Started At' }}</div>
								<div>{{ formatDetailDate(selectedLog.started_at) }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">{{ 'Finished At' }}</div>
								<div>{{ formatDetailDate(selectedLog.finished_at) }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">{{ 'Duration' }}</div>
								<div>{{ formatDuration(selectedLog.duration_seconds) }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">{{ 'Duration Formatted' }}</div>
								<div>{{ selectedLog.duration_formatted || '-' }}</div>
							</div>
						</div>
					</div>

					<!-- Section 3: Stats -->
					<div class="rounded border p-3">
						<div class="mb-2 text-sm font-medium text-gray-700">{{ 'Stats' }}</div>
						<div class="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
							<div>
								<div class="text-xs text-gray-500">{{ 'Files Count' }}</div>
								<div>{{ selectedLog.files_count != null ? selectedLog.files_count.toLocaleString() : '-' }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">{{ 'Data Size (MB)' }}</div>
								<div>{{ formatNumber(selectedLog.data_size_mb) }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">{{ 'Compressed Size (MB)' }}</div>
								<div>{{ formatNumber(selectedLog.compressed_size_mb) }}</div>
							</div>
							<div>
								<div class="text-xs text-gray-500">{{ 'Compression Ratio' }}</div>
								<div>{{ selectedLog.compression_ratio != null ? selectedLog.compression_ratio.toFixed(2) : '-' }}</div>
							</div>
						</div>
					</div>

					<!-- Section 4: Output -->
					<div v-if="selectedLog.raw_tail" class="rounded border p-3">
						<div class="mb-2 text-sm font-medium text-gray-700">{{ 'Output' }}</div>
						<pre class="max-h-[300px] overflow-auto whitespace-pre-wrap rounded bg-gray-50 p-3 font-mono text-xs text-gray-700">{{ selectedLog.raw_tail }}</pre>
					</div>

					<!-- Section 5: Error -->
					<div v-if="selectedLog.error_json" class="rounded border border-red-200 bg-red-50 p-3">
						<div class="mb-2 text-sm font-medium text-red-700">{{ 'Error' }}</div>
						<pre class="max-h-[300px] overflow-auto whitespace-pre-wrap font-mono text-xs text-red-600">{{ formatJson(selectedLog.error_json) }}</pre>
					</div>

					<!-- Section 6: Stats JSON -->
					<div v-if="selectedLog.stats_json" class="rounded border p-3">
						<div class="mb-2 text-sm font-medium text-gray-700">{{ 'Stats JSON' }}</div>
						<pre class="max-h-[300px] overflow-auto whitespace-pre-wrap rounded bg-gray-50 p-3 font-mono text-xs text-gray-700">{{ formatJson(selectedLog.stats_json) }}</pre>
					</div>
				</div>
			</template>
			<template #actions>
				<Button @click="detailDialogOpen = false">{{ 'Close' }}</Button>
			</template>
		</Dialog>
	</div>
</template>

<script>
import ObjectList from '../../components/ObjectList.vue';
import { Button, Dialog, Badge, createResource } from 'frappe-ui';
import { date } from '../../utils/format';

export default {
	name: 'BackupRunLog',
	components: { ObjectList, Button, Dialog, Badge },
	data() {
		return {
			activeTab: 'history',
			detailDialogOpen: false,
			selectedLog: null,
			analytics: {},
			chartInstances: {},
		};
	},
	computed: {
		tabs() {
			return [
				{ label: 'History', value: 'history' },
				{ label: 'Analytics', value: 'analytics' },
			];
		},
		successRateColor() {
			const rate = this.analytics.success_rate;
			if (rate == null) return '';
			if (rate > 90) return 'text-green-600';
			if (rate > 70) return 'text-yellow-600';
			return 'text-red-600';
		},
		listOptions() {
			return {
				url: 'daman_backup.daman_backup.press_api.get_run_log_list',
				doctype: 'Backup Run Log',
				orderBy: 'started_at desc',
				columns: [
					{ label: 'Name', fieldname: 'name', width: 0.6 },
					{ label: 'Client', fieldname: 'client', width: 0.8 },
					{
						label: 'Mode',
						fieldname: 'mode',
						width: '100px',
						align: 'center',
						type: 'Badge',
					},
					{
						label: 'Status',
						fieldname: 'status',
						width: '120px',
						align: 'center',
						type: 'Badge',
					},
					{
						label: 'Started At',
						fieldname: 'started_at',
						width: 0.8,
						format: (value) => (value ? date(value, 'llll') : '-'),
					},
					{
						label: 'Duration',
						fieldname: 'duration_seconds',
						width: '100px',
						align: 'center',
						format: (value) => this.formatDuration(value),
					},
					{
						label: 'Files',
						fieldname: 'files_count',
						width: '80px',
						align: 'right',
						format: (value) => (value != null ? value.toLocaleString() : '-'),
					},
					{
						label: 'Size MB',
						fieldname: 'data_size_mb',
						width: '100px',
						align: 'right',
						format: (value) => this.formatNumber(value),
					},
					{
						label: 'Ratio',
						fieldname: 'compression_ratio',
						width: '80px',
						align: 'right',
						format: (value) => (value != null ? value.toFixed(2) : '-'),
					},
					{
						label: 'Exit',
						fieldname: 'exit_code',
						width: '60px',
						align: 'center',
						format: (value) => (value ?? '-'),
					},
				],
				onRowClick: (row) => {
					this.selectedLog = row;
					this.detailDialogOpen = true;
				},
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
						options: ['', 'success', 'error', 'failed', 'warning', 'running'],
					},
					{
						type: 'date',
						label: 'From Date',
						fieldname: 'started_at',
						operator: '>=',
					},
					{
						type: 'date',
						label: 'To Date',
						fieldname: 'started_at',
						operator: '<=',
					},
				],
			};
		},
	},
	watch: {
		activeTab(val) {
			if (val === 'analytics') {
				this.fetchAnalytics();
			}
		},
	},
	methods: {
		formatDetailDate(value) {
			if (!value) return '-';
			return date(value, 'llll');
		},
		formatDuration(seconds) {
			if (!seconds && seconds !== 0) return '-';
			seconds = Math.round(seconds);
			if (seconds < 60) return `${seconds}s`;
			if (seconds < 3600) {
				const m = Math.floor(seconds / 60);
				const s = seconds % 60;
				return `${m}m ${s}s`;
			}
			const h = Math.floor(seconds / 3600);
			const m = Math.floor((seconds % 3600) / 60);
			const s = seconds % 60;
			return `${h}h ${m}m ${s}s`;
		},
		formatNumber(value) {
			if (value == null) return '-';
			return Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 });
		},
		formatJson(value) {
			if (!value) return '';
			try {
				return JSON.stringify(JSON.parse(value), null, 2);
			} catch {
				return value;
			}
		},
		statusTheme(status) {
			const map = {
				success: 'green',
				error: 'red',
				failed: 'red',
				warning: 'orange',
				running: 'blue',
			};
			return map[(status || '').toLowerCase()] || 'gray';
		},
		hasChartData(key) {
			const trends = this.analytics.trends;
			if (!trends) return false;
			if (key === 'success_fail') return trends.dates && trends.dates.length > 0;
			if (key === 'duration') return trends.avg_duration && trends.avg_duration.length > 0;
			if (key === 'data_backed_up') return trends.total_data && trends.total_data.length > 0;
			if (key === 'compression') return trends.avg_compression && trends.avg_compression.length > 0;
			return false;
		},
		fetchAnalytics() {
			if (!this._analyticsResource) {
				this._analyticsResource = createResource({
					url: 'daman_backup.daman_backup.press_api.get_run_log_analytics',
					onSuccess: (result) => {
						this.analytics = result || {};
						this.$nextTick(() => this.renderCharts());
					},
					onError: () => {
						this.analytics = {};
					},
				});
			}
			this._analyticsResource.submit({});
		},
		renderCharts() {
			// Destroy old chart instances
			Object.values(this.chartInstances).forEach((c) => {
				if (c && typeof c.destroy === 'function') c.destroy();
			});
			this.chartInstances = {};

			const trends = this.analytics.trends;
			if (!trends || !trends.dates || !trends.dates.length) return;

			const hasFrappeChart = typeof frappe !== 'undefined' && frappe.Chart;

			if (hasFrappeChart) {
				this.renderFrappeCharts(trends);
			} else {
				this.renderFallbackCharts(trends);
			}
		},
		renderFrappeCharts(trends) {
			// Chart 1: Success/Fail stacked bar
			if (this.$refs.chartSuccessFail && trends.success_counts) {
				this.chartInstances.successFail = new frappe.Chart(this.$refs.chartSuccessFail, {
					type: 'bar',
					height: 200,
					data: {
						labels: trends.dates,
						datasets: [
							{ name: 'Success', values: trends.success_counts, chartType: 'bar' },
							{ name: 'Failed', values: trends.fail_counts || [], chartType: 'bar' },
						],
					},
					colors: ['#22c55e', '#ef4444'],
					barOptions: { stacked: true },
					axisOptions: { xIsSeries: true },
				});
			}

			// Chart 2: Avg Duration trend line
			if (this.$refs.chartDuration && trends.avg_duration) {
				this.chartInstances.duration = new frappe.Chart(this.$refs.chartDuration, {
					type: 'line',
					height: 200,
					data: {
						labels: trends.dates,
						datasets: [
							{ name: 'Avg Duration (s)', values: trends.avg_duration, chartType: 'line' },
						],
					},
					colors: ['#3b82f6'],
					axisOptions: { xIsSeries: true },
					lineOptions: { regionFill: 1 },
				});
			}

			// Chart 3: Total Data Backed Up (cumulative area)
			if (this.$refs.chartData && trends.total_data) {
				this.chartInstances.data = new frappe.Chart(this.$refs.chartData, {
					type: 'line',
					height: 200,
					data: {
						labels: trends.dates,
						datasets: [
							{ name: 'Data (MB)', values: trends.total_data, chartType: 'line' },
						],
					},
					colors: ['#8b5cf6'],
					axisOptions: { xIsSeries: true },
					lineOptions: { regionFill: 1 },
				});
			}

			// Chart 4: Avg Compression Ratio
			if (this.$refs.chartCompression && trends.avg_compression) {
				this.chartInstances.compression = new frappe.Chart(this.$refs.chartCompression, {
					type: 'line',
					height: 200,
					data: {
						labels: trends.dates,
						datasets: [
							{ name: 'Compression Ratio', values: trends.avg_compression, chartType: 'line' },
						],
					},
					colors: ['#f59e0b'],
					axisOptions: { xIsSeries: true },
					lineOptions: { regionFill: 1 },
				});
			}
		},
		renderFallbackCharts(trends) {
			// Pure HTML/CSS bar charts as fallback when frappe.Chart is not available
			const renderBars = (el, values, color, label) => {
				if (!el || !values || !values.length) return;
				const max = Math.max(...values, 1);
				el.innerHTML = `
					<div style="display:flex;align-items:flex-end;gap:2px;height:200px;padding-top:8px;">
						${values.map((v, i) => {
							const pct = Math.max((v / max) * 100, 1);
							const dt = trends.dates[i] || '';
							return `<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;" title="${dt}: ${v}">
								<div style="width:100%;max-width:24px;background:${color};border-radius:2px 2px 0 0;height:${pct}%;min-height:2px;transition:height 0.3s;"></div>
							</div>`;
						}).join('')}
					</div>
					<div style="text-align:center;font-size:11px;color:#6b7280;margin-top:4px;">${label}</div>
				`;
			};

			renderBars(this.$refs.chartSuccessFail, trends.success_counts, '#22c55e', 'Success counts');
			renderBars(this.$refs.chartDuration, trends.avg_duration, '#3b82f6', 'Avg duration (s)');
			renderBars(this.$refs.chartData, trends.total_data, '#8b5cf6', 'Data (MB)');
			renderBars(this.$refs.chartCompression, trends.avg_compression, '#f59e0b', 'Compression ratio');
		},
	},
	beforeUnmount() {
		Object.values(this.chartInstances).forEach((c) => {
			if (c && typeof c.destroy === 'function') c.destroy();
		});
	},
};
</script>

<style scoped>
.chart-container {
	min-height: 200px;
}
</style>
