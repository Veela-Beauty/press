<template>
	<div class="space-y-4">
		<!-- Cost summary -->
		<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Revenue (SAR)</p>
				<p class="mt-1 text-2xl font-bold">{{ fmtSar(revenueSar) }}</p>
				<p class="text-xs text-gray-400">{{ activeSeats }} active × SAR {{ fmtSar(sellPrice) }}/seat</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Cost (SAR)</p>
				<p class="mt-1 text-2xl font-bold">{{ fmtSar(costSar) }}</p>
				<p class="text-xs text-gray-400">${{ totalCost.toFixed(2) }} gateway spend</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Margin (SAR)</p>
				<p class="mt-1 text-2xl font-bold" :class="marginSar >= 0 ? 'text-green-600' : 'text-red-600'">{{ fmtSar(marginSar) }}</p>
				<p class="text-xs text-gray-400">{{ marginPct }}% margin</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Active seats</p>
				<p class="mt-1 text-2xl font-bold">{{ activeSeats }}</p>
				<p class="text-xs text-gray-400">{{ totalSessions }} provisioned</p>
			</div>
		</div>

		<!-- Usage by user -->
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-sm font-semibold">Usage by User</h3>
				<select v-model="period" class="rounded border border-gray-200 px-2 py-1 text-xs">
					<option value="today">Today</option>
					<option value="week">Last 7 days</option>
					<option value="month">This month</option>
				</select>
			</div>
			<div class="space-y-2">
				<div class="grid grid-cols-[140px_1fr_80px_80px] gap-2 border-b border-gray-100 pb-1 text-[10px] font-semibold text-gray-500">
					<span>User</span><span>Usage</span><span class="text-right">Tokens</span><span class="text-right">Est. cost</span>
				</div>
				<div
					v-for="u in userUsage"
					:key="u.user"
					class="grid grid-cols-[140px_1fr_80px_80px] items-center gap-2"
				>
					<div>
						<p class="text-xs font-semibold text-gray-800">{{ u.user.split('@')[0] }}</p>
						<p class="text-[10px] text-gray-400">{{ u.role }} / {{ u.provider }}</p>
					</div>
					<div class="h-1.5 rounded-full bg-gray-100">
						<div
							class="h-full rounded-full"
							:class="u.pct >= 80 ? 'bg-red-500' : u.pct >= 50 ? 'bg-yellow-500' : 'bg-green-500'"
							:style="{ width: u.pct + '%' }"
						></div>
					</div>
					<span class="text-right text-xs">{{ formatTokens(u.tokens) }}</span>
					<span class="text-right text-xs text-gray-500">${{ u.cost.toFixed(2) }}</span>
				</div>
			</div>
		</div>
	</div>
</template>

<script>
import { call } from 'frappe-ui';

export default {
	name: 'AiUsageCost',
	data() {
		return {
			period: 'month',
			totalCost: 0,
			totalTokens: 0,
			inputTokens: 0,
			outputTokens: 0,
			totalSessions: 0,
			avgDuration: 0,
			providerBreakdown: '',
			userUsage: [],
			activeSeats: 0,
			sellPrice: 0,
			revenueSar: 0,
			costSar: 0,
			marginSar: 0,
			marginPct: 0,
		};
	},
	mounted() {
		this.load();
	},
	watch: {
		period() {
			this.load();
		},
	},
	methods: {
		async load() {
			// Live per-seat usage from the gateway control plane (same site).
			// Soft-fail: if the control-center app isn't reachable, keep zeros.
			try {
				const d = await call('sanad_ai_control_center.api.get_usage_cost', { period: this.period });
				this.totalCost = d.total_cost;
				this.totalTokens = d.total_tokens;
				this.inputTokens = d.input_tokens;
				this.outputTokens = d.output_tokens;
				this.totalSessions = d.total_sessions;
				this.avgDuration = d.avg_duration;
				this.providerBreakdown = d.provider_breakdown;
				this.userUsage = d.user_usage;
				this.activeSeats = d.active_seats || 0;
				this.sellPrice = d.sell_price_per_seat_sar || 0;
				this.revenueSar = d.revenue_sar || 0;
				this.costSar = d.cost_sar || 0;
				this.marginSar = d.margin_sar || 0;
				this.marginPct = d.margin_pct || 0;
			} catch (e) {
				// control-center unreachable — leave the empty state
			}
		},
		formatTokens(n) {
			if (!n) return '0';
			if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
			if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K';
			return n.toString();
		},
		fmtSar(n) {
			return Number(n || 0).toLocaleString('en-US', { maximumFractionDigits: 0 });
		},
	},
};
</script>
