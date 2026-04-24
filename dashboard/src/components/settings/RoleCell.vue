<template>
	<select
		v-if="!disabled"
		class="rounded border border-gray-200 px-2 py-1 text-xs font-medium"
		:class="roleColor(currentRole)"
		:value="currentRole"
		@change="onChange"
	>
		<option v-for="r in allowedRoles" :key="r" :value="r">{{ r }}</option>
	</select>
	<span
		v-else
		class="rounded border border-transparent px-2 py-1 text-xs font-medium"
		:class="roleColor(currentRole)"
	>{{ currentRole || 'Viewer' }}</span>
</template>

<script setup>
defineProps({
	currentRole: { type: String, required: true },
	allowedRoles: { type: Array, required: true },
	disabled: { type: Boolean, default: true },
});

const emit = defineEmits(['change']);

function onChange(event) {
	emit('change', event.target.value);
}

function roleColor(role) {
	const map = {
		'Platform Admin': 'bg-red-50 text-red-700',
		'DevOps Admin':   'bg-orange-50 text-orange-700',
		'Developer':      'bg-blue-50 text-blue-700',
		'DevOps User':    'bg-green-50 text-green-700',
		'Implementor':    'bg-purple-50 text-purple-700',
		'Viewer':         'bg-gray-50 text-gray-700',
	};
	return map[role] || 'bg-gray-50 text-gray-700';
}
</script>