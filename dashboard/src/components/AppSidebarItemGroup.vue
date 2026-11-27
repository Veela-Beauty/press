<!-- A menu group (desk look, ACM-SP-05). In the full menu (kept by "..." or opened as a drawer) it opens inline, its
pages under it, and starts open when one of them is the page you are on. On the collapsed rail a click opens the full
menu as a drawer over the page with this group open (owner 2026-11-21: "open the full drawer, not this drop list");
the rail shows no arrows. -->
<template>
	<div
		ref="tile"
		role="button"
		:tabindex="item.disabled ? -1 : 0"
		:aria-expanded="full ? inline : false"
		:aria-disabled="item.disabled || undefined"
		:title="item.name"
		class="as-rail-item as-rail-group"
		:class="{ active: isActive, 'pointer-events-none opacity-50': item.disabled }"
		@click="toggle"
		@keydown.enter.space.prevent="toggle"
	>
		<component :is="item.icon" class="as-item-icon" />
		<span class="as-item-label">{{ item.name }}</span>
		<component v-if="item.badge" :is="item.badge" class="as-item-badge" />
		<lucide-chevron-right class="as-rail-more" :class="{ down: inline }" />
	</div>
	<div v-if="full && inline" class="as-rail-children">
		<template v-for="sub in item.children" :key="sub.name">
			<div v-if="sub.children" class="as-rail-nested">
				<AppSidebarItemGroup :item="sub" />
			</div>
			<AppSidebarItem v-else :item="sub" />
		</template>
	</div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import AppSidebarItem from './AppSidebarItem.vue';
import { menuDrawer, menuExpanded } from './topbar';

const props = defineProps({
	item: {
		type: Object,
		required: true,
	},
});

const tile = ref(null);
const full = computed(() => menuExpanded.value || menuDrawer.value);
const isActive = computed(
	() => props.item.isActive || props.item.children.some((c) => c.isActive || (c.children || []).some((g) => g.isActive)),
);
// open inline, and open by itself when you land on one of its pages
const inline = ref(isActive.value);
watch(isActive, (now) => now && (inline.value = true));

async function toggle() {
	if (props.item.disabled) return;
	if (!full.value) {
		// the collapsed rail: the full menu over the page, this group open and in view
		inline.value = true;
		menuDrawer.value = true;
		await nextTick();
		tile.value?.scrollIntoView({ block: 'nearest' });
		return;
	}
	inline.value = !inline.value;
}
</script>

<style>
.as-rail:not(.expanded) .as-rail-more {
	display: none; /* the rail shows no arrows (owner 2026-11-21) */
}
.as-rail.expanded .as-rail-item .as-rail-more {
	margin-left: auto;
	width: 14px;
	height: 14px;
	opacity: 0.65;
}
.as-rail-item .as-rail-more.down {
	transform: rotate(90deg);
}
/* full menu with its pages showing: only the page you are on is white, its group a light tint */
.as-rail.expanded .as-rail-group.active {
	background: rgba(255, 255, 255, 0.14);
	color: #fff;
}
.as-rail.expanded .as-rail-children .as-rail-item {
	padding-left: 44px; /* under its group: more specific than the full menu's row padding */
}
.as-rail.expanded .as-rail-nested .as-rail-children .as-rail-item {
	padding-left: 60px; /* a group inside a group: its pages one step further in */
}
.as-rail-children .as-rail-item .as-item-icon {
	width: 16px;
	height: 16px;
}
</style>
