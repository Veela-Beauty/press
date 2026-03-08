<template>
	<router-link custom v-slot="{ href, navigate }" :to="item.route">
		<a
			:href="href"
			@click="navigate"
			class="as-nav-item flex items-center rounded px-2 py-1 transition"
			:class="[
				item.isActive ? 'as-nav-active' : 'as-nav-inactive',
				item.disabled ? 'pointer-events-none opacity-50' : '',
				$attrs.class,
			]"
		>
			<div class="flex w-full items-center space-x-2">
				<span class="grid h-5 w-6 place-items-center">
					<component :is="item.icon" class="h-4 w-4 as-nav-icon" />
				</span>
				<span class="text-sm">{{ item.name }}</span>
				<component :is="item.badge" />
			</div>
		</a>
	</router-link>
</template>

<script setup>
let props = defineProps({
	item: {
		type: Object,
		required: true,
	},
});
</script>

<style scoped>
/* Rebrand: Dark sidebar nav items */
.as-nav-item {
	color: rgba(255,255,255,0.65);
}
.as-nav-icon {
	color: rgba(255,255,255,0.5);
}
.as-nav-inactive:hover {
	color: white;
	background: rgba(255,255,255,0.08);
}
.as-nav-inactive:hover .as-nav-icon {
	color: rgba(255,255,255,0.8);
}
.as-nav-active {
	color: white;
	background: #046BD2;
}
.as-nav-active .as-nav-icon {
	color: white;
}
</style>
