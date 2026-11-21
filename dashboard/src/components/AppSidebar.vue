<!-- The dashboard menu as the desk's icon rail (owner 2026-11-21, prototype ACM-SP-05): 104 px, icon over label, the
Accurate blue; groups open a flyout of their pages. The "..." toggle on top expands it like the desk: 240 px, icon and
label side by side, groups open inline (remembered per browser). Same items and conditions as before
(NavigationItems.vue); Notifications is the top bar's bell, and the account menu moved to the top bar's avatar. -->
<template>
	<nav class="as-rail" :class="{ expanded: menuExpanded }" aria-label="Main menu">
		<button
			type="button"
			class="as-rail-toggle"
			:aria-expanded="menuExpanded"
			:aria-label="menuExpanded ? 'Collapse the menu' : 'Expand the menu'"
			:title="menuExpanded ? 'Collapse the menu' : 'Expand the menu'"
			@click="menuExpanded = !menuExpanded"
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
</template>

<script setup>
import AppSidebarItem from './AppSidebarItem.vue';
import AppSidebarItemGroup from './AppSidebarItemGroup.vue';
import NavigationItems from './NavigationItems.vue';
import { menuExpanded } from './topbar';
</script>

<style scoped>
.as-rail {
	width: 104px;
	transition: width 0.15s ease;
	height: 100%;
	overflow-y: auto;
	padding: 10px 8px 16px;
	scrollbar-width: thin;
	scrollbar-color: rgba(255, 255, 255, 0.3) transparent;
}
.as-rail.expanded {
	width: 240px;
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
