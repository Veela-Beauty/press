<template>
	<div
		@click="toggle"
		class="as-nav-group flex cursor-pointer select-none items-center rounded-[6px] px-3 py-2 transition"
		:class="[
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
			<span class="!ml-auto">
				<lucide-chevron-down v-if="isOpened" class="h-4 w-4 as-nav-chevron" />
				<lucide-chevron-right v-else class="h-4 w-4 as-nav-chevron" />
			</span>
		</div>
	</div>
	<div class="ml-5 py-1" v-if="isOpened">
		<AppSidebarItem
			v-for="subItem in item.children"
			:key="subItem.name"
			:item="subItem"
		/>
	</div>
</template>

<script setup>
import { ref, watch } from 'vue';
import AppSidebarItem from './AppSidebarItem.vue';

let props = defineProps({
	item: {
		type: Object,
		required: true,
	},
});

const isOpened = ref(false);

const toggle = () => {
	isOpened.value = !isOpened.value;
};

watch(
	() => props.item.isActive,
	() => {
		isOpened.value = props.item.isActive;
	},
);
</script>

<style scoped>
/* Rebrand: Dark sidebar group items */
.as-nav-group {
	color: #CBD5E1;
}
.as-nav-group:hover {
	color: white;
	background: rgba(255,255,255,0.06);
}
.as-nav-icon {
	color: #CBD5E1;
}
.as-nav-group:hover .as-nav-icon {
	color: white;
}
.as-nav-chevron {
	color: #94A3B8;
}
</style>
