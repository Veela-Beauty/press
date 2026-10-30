// Mounts the real ported benches list page (fork copy under src/fork) with faked data.
import { createApp, h } from 'vue';
import { createRouter, createWebHashHistory, RouterView } from 'vue-router';
import { Toaster } from 'vue-sonner';
import { resourcesPlugin } from 'frappe-ui';
import 'frappe-ui/style.css';
import './tw.css';
import Page from './fork/pages/benches/list/Page.vue';
import { dialogs } from './fork/utils/components';
import registerGlobalComponents from './fork/components/global/register';
window.__dialogs = dialogs;

window.$socket = { on() {}, off() {}, emit() {} };
const stub = { render: () => h('div', 'navigated') };
const names = ['New Release Group', 'Release Group Detail', 'Site Detail', 'Release Group Detail Actions',
	'Site Detail Actions', 'Release Group New Site'];
const router = createRouter({
	history: createWebHashHistory(),
	routes: [
		{ path: '/', component: Page },
		...names.map((name, i) => ({ name, path: `/r${i}/:name?/:bench?`, component: stub })),
		{ path: '/apps', component: stub },
	],
});
// Same as App.vue: renderDialog() pushes into `dialogs`, which the root renders.
const app = createApp({ render: () => [h(Toaster), h(RouterView), ...dialogs.value.map((d) => h(d, { key: d.id }))] });
// main.js sets $team globally; this doc triggers none of the billing alerts.
app.config.globalProperties.$team = {
	doc: { payment_mode: 'Card', currency: 'USD', billing_details: { name: 'BD-1' }, payment_method: { stripe_mandate_id: 'm' } },
};
registerGlobalComponents(app);  // as main.js does; ConfirmDialog uses global Dialog/Button
app.use(router);
// main.js installs this; LinkControl's options-API resources need it.
app.use(resourcesPlugin);
app.mount('#app');
