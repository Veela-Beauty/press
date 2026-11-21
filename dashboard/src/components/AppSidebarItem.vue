<!-- One menu entry. On the rail (desk look, ACM-SP-05): icon over label, white tile when it is the page you are on.
In a group's flyout (`flyout`): a plain row. -->
<template>
	<router-link custom v-slot="{ href, navigate }" :to="item.route">
		<a
			:href="item.disabled ? undefined : href"
			:title="item.name"
			:tabindex="item.disabled ? -1 : undefined"
			:aria-disabled="item.disabled || undefined"
			@click="(e) => (item.disabled ? e.preventDefault() : (navigate(e), emit('go')))"
			:class="[
				flyout ? 'as-fly-item' : 'as-rail-item',
				{ active: item.isActive, 'pointer-events-none opacity-50': item.disabled },
				$attrs.class,
			]"
		>
			<component :is="item.icon" class="as-item-icon" />
			<span class="as-item-label">{{ item.name }}</span>
			<component v-if="item.badge" :is="item.badge" class="as-item-badge" />
		</a>
	</router-link>
</template>

<script setup>
defineProps({
	item: {
		type: Object,
		required: true,
	},
	flyout: {
		type: Boolean,
		default: false,
	},
});
const emit = defineEmits(['go']);
</script>

<style>
/* shared by the rail tiles of AppSidebarItemGroup.vue (not scoped) */
.as-rail-item {
	position: relative;
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 6px;
	margin-bottom: 4px;
	padding: 10px 4px;
	border-radius: 10px;
	color: rgba(255, 255, 255, 0.92);
	text-align: center;
	cursor: pointer;
}
.as-rail-item .as-item-icon {
	width: 20px;
	height: 20px;
}
.as-rail-item .as-item-label {
	font-size: 11.5px;
	font-weight: 550;
	line-height: 1.2;
}
.as-rail-item .as-item-badge {
	position: absolute;
	top: 4px;
	right: 6px;
}
.as-rail-item:hover {
	background: rgba(255, 255, 255, 0.12);
}
.as-rail-item.active {
	background: #fff;
	color: #1a5f7a;
}
.as-fly-item {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 8px 10px;
	border-radius: 6px;
	font-size: 13.5px;
	color: #1c2024;
}
.as-fly-item .as-item-icon {
	width: 16px;
	height: 16px;
	color: #525a64;
}
.as-fly-item:hover {
	background: #f6f7f8;
}
.as-fly-item.active {
	background: #e8f1f7;
	color: #1a5f7a;
	font-weight: 600;
}
.as-fly-item .as-item-badge {
	margin-left: auto;
}
</style>
