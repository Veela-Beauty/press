<!-- The dashboard menu as the desk's icon rail (owner 2026-11-21, prototype ACM-SP-05): 104 px, icon over label, the
Accurate blue; groups open a flyout of their pages. Same items and conditions as before (NavigationItems.vue);
Notifications is the top bar's bell, and the account menu moved to the top bar's avatar. -->
<template>
	<nav class="as-rail" aria-label="Main menu">
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
</script>

<style scoped>
.as-rail {
	width: 104px;
	height: 100%;
	overflow-y: auto;
	padding: 10px 8px 16px;
	scrollbar-width: thin;
	scrollbar-color: rgba(255, 255, 255, 0.3) transparent;
}
</style>
