// Mounts the real ported benches list page (fork copy under src/fork) with faked data.
import { createApp, h } from 'vue';
import { createRouter, createWebHashHistory, RouterView } from 'vue-router';
import { Toaster } from 'vue-sonner';
import { resourcesPlugin } from 'frappe-ui';
import 'frappe-ui/style.css';
import './tw.css';
import Page from './fork/pages/benches/list/Page.vue';
import { dialogs } from './fork/utils/components';

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
app.use(router);
// main.js installs this; LinkControl's options-API resources need it.
app.use(resourcesPlugin);
app.mount('#app');
