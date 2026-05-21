<template>
	<div class="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
		<!-- Tab strip — shared style via tabClasses.js. Click active tab to collapse body. -->
		<div :class="[TAB_STRIP_PANEL_TOP, active ? TAB_STRIP_DIVIDER : '']">
			<button
				v-for="t in tabs"
				:key="t.id"
				type="button"
				:class="['relative', tabClass(active === t.id)]"
				@click="toggle(t.id)"
			>
				<FeatherIcon :name="t.icon" class="h-4 w-4" :class="active === t.id ? t.iconActiveClass : 'text-gray-400'" />
				<span>{{ t.label }}</span>
				<span v-if="t.badge" class="ml-1 rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-600">
					{{ t.badge }}
				</span>
			</button>
			<div class="ml-auto pr-4 text-[11px] text-gray-500">
				{{ activeTab?.tagline || 'Click a tab to expand' }}
			</div>
		</div>
		<!-- Active tab body — Active Tokens shows by default; other tabs lazy -->
		<div v-if="active" class="bg-white">
			<MCPActiveTokensBody v-if="active === 'tokens'" ref="tokensBody" @issue="$emit('issue')" />
			<MCPGuideBody v-else-if="active === 'guide'" />
			<MCPHowToBody v-else-if="active === 'howto'" />
			<MCPRecentCallsBody v-else-if="active === 'calls'" />
		</div>
	</div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { FeatherIcon } from 'frappe-ui';
import MCPActiveTokensBody from './MCPActiveTokensBody.vue';
import MCPGuideBody from './MCPGuideBody.vue';
import MCPHowToBody from './MCPHowToBody.vue';
import MCPRecentCallsBody from './MCPRecentCallsBody.vue';
import { TAB_STRIP_PANEL_TOP, TAB_STRIP_DIVIDER, tabClass } from '../_shared/tabClasses.js';

defineEmits(['issue']);

// Active Tokens is the default — most-used surface
const active = ref('tokens');

function toggle(id) {
	active.value = active.value === id ? null : id;
}

const tabs = [
	{
		id: 'tokens',
		label: 'Active Tokens',
		tagline: 'Your MCP access tokens — issue, copy, reissue, revoke',
		icon: 'key',
		iconActiveClass: 'text-indigo-600',
	},
	{
		id: 'guide',
		label: 'MCP Guide',
		tagline: 'Every tool — args, risk, copy-pasteable example',
		icon: 'book',
		iconActiveClass: 'text-emerald-600',
	},
	{
		id: 'howto',
		label: 'Quickstart',
		tagline: 'Issue a token, hand it to your AI agent, audit calls',
		icon: 'info',
		iconActiveClass: 'text-blue-600',
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

const tokensBody = ref(null);

// Exposed for MCPPanel: after a new token is issued, switch to the
// Active Tokens tab + refresh its list so the user sees their new row.
function refreshTokens() {
	active.value = 'tokens';
	// Wait a tick for the body to mount (if it wasn't open) before calling
	requestAnimationFrame(() => {
		tokensBody.value?.loadTokens?.();
	});
}

defineExpose({ refreshTokens });
</script>
