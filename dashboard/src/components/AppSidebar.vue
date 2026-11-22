<!-- The dashboard menu in the desk look (owner 2026-11-21, prototype ACM-SP-05): the 104 px icon rail (icon over label)
in the Accurate blue, or the full 240 px menu (icon beside label, groups inline). "..." keeps it full, remembered per
browser; a group clicked on the rail opens the full menu beside the page, which moves over to make room (owner
2026-11-22: covering the page hid its text), closed by choosing a page, a click outside it or Escape. The scrollbar
shows only while the pointer is on the menu. Same items and conditions as before
(NavigationItems.vue); Notifications is the top bar's bell, and the account menu is the top bar's avatar. -->
<template>
	<div class="as-rail-slot" :class="{ wide: menuExpanded || menuDrawer }">
		<nav
			ref="nav"
			class="as-rail"
			:class="{ expanded: menuExpanded || menuDrawer, drawer: menuDrawer && !menuExpanded }"
			aria-label="Main menu"
			@click="closeOnPage"
		>
			<button
				type="button"
				class="as-rail-toggle"
				:aria-expanded="menuExpanded"
				:aria-label="menuExpanded ? 'Collapse the menu' : 'Keep the menu expanded'"
				:title="menuExpanded ? 'Collapse the menu' : 'Keep the menu expanded'"
				@click.stop="menuExpanded = !menuExpanded"
			>
				<span /><span /><span />
			</button>
			<NavigationItems>
				<template v-slot="{ navigation }">
					<template v-for="item in navigation.filter((i) => i.route !== '/notifications')" :key="item.name">
						<AppSidebarItemGroup v-if="item.children" :item="item" />
						<AppSidebarItem v-else :item="item" />
					</template>
				</template>
			</NavigationItems>
		</nav>
	</div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import AppSidebarItem from './AppSidebarItem.vue';
import AppSidebarItemGroup from './AppSidebarItemGroup.vue';
import NavigationItems from './NavigationItems.vue';
import { menuDrawer, menuExpanded } from './topbar';

const nav = ref(null);
const route = useRoute();

function close() {
	menuDrawer.value = false;
}
// a page chosen in the drawer closes it, also the page you are already on (no route change then)
function closeOnPage(event) {
	if (menuDrawer.value && event.target.closest('a')) close();
}
function escape(event) {
	if (event.key === 'Escape') close();
}
// the page is beside the menu now, not under it: a click there closes the menu and still does its own job
function outside(event) {
	if (nav.value && !nav.value.contains(event.target)) close();
}
watch(() => route.fullPath, close);
watch(menuDrawer, (open) => {
	const act = open ? 'addEventListener' : 'removeEventListener';
	document[act]('keydown', escape);
	document[act]('mousedown', outside);
});
onBeforeUnmount(() => {
	close();
	document.removeEventListener('keydown', escape);
	document.removeEventListener('mousedown', outside);
});
</script>

<style scoped>
/* the slot holds the menu's room: 104 px for the rail, 240 px for the full menu, kept or opened by a group */
.as-rail-slot {
	position: relative;
	width: 104px;
	height: 100%;
	transition: width 0.15s ease;
}
.as-rail-slot.wide {
	width: 240px;
}
.as-rail {
	position: absolute;
	top: 0;
	bottom: 0;
	left: 0;
	width: 100%;
	overflow-y: auto;
	padding: 10px 8px 16px;
	scrollbar-width: none; /* hidden until the pointer is on the menu (owner 2026-11-22) */
	scrollbar-color: rgba(255, 255, 255, 0.3) transparent;
}
.as-rail:hover {
	scrollbar-width: thin;
}
.as-rail::-webkit-scrollbar {
	width: 0;
}
.as-rail:hover::-webkit-scrollbar {
	width: 6px;
}
.as-rail:hover::-webkit-scrollbar-thumb {
	background: rgba(255, 255, 255, 0.3);
	border-radius: 3px;
}
.as-rail.drawer {
	background: #1a5f7a;
}
/* the desk's three dots: the rail's own control, so it sits apart from the menu entries */
.as-rail-toggle {
	display: flex;
	gap: 5px;
	justify-content: center;
	align-items: center;
	width: 100%;
	height: 34px;
	margin-bottom: 8px;
	border-radius: 8px !important;
}
.as-rail.expanded .as-rail-toggle {
	justify-content: flex-start;
	padding-left: 14px;
}
.as-rail-toggle span {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	border: 1.5px solid rgba(255, 255, 255, 0.85);
}
.as-rail-toggle:hover {
	background: rgba(255, 255, 255, 0.12);
}
</style>
