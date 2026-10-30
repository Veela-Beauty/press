// Mounts the real Infrastructure page with faked get_infra_tree data, set up like main.js + App.vue.
import { createApp, h } from 'vue';
import { createRouter, createWebHashHistory, RouterView } from 'vue-router';
import { Toaster } from 'vue-sonner';
import { resourcesPlugin } from 'frappe-ui';
import 'frappe-ui/style.css';
import './tw.css';
import InfraDashboard from '../dash/src/pages/infrastructure/InfraDashboard.vue';
import { dialogs } from '../dash/src/utils/components';
import registerGlobalComponents from '../dash/src/components/global/register';

const stub = { render: () => h('div', 'navigated') };
const router = createRouter({
	history: createWebHashHistory(),
	routes: [
		{ path: '/', name: 'Infrastructure', component: InfraDashboard },
		{ path: '/servers/:name', component: stub },
	],
});
const app = createApp({ render: () => [h(Toaster), h(RouterView), ...dialogs.value.map((d) => h(d, { key: d.id }))] });
registerGlobalComponents(app);
app.config.globalProperties.$team = { doc: { payment_mode: 'Card', billing_details: { name: 'x' } } };
app.use(router);
app.use(resourcesPlugin);
app.mount('#app');
