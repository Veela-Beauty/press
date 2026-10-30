// Compile ListPage.vue (other list pages use it) and render ListPageAlerts for a team with no payment mode.
import { createApp, h } from 'vue';
import { resourcesPlugin } from 'frappe-ui';
import 'frappe-ui/style.css';
import './tw.css';
import ListPageAlerts from '../dash/src/components/ListPageAlerts.vue';
import registerGlobalComponents from '../dash/src/components/global/register';

const app = createApp({ render: () => h('div', { id: 'alerts' }, [h(ListPageAlerts)]) });
registerGlobalComponents(app);
app.use(resourcesPlugin);
app.config.globalProperties.$team = { doc: { payment_mode: '', parent_team: '', currency: 'USD' } };
app.mount('#app');
