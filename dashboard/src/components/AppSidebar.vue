<template>
	<div
		class="as-sidebar relative flex min-h-screen w-[220px] flex-col"
	>
		<div class="p-2">
			<Dropdown
				:options="[
					{
						label: 'Change Team',
						icon: 'command',
						condition: () =>
							$team?.doc?.valid_teams?.length > 1 || $team?.doc?.is_desk_user,
						onClick: () => (showTeamSwitcher = true),
					},
					{
						label: 'Support & Docs',
						icon: 'help-circle',
						onClick: docs,
					},
					{
						label: 'Share Feedback',
						icon: 'file-text',
						onClick: feedback,
					},
					{
						label: 'Logout',
						icon: 'log-out',
						onClick: $session.logout.submit,
					},
				]"
			>
				<template v-slot="{ open }">
					<button
						class="flex w-[204px] items-center rounded-md px-2 py-2 text-left"
						:class="open ? 'as-sidebar-btn-open' : 'as-sidebar-btn-closed'"
					>
						<FCLogo class="mb-1 h-9 w-9 shrink-0 rounded-lg bg-white p-0.5" />
						<div class="ml-2 flex flex-1 flex-col overflow-hidden">
							<div class="text-sm font-semibold leading-tight as-sidebar-brand">
								Accurate Systems
							</div>
							<Tooltip :text="$team?.doc?.user || null">
								<div
									class="mt-0.5 hidden overflow-hidden text-ellipsis whitespace-nowrap pb-1 text-xs leading-none as-sidebar-user sm:inline"
								>
									{{ $team?.get.loading ? 'Loading...' : $team?.doc?.user }}
								</div>
							</Tooltip>
						</div>
						<FeatherIcon
							name="chevron-down"
							class="ml-auto h-5 w-5 as-sidebar-chevron"
						/>
					</button>
				</template>
			</Dropdown>
		</div>
		<nav class="px-2">
			<NavigationItems>
				<template v-slot="{ navigation }">
					<template v-for="(item, i) in navigation" :key="item.name">
						<AppSidebarItemGroup v-if="item.children" :item="item" />
						<AppSidebarItem class="mt-0.5" v-else :item="item" />
					</template>
				</template>
			</NavigationItems>
		</nav>
		<!-- TODO: update component name after dashboard-beta merges -->
		<SwitchTeamDialog2 v-model="showTeamSwitcher" />
	</div>
</template>

<script>
import { defineAsyncComponent } from 'vue';
import AppSidebarItem from './AppSidebarItem.vue';
import { Tooltip } from 'frappe-ui';
import NavigationItems from './NavigationItems.vue';
import AppSidebarItemGroup from './AppSidebarItemGroup.vue';

export default {
	name: 'AppSidebar',
	components: {
		AppSidebarItem,
		AppSidebarItemGroup,
		SwitchTeamDialog2: defineAsyncComponent(
			() => import('./SwitchTeamDialog.vue'),
		),
		Tooltip,
		NavigationItems,
	},
	data() {
		return {
			showTeamSwitcher: false,
		};
	},
	methods: {
		docs() {
			/* Rebrand: Accurate Systems support/docs URL */
			window.open('https://accuratesystems.com.sa/docs', '_blank');
		},
		feedback() {
			/* Rebrand: Accurate Systems feedback URL */
			window.open(
				'https://accuratesystems.com.sa/feedback',
				'_blank',
			);
		},
	},
};
</script>

<style scoped>
/* Rebrand: Accurate Systems dark sidebar matching prototype */
.as-sidebar {
	background: #1E293B;
	border-right: 1px solid rgba(255,255,255,0.06);
}
.as-sidebar-brand {
	color: rgba(255,255,255,0.95);
}
.as-sidebar-user {
	color: rgba(255,255,255,0.5);
}
.as-sidebar-chevron {
	color: rgba(255,255,255,0.5);
}
.as-sidebar-btn-open {
	background: rgba(255,255,255,0.1);
}
.as-sidebar-btn-closed:hover {
	background: rgba(255,255,255,0.08);
}
</style>
