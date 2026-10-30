// Mounts the benches tree as a server's Benches tab (embedded mode), twice: Active and not Active.
import { createApp, h } from 'vue';
import { createRouter, createWebHashHistory, RouterView } from 'vue-router';
import { resourcesPlugin } from 'frappe-ui';
import 'frappe-ui/style.css';
import './tw.css';
import Page from '../dash/src/pages/benches/list/Page.vue';
import registerGlobalComponents from '../dash/src/components/global/register';

window.$socket = { on() {}, off() {}, emit() {} };
const params = new URLSearchParams(location.search);
const active = params.get('active') !== '0';
const stub = { render: () => h('div', 'navigated') };
const names = ['New Release Group', 'Server New Release Group', 'Release Group Detail', 'Site Detail',
	'Release Group Detail Actions', 'Site Detail Actions', 'Release Group New Site'];
const router = createRouter({
	history: createWebHashHistory(),
	routes: [
		{ path: '/', component: { render: () => h('div', { class: 'p-5' }, [h(Page, { server: 'u4-default.sandbox.mvpstorm.com', canAddBench: active })]) } },
		...names.map((name, i) => ({ name, path: `/r${i}/:server?/:name?/:bench?`, component: stub })),
	],
});
const app = createApp({ render: () => h(RouterView) });
registerGlobalComponents(app);
app.config.globalProperties.$team = { doc: { payment_mode: 'Card', billing_details: { name: 'x' } } };
app.use(router);
app.use(resourcesPlugin);
app.mount('#app');
