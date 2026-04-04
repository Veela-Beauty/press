<template>
	<div class="space-y-4">
		<!-- Stats row -->
		<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Active AI Users</p>
				<p class="mt-1 text-2xl font-bold">{{ stats.active_users || 0 }}</p>
				<p class="text-xs text-gray-400">of {{ stats.total_users || 0 }} members</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Tokens Today</p>
				<p class="mt-1 text-2xl font-bold" :class="tokenPct >= 80 ? 'text-orange-600' : ''">
					{{ formatTokens(stats.tokens_today) }}
				</p>
				<p class="text-xs text-gray-400">{{ tokenPct }}% of daily pool</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Blocked Actions</p>
				<p class="mt-1 text-2xl font-bold text-red-600">{{ stats.blocked_today || 0 }}</p>
				<p class="text-xs text-gray-400">linter catches today</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<p class="text-xs font-medium uppercase text-gray-500">Open Escalations</p>
				<p class="mt-1 text-2xl font-bold" :class="stats.open_escalations > 0 ? 'text-orange-600' : ''">
					{{ stats.open_escalations || 0 }}
				</p>
				<p class="text-xs text-gray-400">pending review</p>
			</div>
		</div>

		<!-- Anomaly alerts -->
		<div v-if="anomalies.length > 0" class="rounded-lg border border-gray-200 bg-white p-4">
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-sm font-semibold">Anomaly Alerts</h3>
				<span class="rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-medium text-orange-700">
					{{ anomalies.length }} active
				</span>
			</div>
			<div class="space-y-2">
				<div
					v-for="a in anomalies"
					:key="a.id"
					class="flex items-start gap-3 rounded-lg p-3 text-xs"
					:class="a.severity === 'danger' ? 'bg-red-50 text-red-700' : 'bg-orange-50 text-orange-700'"
				>
					<i class="fa fa-exclamation-triangle mt-0.5 flex-shrink-0"></i>
					<div class="flex-1">
						<strong>{{ a.title }}</strong> — {{ a.description }}
						<div class="mt-0.5 opacity-75">{{ a.detail }}</div>
					</div>
					<span class="text-[10px] text-gray-400">{{ a.time }}</span>
				</div>
			</div>
		</div>

		<!-- Global AI Rules -->
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-sm font-semibold">Global AI Rules — Technical</h3>
				<Button size="sm" variant="solid" @click="$emit('edit-rules')">Edit Policy</Button>
			</div>
			<div class="space-y-2">
				<div v-for="rule in technicalRules" :key="rule.name" class="flex items-center gap-3 rounded-lg border border-gray-100 px-3 py-2">
					<span
						class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded text-[10px] font-bold text-white"
						:class="rule.level === 'block' ? 'bg-red-500' : 'bg-orange-500'"
					>
						{{ rule.level === 'block' ? 'X' : '!' }}
					</span>
					<div class="flex-1">
						<p class="text-xs font-medium text-gray-800">{{ rule.name }}</p>
						<p class="text-[10px] text-gray-500">{{ rule.description }}</p>
					</div>
					<span
						class="rounded-full px-2 py-0.5 text-[10px] font-medium"
						:class="rule.level === 'block' ? 'bg-red-100 text-red-700' : 'bg-orange-100 text-orange-700'"
					>
						{{ rule.level === 'block' ? 'Hard block' : 'Soft block' }}
					</span>
				</div>
			</div>
		</div>

		<!-- Role-Level AI Limits -->
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<h3 class="mb-3 text-sm font-semibold">
				<i class="fa fa-id-badge mr-1 text-blue-600"></i>
				Role-Level AI Limits
			</h3>
			<table class="w-full text-xs">
				<thead>
					<tr class="border-b border-gray-100 text-left text-gray-500">
						<th class="py-2">Role</th>
						<th>Token Cap / Day</th>
						<th>AI on Prod</th>
						<th>Review Required</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="role in roleLimits" :key="role.name" class="border-b border-gray-50">
						<td class="py-2">
							<span class="rounded-full px-2 py-0.5 text-[10px] font-medium" :style="{ background: role.bg, color: role.fg }">
								{{ role.name }}
							</span>
						</td>
						<td>{{ role.tokenCap === 0 ? 'Unlimited' : role.tokenCap.toLocaleString() }}</td>
						<td>
							<span :class="role.prodAccess === 'blocked' ? 'text-red-600' : role.prodAccess === 'read-only' ? 'text-orange-600' : 'text-green-600'">
								{{ role.prodAccess }}
							</span>
						</td>
						<td>{{ role.reviewRequired }}</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

<script>
import { Button } from 'frappe-ui';

export default {
	name: 'AiGovernance',
	components: { Button },
	emits: ['edit-rules'],
	data() {
		return {
			stats: {},
			anomalies: [],
			technicalRules: [
				{ name: 'Raw SQL blocked', description: 'DELETE / DROP / TRUNCATE — removed from response + escalation', level: 'block' },
				{ name: 'App uninstall / destroy blocked', description: 'bench uninstall-app, bench destroy, rm -rf', level: 'block' },
				{ name: 'Production sites blocked', description: 'AI panel is read-only on production sites', level: 'block' },
				{ name: 'Daily token cap', description: 'Default 100K tokens/day per user. Warning at 80%.', level: 'warn' },
			],
			roleLimits: [
				{ name: 'Platform Admin', tokenCap: 0, prodAccess: 'full', reviewRequired: 'Optional', bg: '#ede9fe', fg: '#6d28d9' },
				{ name: 'DevOps Admin', tokenCap: 200_000, prodAccess: 'read-only', reviewRequired: 'Recommended', bg: '#dbeafe', fg: '#1d4ed8' },
				{ name: 'Developer', tokenCap: 100_000, prodAccess: 'blocked', reviewRequired: 'Recommended', bg: '#dcfce7', fg: '#15803d' },
				{ name: 'Implementor', tokenCap: 50_000, prodAccess: 'blocked', reviewRequired: 'Mandatory', bg: '#fef3c7', fg: '#a16207' },
				{ name: 'Viewer', tokenCap: 0, prodAccess: 'blocked', reviewRequired: 'N/A', bg: '#f3f4f6', fg: '#6b7280' },
			],
		};
	},
	computed: {
		tokenPct() {
			if (!this.stats.daily_pool || !this.stats.tokens_today) return 0;
			return Math.round((this.stats.tokens_today / this.stats.daily_pool) * 100);
		},
	},
	methods: {
		formatTokens(n) {
			if (!n) return '0';
			if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
			if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K';
			return n.toString();
		},
	},
};
</script>
