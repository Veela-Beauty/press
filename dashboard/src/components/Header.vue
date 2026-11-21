<!-- A page's header row. Desk look (owner 2026-11-21, prototype ACM-SP-05): on a desktop the page's breadcrumb trail
shows in the top bar, like the desk. Press's own Breadcrumbs moves its trail there itself (it keeps its #actions slot
here); a frappe-ui Breadcrumbs placed directly in this slot is lifted here. The page's actions stay in this row, and
a row left with no element to show hides. On a phone nothing moves. -->
<script>
import { Breadcrumbs as FrappeBreadcrumbs } from 'frappe-ui';
import { Fragment, Teleport, defineComponent, h, onBeforeUnmount, onMounted, provide, ref } from 'vue';
import { IN_PAGE_HEADER, topbarCrumbsEl } from './topbar';

const flat = (nodes) =>
	nodes.flatMap((n) => (n.type === Fragment && Array.isArray(n.children) ? flat(n.children) : [n]));

export default defineComponent({
	name: 'Header',
	props: {
		sticky: {
			type: Boolean,
			default: false,
		},
	},
	setup(props, { slots }) {
		provide(IN_PAGE_HEADER, true);
		const header = ref(null);
		const row = ref(null);
		// Teleport markers and Fragment anchors are not elements: count elements only, also when a child component
		// (Breadcrumbs' #actions) changes on its own
		let observer;
		const sync = () => {
			if (header.value && row.value) header.value.style.display = row.value.children.length ? '' : 'none';
		};
		onMounted(() => {
			observer = new MutationObserver(sync);
			observer.observe(row.value, { childList: true });
			sync();
		});
		onBeforeUnmount(() => observer?.disconnect());
		return () => {
			const nodes = flat(slots.default?.() || []);
			const crumbs = topbarCrumbsEl.value ? nodes.filter((n) => n.type === FrappeBreadcrumbs) : [];
			const rest = nodes.filter((n) => !crumbs.includes(n));
			return h(
				'header',
				{ ref: header, class: ['border-b bg-white px-5 py-2.5 sm:px-5', { 'sticky top-0 z-10': props.sticky }] },
				[
					crumbs.length ? h(Teleport, { to: topbarCrumbsEl.value }, crumbs) : null,
					h('div', { ref: row, class: 'flex items-center justify-between sm:h-7' }, rest),
				],
			);
		};
	},
});
</script>
