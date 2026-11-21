<template>
	<div class="relative flex h-full flex-col">
		<!-- desk look (owner 2026-11-21, prototype ACM-SP-05): top bar, icon rail, the page on a rounded sheet -->
		<AppTopbar v-if="!$isMobile && deskShell" />
		<div class="min-h-0 flex-1" :class="{ 'as-shell-body': !$isMobile && deskShell }">
			<div class="flex h-full">
				<div
					v-if="!isSignupFlow && !$isMobile && !isHideSidebar"
					class="relative block min-h-0 flex-shrink-0"
				>
					<AppSidebar
						v-if="$session.user && $team?.doc && route.name !== 'Login'"
					/>
				</div>
				<div
					class="w-full overflow-auto z-0"
					:class="{ 'as-sheet': !$isMobile && deskShell }"
					id="scrollContainer"
				>
					<MobileNav
						v-if="!isSignupFlow && $isMobile && !isHideSidebar && $session.user"
					/>
					<div
						v-if="
							!isSignupFlow &&
							!isSiteLogin &&
							!$session.user &&
							!$route.meta.isLoginPage
						"
						class="border bg-red-200 px-5 py-3 text-base text-red-900"
					>
						You are not logged in.
						<router-link to="/login" class="underline">Login</router-link> to
						access dashboard.
					</div>
					<router-view />
				</div>
			</div>
		</div>
		<Toaster position="top-right" />
		<component v-for="dialog in dialogs" :is="dialog" :key="dialog.id" />
	</div>
</template>

<script setup>
import { defineAsyncComponent, computed, watch, ref, provide } from 'vue';
import { Toaster } from 'vue-sonner';
import { dialogs } from './utils/components';
import { useRoute } from 'vue-router';
import { getTeam } from './data/team';
import { session } from './data/session.js';

const AppSidebar = defineAsyncComponent(
	() => import('./components/AppSidebar.vue'),
);
const AppTopbar = defineAsyncComponent(
	() => import('./components/AppTopbar.vue'),
);
const MobileNav = defineAsyncComponent(
	() => import('./components/MobileNav.vue'),
);

const route = useRoute();
const team = getTeam();

const isHideSidebar = computed(() => {
	const alwaysHideSidebarRoutes = [
		'Site Login',
		'SignupLoginToSite',
		'SignupSetup',
	];
	const alwaysHideSidebarPaths = ['/dashboard/site-login'];

	if (!session.user) return false;
	if (
		alwaysHideSidebarRoutes.includes(route.name) ||
		alwaysHideSidebarPaths.includes(window.location.pathname)
	)
		return true;

	return (
		route.meta.hideSidebar && session.user && team?.doc?.hide_sidebar === true
	);
});

const isSignupFlow = ref(
	window.location.pathname.startsWith('/dashboard/create-site') ||
		window.location.pathname.startsWith('/dashboard/setup-account') ||
		window.location.pathname.startsWith('/dashboard/site-login') ||
		window.location.pathname.startsWith('/dashboard/signup'),
);
const isSiteLogin = ref(window.location.pathname.endsWith('/site-login'));

watch(
	() => route.name,
	() => {
		isSignupFlow.value =
			window.location.pathname.startsWith('/dashboard/create-site') ||
			window.location.pathname.startsWith('/dashboard/setup-account') ||
			window.location.pathname.startsWith('/dashboard/site-login') ||
			window.location.pathname.startsWith('/dashboard/signup');
	},
);

// the desk-look shell shows where the sidebar did (not on sign-up, site login or hidden-sidebar pages)
const deskShell = computed(
	() =>
		!isSignupFlow.value &&
		!isHideSidebar.value &&
		!!session.user &&
		!!team?.doc &&
		route.name !== 'Login',
);

provide('team', team);
provide('session', session);
</script>

<style src="./assets/style.css"></style>
<style>
/* desk look (ACM-SP-05): the rail's blue runs behind the sheet, so the sheet's rounded corner shows like the desk's */
.as-shell-body {
	background: linear-gradient(180deg, #1a5f7a 0%, #21709a 100%);
}
/* white, not the prototype's grey: on grey the Sites list's filter fields disappeared (checked live 2026-11-21) */
.as-sheet {
	background: #fff;
	border-top-left-radius: 24px;
}
</style>
