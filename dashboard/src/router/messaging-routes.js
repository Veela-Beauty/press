// Communications, SMS (owner 2026-11-27): the five owner-only pages for Basher SMS codes.
export default [
	{ path: '/sms/sites', name: 'SMS Sites', component: () => import('../pages/messaging/SmsSites.vue') },
	{ path: '/sms/log', name: 'SMS Log', component: () => import('../pages/messaging/SmsLog.vue') },
	{ path: '/sms/cost', name: 'SMS Cost by Client', component: () => import('../pages/messaging/SmsCostByClient.vue') },
	{ path: '/sms/routes', name: 'SMS Routes', component: () => import('../pages/messaging/SmsRoutes.vue') },
	{ path: '/sms/providers', name: 'SMS Providers', component: () => import('../pages/messaging/SmsProviders.vue') },
];
