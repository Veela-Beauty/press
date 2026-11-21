// A Watch Tower finding list one page at a time (owner 2026-11-21: the list card ends level with the chart beside it,
// with pagination). Page 1 comes with the page's own read; the next pages from the hub's paged read (GET only).
import { computed, ref } from 'vue';
import { createResource } from 'frappe-ui';

export const PAGE_ROWS = 6; // the hub's page_data.PAGE_ROWS

// first(): { rows, total } from the page's read; params(): what the paged read needs besides `start`
export function usePages(url, first, params = () => ({})) {
	const page = ref(0);
	const more = createResource({
		url,
		method: 'GET',
		makeParams: () => ({ ...params(), start: page.value * PAGE_ROWS }),
	});
	const rows = computed(() => (page.value === 0 ? first().rows : more.data?.rows || []));
	const total = computed(() => (page.value === 0 || !more.data ? first().total : more.data.total));
	function go(n) {
		page.value = n;
		if (n) more.reload();
	}
	function reset() {
		page.value = 0;
		more.reset();
	}
	return { page, rows, total, more, go, reset };
}
