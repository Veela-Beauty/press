<template>
	<div class="space-y-4">
		<div class="flex items-center justify-between">
			<div>
				<h3 class="text-base font-semibold">Gateway Ops: Performance</h3>
				<p class="text-xs text-gray-500">Scope: all clients · from the gateway request log</p>
			</div>
			<select v-model="period" class="rounded border border-gray-200 px-2 py-1 text-xs">
				<option value="week">Last 7 days</option>
				<option value="month">Last 30 days</option>
			</select>
		</div>

		<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Requests</p>
				<p class="mt-1 text-2xl font-bold">{{ fmtNum(overall.calls) }}</p>
				<p class="text-xs text-gray-400">{{ throughputPerDay }}/day · peak {{ peak }}</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Latency p50 / p95</p>
				<p class="mt-1 text-2xl font-bold">{{ fmtMs(overall.p50_ms) }} <small class="text-sm font-normal text-gray-400">/ {{ fmtMs(overall.p95_ms) }}</small></p>
				<p class="text-xs text-gray-400">median / tail</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Cost (window)</p>
				<p class="mt-1 text-2xl font-bold">${{ Number(overall.spend || 0).toFixed(4) }}</p>
				<p class="text-xs text-gray-400">gateway spend</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Slowest model</p>
				<p class="mt-1 truncate text-lg font-bold" :title="slowest.model">{{ short(slowest.model) }}</p>
				<p class="text-xs" :class="slowest.p95_ms > 15000 ? 'text-red-600' : 'text-gray-400'">p95 {{ fmtMs(slowest.p95_ms) }}</p>
			</div>
		</div>

		<!-- Reliability & SLO: a slow answer angers users even when it succeeds -->
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<div class="mb-3">
				<h4 class="text-xs font-semibold uppercase text-gray-500">Reliability &amp; SLO</h4>
				<p class="text-xs text-gray-400">A slow answer frustrates users even when it succeeds. Flag line: {{ sloSec }}s (set in AI Gateway Settings).</p>
			</div>
			<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
				<div>
					<p class="text-xs text-gray-500">Success rate</p>
					<p class="mt-1 text-2xl font-bold" :class="rel.success_rate_pct >= 99 ? 'text-green-700' : rel.success_rate_pct >= 95 ? 'text-amber-600' : 'text-red-600'">{{ pct(rel.success_rate_pct) }}</p>
					<p class="text-xs text-gray-400">{{ fmtNum(rel.served) }} served</p>
				</div>
				<div>
					<p class="text-xs text-gray-500">Slow answers</p>
					<p class="mt-1 text-2xl font-bold" :class="rel.slow > 0 ? 'text-amber-600' : 'text-gray-900'">{{ fmtNum(rel.slow) }}</p>
					<p class="text-xs text-gray-400">{{ pct(rel.slow_rate_pct) }} of answers &gt; {{ sloSec }}s</p>
				</div>
				<div>
					<p class="text-xs text-gray-500">Timeouts</p>
					<p class="mt-1 text-2xl font-bold" :class="rel.timeouts > 0 ? 'text-red-600' : 'text-gray-900'">{{ fmtNum(rel.timeouts) }}</p>
					<p class="text-xs text-gray-400">failed after {{ sloSec }}s</p>
				</div>
				<div>
					<p class="text-xs text-gray-500">Rejected</p>
					<p class="mt-1 text-2xl font-bold text-gray-400">{{ fmtNum(rel.rejected) }}</p>
					<p class="text-xs text-gray-400">health checks + probes</p>
				</div>
			</div>
			<div v-if="slowModels.length" class="mt-4">
				<p class="mb-2 text-xs font-semibold uppercase text-gray-500">Slow-answer watch</p>
				<div v-for="m in slowModels" :key="m.model" class="mb-2.5">
					<div class="flex items-center justify-between text-xs">
						<span class="font-mono text-gray-700">{{ short(m.model) }}</span>
						<span class="text-gray-500">{{ m.slow }} slow / {{ m.success }} · p95 {{ fmtMs(m.p95_ms) }} · max {{ fmtMs(m.max_ms) }}</span>
					</div>
					<div class="mt-1 h-2 rounded-full bg-gray-100">
						<div class="h-full rounded-full" :class="m.p95_ms > sloMs ? 'bg-red-500' : m.p95_ms > sloMs * 0.5 ? 'bg-amber-500' : 'bg-green-600'" :style="{ width: barSlow(m.slow) }"></div>
					</div>
				</div>
				<p class="mt-2 text-[11px] text-gray-400">Worst: {{ short(rel.worst_model && rel.worst_model.model) }}. Route complex queries to a faster model to cut the wait.</p>
			</div>
			<p v-else class="mt-3 text-xs text-gray-400">No answers crossed the {{ sloSec }}s line in this window.</p>
		</div>

		<div class="grid gap-3 lg:grid-cols-2">
			<!-- Provider comparison -->
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<h4 class="mb-1 text-xs font-semibold uppercase text-gray-500">Provider comparison</h4>
				<p class="mb-3 text-xs text-gray-400">p95 latency by model. Route toward the faster provider.</p>
				<div v-if="!providers.length" class="py-6 text-center text-xs text-gray-400">No requests in this window.</div>
				<div v-for="p in providers" :key="p.model" class="mb-2.5">
					<div class="flex items-center justify-between text-xs">
						<span class="font-mono text-gray-700">{{ short(p.model) }}</span>
						<span class="text-gray-500">{{ fmtMs(p.p95_ms) }} · {{ p.calls }} calls</span>
					</div>
					<div class="mt-1 h-2 rounded-full bg-gray-100">
						<div class="h-full rounded-full" :class="p.p95_ms > 15000 ? 'bg-red-500' : p.p95_ms > 7000 ? 'bg-amber-500' : 'bg-green-600'" :style="{ width: barMs(p.p95_ms) }"></div>
					</div>
				</div>
			</div>

			<!-- Daily throughput -->
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<h4 class="mb-3 text-xs font-semibold uppercase text-gray-500">Daily requests</h4>
				<div v-if="!daily.length" class="py-6 text-center text-xs text-gray-400">No activity yet.</div>
				<div v-else class="flex h-32 items-end gap-1">
					<div v-for="d in daily" :key="d.day" class="flex flex-1 flex-col items-center justify-end" :title="d.day + ': ' + d.calls">
						<div class="w-full rounded-t bg-gray-800" :style="{ height: barDay(d.calls) }"></div>
						<span class="mt-1 rotate-0 text-[9px] text-gray-400">{{ d.day }}</span>
					</div>
				</div>
			</div>
		</div>

		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<h4 class="mb-3 text-xs font-semibold uppercase text-gray-500">Providers detail</h4>
			<table class="w-full text-xs">
				<thead>
					<tr class="border-b border-gray-100 text-left text-gray-500">
						<th class="py-2">Model</th><th class="text-right">Calls</th><th class="text-right">p50</th><th class="text-right">p95</th><th class="text-right">Avg tokens</th><th class="text-right">Spend</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="p in providers" :key="p.model" class="border-b border-gray-50">
						<td class="py-2 font-mono text-gray-700">{{ p.model }}</td>
						<td class="text-right">{{ p.calls }}</td>
						<td class="text-right text-gray-500">{{ fmtMs(p.p50_ms) }}</td>
						<td class="text-right text-gray-500">{{ fmtMs(p.p95_ms) }}</td>
						<td class="text-right text-gray-500">{{ fmtNum(p.avg_tokens) }}</td>
						<td class="text-right mono">${{ Number(p.spend || 0).toFixed(4) }}</td>
					</tr>
					<tr v-if="loading"><td colspan="6" class="py-6 text-center text-gray-400">Loading…</td></tr>
				</tbody>
			</table>
			<p class="mt-3 text-[11px] text-gray-400">Success, slow, and timeout rates are above. Worker concurrency and the tool-vs-model latency split are not in the gateway log; they come from agent-run duration on the client (next).</p>
		</div>
	</div>
</template>

<script>
import { call } from 'frappe-ui';

export default {
	name: 'AiGatewayOps',
	data() {
		return {
			period: 'month',
			loading: false,
			overall: { calls: 0, p50_ms: 0, p95_ms: 0, spend: 0 },
			providers: [],
			daily: [],
			rel: { success_rate_pct: 0, slow_rate_pct: 0, served: 0, slow: 0, timeouts: 0, rejected: 0, slo_ms: 20000, per_model: [], worst_model: {} },
			throughputPerDay: 0,
			peak: 0,
		};
	},
	computed: {
		slowest() {
			if (!this.providers.length) return { model: '(none)', p95_ms: 0 };
			return this.providers.reduce((a, b) => (b.p95_ms > a.p95_ms ? b : a));
		},
		sloMs() { return Number(this.rel.slo_ms || 20000); },
		sloSec() { return Math.round(this.sloMs / 1000); },
		slowModels() { return (this.rel.per_model || []).filter((m) => m.slow > 0 || m.timeouts > 0); },
	},
	mounted() { this.load(); },
	watch: { period() { this.load(); } },
	methods: {
		async load() {
			this.loading = true;
			this.providers = []; this.daily = [];
			try {
				const d = await call('sanad_ai_control_center.gateway.ops.get_gateway_ops', { period: this.period });
				this.overall = d.overall || this.overall;
				this.providers = (d.providers || []).filter((p) => p.model !== '(none)');
				this.daily = d.daily || [];
				this.rel = d.reliability || this.rel;
				this.throughputPerDay = d.throughput_per_day || 0;
				this.peak = d.peak_per_day || 0;
			} catch (e) { /* control-center unreachable */ }
			this.loading = false;
		},
		fmtNum(n) { return Number(n || 0).toLocaleString('en-US'); },
		fmtMs(ms) { const n = Number(ms || 0); return n >= 1000 ? (n / 1000).toFixed(1) + 's' : Math.round(n) + 'ms'; },
		pct(n) { return Number(n || 0).toFixed(1) + '%'; },
		short(m) { return String(m || '').split('/').pop(); },
		barMs(ms) { const max = Math.max(...this.providers.map((p) => p.p95_ms), 1); return Math.max(3, Math.round((ms / max) * 100)) + '%'; },
		barSlow(c) { const max = Math.max(...this.slowModels.map((m) => m.slow), 1); return Math.max(6, Math.round((c / max) * 100)) + '%'; },
		barDay(c) { const max = Math.max(...this.daily.map((d) => d.calls), 1); return Math.max(4, Math.round((c / max) * 100)) + '%'; },
	},
};
</script>
