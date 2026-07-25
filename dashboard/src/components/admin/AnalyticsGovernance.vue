<template>
	<div>
		<div class="mb-4">
			<h2 class="text-lg font-semibold">Analytics &amp; Governance</h2>
			<p class="text-xs text-gray-500">Adoption, economics, governance, and gateway performance.</p>
		</div>
		<div class="mb-5 flex gap-1 border-b border-gray-200">
			<button
				v-for="t in tabs"
				:key="t.id"
				@click="tab = t.id"
				class="-mb-px border-b-2 px-4 py-2.5 text-sm"
				:class="tab === t.id ? 'border-gray-900 font-semibold text-gray-900' : 'border-transparent text-gray-500 hover:text-gray-900'"
			>{{ t.label }}</button>
		</div>
		<AiInsights v-if="tab === 'insights'" />
		<AiUsageCost v-else-if="tab === 'cost'" />
		<AiGovernance v-else-if="tab === 'gov'" @edit-rules="$emit('edit-rules')" />
		<AiGatewayOps v-else-if="tab === 'ops'" />
	</div>
</template>

<script>
import AiInsights from './AiInsights.vue';
import AiUsageCost from './AiUsageCost.vue';
import AiGovernance from './AiGovernance.vue';
import AiGatewayOps from './AiGatewayOps.vue';

export default {
	name: 'AnalyticsGovernance',
	components: { AiInsights, AiUsageCost, AiGovernance, AiGatewayOps },
	emits: ['edit-rules'],
	data() {
		return {
			tab: 'insights',
			tabs: [
				{ id: 'insights', label: 'Insights' },
				{ id: 'cost', label: 'Usage & Cost' },
				{ id: 'gov', label: 'Governance' },
				{ id: 'ops', label: 'Gateway Ops' },
			],
		};
	},
};
</script>
