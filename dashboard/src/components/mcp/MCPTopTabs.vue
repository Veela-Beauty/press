<template>
	<div class="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
		<!-- Tab strip -->
		<div class="flex items-center border-b border-gray-200 bg-gray-50">
			<button
				v-for="t in tabs"
				:key="t.id"
				type="button"
				class="relative flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition"
				:class="active === t.id
					? 'bg-white text-gray-900 border-b-2 border-blue-600 -mb-px'
					: 'text-gray-600 hover:text-gray-900 hover:bg-white/60'"
				@click="active = t.id"
			>
				<FeatherIcon :name="t.icon" class="h-4 w-4" :class="active === t.id ? t.iconActiveClass : 'text-gray-400'" />
				<span>{{ t.label }}</span>
				<span v-if="t.badge" class="ml-1 rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-600">
					{{ t.badge }}
				</span>
			</button>
			<div class="ml-auto pr-4 text-[11px] text-gray-500">
				{{ activeTab?.tagline }}
			</div>
		</div>
		<!-- Active tab body -->
		<div class="bg-white">
			<MCPHowToBody v-if="active === 'howto'" />
			<MCPGuideBody v-else-if="active === 'guide'" />
			<MCPRecentCallsBody v-else-if="active === 'calls'" />
		</div>
	</div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { FeatherIcon } from 'frappe-ui';
import MCPHowToBody from './MCPHowToBody.vue';
import MCPGuideBody from './MCPGuideBody.vue';
import MCPRecentCallsBody from './MCPRecentCallsBody.vue';

const active = ref('howto');

const tabs = [
	{
		id: 'howto',
		label: 'How to use MCP',
		tagline: 'Issue a token, hand it to your AI agent, audit calls',
		icon: 'info',
		iconActiveClass: 'text-blue-600',
	},
	{
		id: 'guide',
		label: 'MCP Guide',
		tagline: 'Every tool — args, risk, copy-pasteable example',
		icon: 'book',
		iconActiveClass: 'text-emerald-600',
	},
	{
		id: 'calls',
		label: 'Recent Calls',
		tagline: 'Audit log — every MCP call, status, latency, error',
		icon: 'activity',
		iconActiveClass: 'text-amber-600',
	},
];

const activeTab = computed(() => tabs.find((t) => t.id === active.value));
</script>
