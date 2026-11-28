<template>
		<div>
			<div class="flex items-baseline justify-between gap-2 mb-2">
				<label class="text-sm font-medium text-gray-700">
					{{ label }}
				</label>
				<div class="text-xs text-gray-500">
					{{ scopeSummary }}
				</div>
			</div>

			<div class="mb-2 flex flex-wrap items-center gap-2">
				<input
					type="text"
					v-model="search"
					placeholder="Search tools..."
					class="flex-1 min-w-[180px] rounded border border-gray-300 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none"
				/>
				<Button v-for="(_, presetName) in PRESETS" :key="presetName"
					size="sm"
					@click="applyPreset(presetName)"
				>
					{{ presetName }}
				</Button>
				<Button size="sm" theme="gray" @click="clearScope">Clear</Button>
			</div>

			<slot name="notice" />
			<div class="space-y-2 max-h-[420px] overflow-y-auto pr-1">
				<div
					v-for="cat in TOOL_CATEGORIES"
					:key="cat.id"
					class="rounded border p-2"
					:class="categoryBorderClass(cat.tone)"
				>
					<div class="flex items-center justify-between mb-1.5">
						<div class="flex items-center gap-2">
							<span class="text-sm font-semibold text-gray-800">
								{{ cat.label }}
							</span>
							<span class="text-xs text-gray-500">
								({{ visibleToolsByCategory(cat.id).length }} visible · {{ selectedInCategory(cat.id) }} selected)
							</span>
						</div>
						<button
							type="button"
							class="text-xs text-blue-600 hover:underline"
							@click="toggleCategory(cat.id)"
						>
							{{ allCategorySelected(cat.id) ? 'Deselect all' : 'Select all' }}
						</button>
					</div>
					<div class="grid grid-cols-1 gap-x-3 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
						<label
							v-for="tool in visibleToolsByCategory(cat.id)"
							:key="tool"
							class="flex items-start gap-2 cursor-pointer hover:bg-white/60 rounded px-1.5 py-1 min-w-0"
							:title="TOOL_CATALOG[tool].desc"
						>
							<input
								type="checkbox"
								:value="tool"
								v-model="scope"
								class="mt-0.5 shrink-0"
							/>
							<span class="flex-1 min-w-0">
								<span class="block text-sm text-gray-800 leading-tight">
									{{ TOOL_CATALOG[tool].label || tool }}
									<span v-if="change(tool)" :class="change(tool) === 'Added' ? 'bg-green-100 text-green-800' : 'bg-gray-200 text-gray-700'" class="ml-1 rounded px-1 text-[10px]">{{ change(tool) }}</span>
								</span>
								<span class="block font-mono text-[10px] text-gray-400 leading-tight truncate">
									{{ tool }}
								</span>
							</span>
							<span :class="riskBadgeClass(TOOL_CATALOG[tool].risk)" class="shrink-0">
								{{ TOOL_CATALOG[tool].risk }}
							</span>
						</label>
					</div>
					<div
						v-if="visibleToolsByCategory(cat.id).length === 0"
						class="text-xs text-gray-400 italic px-1 py-0.5"
					>
						No tools in this category match your search.
					</div>
				</div>
			</div>

		</div>
</template>

<script setup>
// The Issue Token scope picker, shared with Edit tools (PRS-SP-22). With a baseline it marks each tool Added or
// Removed against it.
import { ref, computed } from 'vue';
import { Button } from 'frappe-ui';
import {
	TOOL_CATEGORIES,
	TOOL_CATALOG,
	ALL_TOOLS,
	PRESETS,
	riskBadgeClass,
	categoryBorderClass,
} from './_tool_catalog.js';

const props = defineProps({
	modelValue: { type: Array, default: () => [] },
	baseline: { type: Array, default: null },
	label: { type: String, default: 'Scope (tools this token can call)' },
});
const emit = defineEmits(['update:modelValue']);
const scope = computed({
	get: () => props.modelValue,
	set: (v) => emit('update:modelValue', v),
});
const search = ref('');

function visibleToolsByCategory(catId) {
	const q = search.value.trim().toLowerCase();
	return ALL_TOOLS.filter((tool) => {
		if (TOOL_CATALOG[tool].category !== catId) return false;
		if (!q) return true;
		return (
			tool.toLowerCase().includes(q) ||
			(TOOL_CATALOG[tool].label || '').toLowerCase().includes(q) ||
			(TOOL_CATALOG[tool].desc || '').toLowerCase().includes(q)
		);
	});
}
function selectedInCategory(catId) {
	return scope.value.filter((t) => TOOL_CATALOG[t]?.category === catId).length;
}
function allCategorySelected(catId) {
	const visible = visibleToolsByCategory(catId);
	if (visible.length === 0) return false;
	return visible.every((t) => scope.value.includes(t));
}
function toggleCategory(catId) {
	const visible = visibleToolsByCategory(catId);
	if (allCategorySelected(catId)) {
		scope.value = scope.value.filter((t) => !visible.includes(t));
	} else {
		scope.value = Array.from(new Set([...scope.value, ...visible]));
	}
}
function applyPreset(presetName) {
	scope.value = [...(PRESETS[presetName] || [])];
}
function clearScope() {
	scope.value = [];
}
function change(tool) {
	if (!props.baseline) return '';
	const was = props.baseline.includes(tool);
	const is = scope.value.includes(tool);
	if (is && !was) return 'Added';
	if (was && !is) return 'Removed';
	return '';
}
const scopeSummary = computed(() => {
	if (scope.value.length === 0) return 'No tools selected';
	const lows = scope.value.filter((t) => TOOL_CATALOG[t]?.risk === 'low').length;
	const meds = scope.value.filter((t) => TOOL_CATALOG[t]?.risk === 'medium').length;
	const highs = scope.value.filter((t) => TOOL_CATALOG[t]?.risk === 'high').length;
	const parts = [];
	if (lows) parts.push(`${lows} read-only`);
	if (meds) parts.push(`${meds} state-changing`);
	if (highs) parts.push(`${highs} high-risk`);
	return `${scope.value.length} tools · ${parts.join(' · ')}`;
});
</script>
