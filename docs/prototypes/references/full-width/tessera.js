// Mount TesseraAdmin (before or after the full-width change) to measure how much of the width it uses.
import { createApp, h } from 'vue';
import { createRouter, createWebHashHistory, RouterView } from 'vue-router';
import { resourcesPlugin } from 'frappe-ui';
import 'frappe-ui/style.css';
import './tw.css';
import After from '../dash/src/pages/TesseraAdmin.vue';
import Before from '../dash-before/TesseraAdmin.vue';
import registerGlobalComponents from '../dash/src/components/global/register';

const which = new URLSearchParams(location.search).get('v') === 'before' ? Before : After;
const router = createRouter({ history: createWebHashHistory(), routes: [{ path: '/:p(.*)*', component: which }] });
const app = createApp({ render: () => h('div', { id: 'content', style: 'width:100%' }, [h(RouterView)]) });
registerGlobalComponents(app);
app.config.globalProperties.$team = { doc: { payment_mode: 'Card', billing_details: { name: 'x' } } };
app.use(router);
app.use(resourcesPlugin);
app.mount('#app');
