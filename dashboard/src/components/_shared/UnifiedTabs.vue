<template>
	<div class="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
		<!-- Tab strip — bold-only active style (no underline, no pill, no shape change).
		     Click active tab again to collapse the body. -->
		<div class="flex items-center bg-gray-50" :class="active ? 'border-b border-gray-200' : ''">
			<button
				v-for="t in tabs"
				:key="t.id"
				type="button"
				class="relative flex items-center gap-2 px-4 py-2.5 text-sm transition"
				:class="active === t.id
					? 'font-bold text-gray-900'
					: 'font-medium text-gray-500 hover:text-gray-900'"
				@click="toggle(t.id)"
			>
				<FeatherIcon
					v-if="t.icon"
					:name="t.icon"
					class="h-4 w-4"
					:class="active === t.id ? (t.iconActiveClass || 'text-gray-900') : 'text-gray-400'"
				/>
				<span>{{ t.label }}</span>
				<span v-if="t.badge !== undefined && t.badge !== null && t.badge !== ''" class="ml-1 rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-600">
					{{ t.badge }}
				</span>
			</button>
			<div class="ml-auto pr-4 text-[11px] text-gray-500">
				{{ activeTabObj?.tagline || (collapsible ? 'Click a tab to expand' : '') }}
			</div>
		</div>
		<!-- Active tab body — slot named after tab id -->
		<div v-if="active" class="bg-white">
			<slot :name="active" :active="active" />
		</div>
	</div>
</template>

<script setup>
import { computed, watch } from 'vue';
import { FeatherIcon } from 'frappe-ui';

const props = defineProps({
	// [{id, label, tagline?, icon?, iconActiveClass?, badge?}]
	tabs: { type: Array, required: true },
	// v-model: active tab id, or null when collapsed
	modelValue: { type: [String, null], default: null },
	// If true: clicking active tab again collapses body. If false: always one tab open.
	collapsible: { type: Boolean, default: true },
});

const emit = defineEmits(['update:modelValue']);

const active = computed({
	get: () => props.modelValue,
	set: (v) => emit('update:modelValue', v),
});

const activeTabObj = computed(() => props.tabs.find((t) => t.id === active.value));

function toggle(id) {
	if (props.collapsible && active.value === id) {
		active.value = null;
	} else {
		active.value = id;
	}
}

// If modelValue becomes invalid (tab list changed), reset
watch(
	() => props.tabs,
	(newTabs) => {
		if (active.value && !newTabs.find((t) => t.id === active.value)) {
			active.value = props.collapsible ? null : newTabs[0]?.id || null;
		}
	},
);
</script>
