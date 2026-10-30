// Mounts the deployed (before) and new (after) dashboard sidebars side by side with stub team/session data.
import { createApp, h } from 'vue';
import { createRouter, createMemoryHistory } from 'vue-router';
import { Dropdown, FeatherIcon, Tooltip } from 'frappe-ui';
import 'frappe-ui/style.css';
import './tw.css';
import Before from './sidebar-before/AppSidebar.vue';
import After from './sidebar-after/AppSidebar.vue';

const icon = (name) => () => h(FeatherIcon, { name });
const navigation = [
	{ name: 'Notifications', icon: icon('inbox'), route: '/n' },
	{ name: 'Sites', icon: icon('layout'), route: '/sites' },
	{ name: 'Benches', icon: icon('package'), route: '/groups', isActive: true },
	{ name: 'Servers', icon: icon('server'), route: '/servers' },
	{ name: 'Infrastructure', icon: icon('cpu'), route: '/infra' },
	{ name: 'Telephony', icon: icon('phone'), route: '/tel' },
	{ name: 'Backups', icon: icon('archive'), children: [{ name: 'Site Backups', icon: icon('database'), route: '/b1' }] },
	{ name: 'Daman Backup', icon: icon('hard-drive'), children: [{ name: 'Overview', icon: icon('grid'), route: '/d1' }] },
	{ name: 'Dev Tools', icon: icon('code'), children: [{ name: 'MCP', icon: icon('terminal'), route: '/mcp' }] },
	{ name: 'Marketplace', icon: icon('grid'), route: '/apps' },
	{ name: 'Billing', icon: icon('credit-card'), route: '/billing' },
	{ name: 'Settings', icon: icon('settings'), route: '/settings' },
];
const FCLogo = { render: () => h('div', { style: 'background:#fff;color:#1e293b;font-weight:800;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:13px' }, 'AS') };

for (const [id, comp] of [['#before', Before], ['#after', After]]) {
	const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { render: () => null } }] });
	const app = createApp({ render: () => h(comp) });
	app.use(router);
	app.provide('navigation', navigation);
	app.component('Dropdown', Dropdown);
	app.component('FeatherIcon', FeatherIcon);
	app.component('Tooltip', Tooltip);
	app.component('FCLogo', FCLogo);
	app.component('LucideChevronDown', icon('chevron-down'));
	app.component('LucideChevronRight', icon('chevron-right'));
	app.config.globalProperties.$team = { doc: { user: 'eng.elgogary@gmail.com' }, get: { loading: false } };
	app.config.globalProperties.$session = { logout: { submit() {} } };
	app.mount(id);
}
