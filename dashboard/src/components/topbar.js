// The desk-look shell (owner 2026-11-21, prototype ACM-SP-05): the top bar's breadcrumb box, filled by the page's own
// breadcrumbs through a Teleport, the one menu group whose flyout is open, and whether the menu is expanded.
import { ref, shallowRef, watch } from 'vue';

export const topbarCrumbsEl = shallowRef(null); // the top bar's crumbs box; null on a phone or before it mounts
export const IN_PAGE_HEADER = Symbol('in-page-header'); // provided by Header.vue: only a page's own trail moves up
export const openGroup = ref(null); // the name of the rail group whose flyout is open, one at a time

// the desk's "..." toggle (owner 2026-11-21): 240 px menu with labels beside icons and groups inline, or the 104 px
// rail with flyouts; this browser remembers the choice
const EXPANDED_KEY = 'as-menu-expanded';
export const menuExpanded = ref(localStorage.getItem(EXPANDED_KEY) === '1');
watch(menuExpanded, (value) => {
	localStorage.setItem(EXPANDED_KEY, value ? '1' : '0');
	openGroup.value = null; // a flyout belongs to the rail only
});
