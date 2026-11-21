<!-- The dashboard's top bar in the desk look (owner 2026-11-21, prototype ACM-SP-05): the Accurate blue gradient of the
press-ctrl desk theme, the white logo, the page's breadcrumbs (Header.vue and Breadcrumbs.vue teleport them into the
box below), notifications and the account menu that used to sit on top of the sidebar. -->
<template>
	<header class="as-topbar">
		<router-link to="/" class="as-topbar-logo" title="Accurate Systems" aria-label="Accurate Systems, home"><FCLogo class="h-9 w-9" /></router-link>
		<span v-show="hasCrumbs" class="as-topbar-sep">|</span>
		<div ref="crumbs" class="as-topbar-crumbs" />
		<div class="ml-auto flex items-center gap-3">
			<router-link v-if="showBell" to="/notifications" class="as-topbar-icon" title="Notifications" aria-label="Notifications">
				<Bell class="h-5 w-5" />
				<span v-if="unreadNotificationsCount.data > 0" class="as-topbar-count">
					{{ unreadNotificationsCount.data > 99 ? '99+' : unreadNotificationsCount.data }}
				</span>
			</router-link>
			<Dropdown :options="menu" placement="right">
				<template v-slot="{ open }">
					<button class="as-topbar-avatar" :class="{ open }" :title="who" :aria-label="`Account menu, ${who}`">{{ initials }}</button>
				</template>
			</Dropdown>
		</div>
		<SwitchTeamDialog v-if="showTeamSwitcher" v-model="showTeamSwitcher" />
	</header>
</template>

<script setup>
import { computed, defineAsyncComponent, getCurrentInstance, onBeforeUnmount, onMounted, ref } from 'vue';
import Bell from '~icons/lucide/bell';
import { unreadNotificationsCount } from '../data/notifications';
import { session } from '../data/session';
import { topbarCrumbsEl } from './topbar';

const SwitchTeamDialog = defineAsyncComponent(() => import('./SwitchTeamDialog.vue'));
const { proxy } = getCurrentInstance();
const crumbs = ref(null);
const showTeamSwitcher = ref(false);

// the separator only when a page put its trail here (a site's page and Settings keep theirs in the page)
const hasCrumbs = ref(false);
let observer;
onMounted(() => {
	topbarCrumbsEl.value = crumbs.value;
	observer = new MutationObserver(() => (hasCrumbs.value = crumbs.value.children.length > 0));
	observer.observe(crumbs.value, { childList: true });
});
onBeforeUnmount(() => {
	observer?.disconnect();
	topbarCrumbsEl.value = null;
});

const team = computed(() => proxy.$team?.doc);
// the same condition as the Notifications menu item it replaces
const showBell = computed(() => team.value?.onboarding?.complete && !team.value?.is_saas_user);
const who = computed(() => session.userFullName || team.value?.user || '');
// "Mohamed Elgogary" -> ME; with no full name, the email's first part
const initials = computed(() => {
	const name = session.userFullName || (team.value?.user || '').split('@')[0];
	const parts = name.split(/[._\-\s]+/).filter(Boolean);
	return ((parts[0]?.[0] || '') + (parts[1]?.[0] || parts[0]?.[1] || '')).toUpperCase() || '?';
});
const menu = [
	{
		label: 'Change Team',
		icon: 'command',
		condition: () => team.value?.valid_teams?.length > 1 || team.value?.is_desk_user,
		onClick: () => (showTeamSwitcher.value = true),
	},
	/* Rebrand: Accurate Systems support/docs and feedback URLs (moved here from the sidebar) */
	{ label: 'Support & Docs', icon: 'help-circle', onClick: () => window.open('https://accuratesystems.com.sa/docs', '_blank') },
	{ label: 'Share Feedback', icon: 'file-text', onClick: () => window.open('https://accuratesystems.com.sa/feedback', '_blank') },
	{ label: 'Logout', icon: 'log-out', onClick: () => proxy.$session.logout.submit() },
];
</script>

<style scoped>
.as-topbar {
	height: 80px;
	flex: 0 0 auto;
	display: flex;
	align-items: center;
	gap: 14px;
	padding: 0 22px 0 17px;
	background: #1a5f7a; /* one solid brand blue with the rail, no seam (owner 2026-11-21: "no gradient") */
	color: #fff;
}
.as-topbar-logo :deep(svg),
.as-topbar-logo :deep(img) {
	filter: brightness(0) invert(1);
}
.as-topbar-sep {
	opacity: 0.7;
	font-size: 18px;
}
.as-topbar-crumbs {
	min-width: 0;
	flex: 0 1 auto;
}
.as-topbar-icon {
	position: relative;
	display: grid;
	place-items: center;
	width: 36px;
	height: 36px;
	border-radius: 8px;
	color: #fff;
}
.as-topbar-icon:hover,
.as-topbar-avatar:hover,
.as-topbar-avatar.open {
	background: rgba(255, 255, 255, 0.14);
}
.as-topbar-count {
	position: absolute;
	top: 0;
	right: -4px;
	min-width: 18px;
	height: 18px;
	padding: 0 4px;
	border-radius: 9px;
	background: #fff;
	color: #1a5f7a;
	font-size: 10.5px;
	font-weight: 700;
	display: grid;
	place-items: center;
}
.as-topbar-avatar {
	width: 38px;
	height: 38px;
	border-radius: 50% !important; /* an avatar is round; style.css forces 6 px on buttons */
	border: 2px solid rgba(255, 255, 255, 0.6);
	background: #fff;
	color: #1a5f7a;
	font-weight: 700;
	font-size: 14px;
}
.as-topbar-avatar:hover,
.as-topbar-avatar.open {
	background: #e8f1f7;
}
</style>

<style>
/* the page's trail lives in the top bar now: white on the blue (the components are the page's, so not scoped) */
.as-topbar-crumbs a,
.as-topbar-crumbs button,
.as-topbar-crumbs span {
	color: rgba(255, 255, 255, 0.82) !important;
}
.as-topbar-crumbs a:last-of-type,
.as-topbar-crumbs a:last-of-type span,
.as-topbar-crumbs [aria-current='page'] {
	color: #fff !important;
	font-weight: 600;
}
.as-topbar-crumbs a:hover {
	color: #fff !important;
}
</style>
