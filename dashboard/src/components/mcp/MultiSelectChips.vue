<template>
	<div class="space-y-1">
		<label v-if="label" class="block text-sm font-medium text-gray-700">{{ label }}</label>
		<div
			class="rounded border border-gray-300 bg-white p-2 focus-within:border-blue-500"
			:class="{ 'opacity-60 pointer-events-none': loading }"
		>
			<!-- Selected chips -->
			<div v-if="modelValue.length" class="mb-1.5 flex flex-wrap gap-1">
				<span
					v-for="val in modelValue"
					:key="val"
					class="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-800"
				>
					{{ labelFor(val) }}
					<button
						type="button"
						class="text-blue-600 hover:text-blue-900"
						:title="`Remove ${val}`"
						@click.stop="remove(val)"
					>
						×
					</button>
				</span>
			</div>

			<!-- Search input + dropdown -->
			<div class="relative">
				<input
					ref="inputRef"
					type="text"
					v-model="query"
					:placeholder="placeholder"
					class="w-full border-0 bg-transparent p-0 text-sm focus:outline-none focus:ring-0"
					@focus="open = true"
					@blur="onBlur"
					@keydown.enter.prevent="addFirst"
					@keydown.escape="open = false"
				/>
				<div
					v-if="open && filtered.length"
					ref="dropdownRef"
					class="absolute left-0 right-0 z-50 mt-1 max-h-64 overflow-y-auto rounded border border-gray-200 bg-white shadow-lg"
				>
					<button
						v-for="opt in filtered"
						:key="opt.value"
						type="button"
						class="block w-full text-left px-3 py-1.5 text-sm hover:bg-blue-50"
						:class="{ 'bg-blue-100': modelValue.includes(opt.value) }"
						@mousedown.prevent="toggle(opt.value)"
					>
						<span class="font-medium">{{ opt.label }}</span>
						<span v-if="opt.sub" class="ml-2 text-xs text-gray-500">{{ opt.sub }}</span>
						<span v-if="modelValue.includes(opt.value)" class="float-right text-blue-600">✓</span>
					</button>
				</div>
				<div v-else-if="open && !filtered.length && !loading" class="absolute left-0 right-0 z-50 mt-1 rounded border border-gray-200 bg-white p-3 text-xs text-gray-500 shadow-lg">
					{{ query ? `No matches for "${query}"` : (options.length === 0 ? 'No items available' : 'Type to search...') }}
				</div>
			</div>
		</div>
		<div v-if="hint" class="text-xs text-gray-500">{{ hint }}</div>
	</div>
</template>

<script setup>
import { ref, computed } from 'vue';

const props = defineProps({
	modelValue: { type: Array, default: () => [] },
	options: { type: Array, default: () => [] }, // [{ value, label, sub? }]
	label: { type: String, default: '' },
	placeholder: { type: String, default: 'Search and pick...' },
	hint: { type: String, default: '' },
	loading: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);

const query = ref('');
const open = ref(false);
const inputRef = ref(null);
const dropdownRef = ref(null);

const filtered = computed(() => {
	const q = query.value.trim().toLowerCase();
	if (!q) return props.options.slice(0, 50);
	return props.options
		.filter(
			(o) =>
				o.label.toLowerCase().includes(q) ||
				(o.sub || '').toLowerCase().includes(q) ||
				o.value.toLowerCase().includes(q),
		)
		.slice(0, 50);
});

function labelFor(val) {
	const opt = props.options.find((o) => o.value === val);
	return opt ? opt.label : val;
}

function toggle(val) {
	const set = new Set(props.modelValue);
	if (set.has(val)) set.delete(val);
	else set.add(val);
	emit('update:modelValue', Array.from(set));
	query.value = '';
	inputRef.value?.focus();
}

function remove(val) {
	emit('update:modelValue', props.modelValue.filter((v) => v !== val));
}

function addFirst() {
	if (filtered.value.length) toggle(filtered.value[0].value);
}

function onBlur(e) {
	// Use relatedTarget to deterministically close only when focus moves
	// outside the dropdown — avoids the 150ms setTimeout race.
	if (e.relatedTarget && dropdownRef.value?.contains(e.relatedTarget)) return;
	open.value = false;
}
</script>
