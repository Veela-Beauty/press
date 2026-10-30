<template>
	<router-link custom v-slot="{ href, navigate }" :to="item.route">
		<a
			:href="href"
			@click="navigate"
			class="as-nav-item flex items-center rounded-[6px] px-3 py-2 transition"
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
				<span class="text-[13px]">{{ item.name }}</span>
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
/* Solid colors, not translucent white: translucent text blends into the slate and reads matte. */
.as-nav-item {
	color: #CBD5E1;
}
.as-nav-icon {
	color: #CBD5E1;
}
.as-nav-inactive:hover {
	color: white;
	background: rgba(255,255,255,0.06);
}
.as-nav-inactive:hover .as-nav-icon {
	color: white;
}
.as-nav-active {
	color: white;
	background: #0B6BD3;
}
.as-nav-active .as-nav-icon {
	color: white;
}
</style>
