<!-- A menu group on the rail (desk look, ACM-SP-05): its tile opens a flyout of its pages to the right of the rail;
one flyout at a time; it closes on a click outside, Escape or a page change. The tile is white while one of its
pages is open. Still 2 clicks to a page, as when the group opened inline. In the expanded menu the group opens inline
instead, its pages under it, and starts open when one of them is the page you are on. -->
<template>
	<div
		ref="tile"
		role="button"
		:tabindex="item.disabled ? -1 : 0"
		:aria-haspopup="menuExpanded ? undefined : 'true'"
		:aria-expanded="menuExpanded ? inline : open"
		:aria-disabled="item.disabled || undefined"
		:title="item.name"
		class="as-rail-item as-rail-group"
		:class="{ active: isActive, 'as-rail-open': open && !isActive, 'pointer-events-none opacity-50': item.disabled }"
		@click="toggle"
		@keydown.enter.space.prevent="toggle"
	>
		<component :is="item.icon" class="as-item-icon" />
		<span class="as-item-label">{{ item.name }}</span>
		<component v-if="item.badge" :is="item.badge" class="as-item-badge" />
		<lucide-chevron-right class="as-rail-more" :class="{ down: menuExpanded && inline }" />
	</div>
	<div v-if="menuExpanded && inline" class="as-rail-children">
		<AppSidebarItem v-for="sub in item.children" :key="sub.name" :item="sub" />
	</div>
	<Teleport to="body">
		<div v-if="open" ref="panel" class="as-flyout" :style="{ top: `${top}px` }" :aria-label="item.name">
			<div class="as-flyout-title">{{ item.name }}</div>
			<AppSidebarItem v-for="sub in item.children" :key="sub.name" :item="sub" flyout @go="close" />
		</div>
	</Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import AppSidebarItem from './AppSidebarItem.vue';
import { menuExpanded, openGroup } from './topbar';

const props = defineProps({
	item: {
		type: Object,
		required: true,
	},
});

const tile = ref(null);
const panel = ref(null);
const top = ref(0);
const open = computed(() => openGroup.value === props.item.name);
const isActive = computed(() => props.item.isActive || props.item.children.some((c) => c.isActive));
// expanded menu: open inline, and open by itself when you land on one of its pages
const inline = ref(isActive.value);
watch(isActive, (now) => now && (inline.value = true));

function close() {
	if (open.value) openGroup.value = null;
}
async function toggle(event) {
	if (props.item.disabled) return;
	if (menuExpanded.value) return (inline.value = !inline.value);
	if (open.value) return close();
	openGroup.value = props.item.name;
	top.value = tile.value.getBoundingClientRect().top;
	await nextTick();
	// keep the flyout inside the window when the group sits low on the rail
	const room = window.innerHeight - (panel.value?.offsetHeight || 0) - 12;
	top.value = Math.max(90, Math.min(top.value, room));
	// opened from the keyboard: go into the flyout, so its pages are one Tab away and not at the end of the page
	if (event?.type === 'keydown') panel.value?.querySelector('a')?.focus();
}
function outside(event) {
	if (!open.value) return;
	if (tile.value?.contains(event.target) || panel.value?.contains(event.target)) return;
	close();
}
function escape(event) {
	if (event.key !== 'Escape') return;
	close();
	tile.value?.focus();
}
// a flyout placed for one scroll position and window size: close it when either changes
watch(open, (now) => {
	const method = now ? 'addEventListener' : 'removeEventListener';
	document[method]('mousedown', outside);
	document[method]('keydown', escape);
	window[method]('resize', close);
	tile.value?.closest('.as-rail')?.[method]('scroll', close);
});
const route = useRoute();
watch(() => route.fullPath, close);
onBeforeUnmount(() => {
	// the rail can go (a hidden-sidebar page) with a flyout open: never come back with it open and no listeners
	close();
	document.removeEventListener('mousedown', outside);
	document.removeEventListener('keydown', escape);
	window.removeEventListener('resize', close);
	tile.value?.closest('.as-rail')?.removeEventListener('scroll', close);
});
</script>

<style>
.as-rail-item .as-rail-more {
	position: absolute;
	top: 10px;
	right: 5px;
	width: 11px;
	height: 11px;
	opacity: 0.65;
}
/* expanded with its pages showing: only the page you are on is white, its group a light tint */
.as-rail.expanded .as-rail-group.active {
	background: rgba(255, 255, 255, 0.14);
	color: #fff;
}
.as-rail-item .as-rail-more.down {
	transform: rotate(90deg);
}
.as-rail.expanded .as-rail-item .as-rail-more {
	position: static;
	margin-left: auto;
	width: 14px;
	height: 14px;
}
.as-rail.expanded .as-rail-children .as-rail-item {
	padding-left: 44px; /* under its group: more specific than the expanded row's padding */
}
.as-rail-children .as-rail-item .as-item-icon {
	width: 16px;
	height: 16px;
}
.as-rail-open {
	background: rgba(255, 255, 255, 0.2);
}
.as-flyout {
	position: fixed;
	left: 112px;
	z-index: 40;
	width: 240px;
	max-height: calc(100vh - 100px);
	overflow-y: auto;
	padding: 6px;
	border-radius: 10px;
	background: #fff;
	box-shadow: 0 12px 32px rgba(16, 24, 40, 0.22);
}
.as-flyout-title {
	margin: 4px 8px 6px;
	font-size: 12px;
	font-weight: 600;
	color: #6b737b;
}
</style>
