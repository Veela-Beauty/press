// The desk-look shell (owner 2026-11-21, prototype ACM-SP-05): the top bar's breadcrumb box, filled by the page's own
// breadcrumbs through a Teleport, and the one menu group whose flyout is open.
import { ref, shallowRef } from 'vue';

export const topbarCrumbsEl = shallowRef(null); // the top bar's crumbs box; null on a phone or before it mounts
export const IN_PAGE_HEADER = Symbol('in-page-header'); // provided by Header.vue: only a page's own trail moves up
export const openGroup = ref(null); // the name of the rail group whose flyout is open, one at a time
