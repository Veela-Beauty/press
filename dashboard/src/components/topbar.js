// The desk-look shell (owner 2026-11-21, prototype ACM-SP-05): the top bar's breadcrumb box, filled by the page's own
// breadcrumbs through a Teleport, and how the menu shows.
import { ref, shallowRef, watch } from 'vue';

export const topbarCrumbsEl = shallowRef(null); // the top bar's crumbs box; null on a phone or before it mounts
export const IN_PAGE_HEADER = Symbol('in-page-header'); // provided by Header.vue: only a page's own trail moves up

// The menu (owner 2026-11-21): the 104 px rail, or the full 240 px menu with labels beside icons and groups inline.
// "..." keeps it full (this browser remembers); a group clicked on the rail opens the full menu as a drawer over the
// page until a page is chosen ("open the full drawer, not this drop list").
const EXPANDED_KEY = 'as-menu-expanded';
export const menuExpanded = ref(localStorage.getItem(EXPANDED_KEY) === '1');
export const menuDrawer = ref(false);
watch(menuExpanded, (value) => {
	localStorage.setItem(EXPANDED_KEY, value ? '1' : '0');
	menuDrawer.value = false;
});
