// Billing and team settings routes (moved out of router.js on 2026-11-27 so it stays under 700 lines).
export default [
	{
		name: 'Billing',
		path: '/billing',
		component: () => import('../pages/Billing.vue'),
		children: [
			{
				name: 'BillingOverview',
				path: '',
				component: () => import('../pages/BillingOverview.vue'),
			},
			{
				name: 'BillingForecast',
				path: 'forecast',
				component: () => import('../pages/BillingForecast.vue'),
			},
			{
				name: 'BillingInvoices',
				path: 'invoices',
				component: () => import('../pages/BillingInvoices.vue'),
			},
			{
				name: 'BillingBalances',
				path: 'balances',
				component: () => import('../pages/BillingBalances.vue'),
			},
			{
				name: 'BillingPaymentMethods',
				path: 'payment-methods',
				component: () => import('../pages/BillingPaymentMethods.vue'),
			},
			{
				name: 'BillingMarketplacePayouts',
				path: 'payouts',
				component: () => import('../pages/BillingMarketplacePayouts.vue'),
			},
			{
				name: 'BillingMpesaInvoices',
				path: 'mpesa-invoices',
				component: () => import('../pages/BillingMpesaInvoices.vue'),
			},
		],
	},
	{
		path: '/settings',
		name: 'Settings',
		redirect: { name: 'SettingsProfile' },
		component: () => import('../pages/Settings.vue'),
		children: [
			{
				name: 'SettingsProfile',
				path: 'profile',
				component: () =>
					import('../components/settings/profile/ProfileSettings.vue'),
			},
			{
				name: 'SettingsTeam',
				path: 'team',
				component: () => import('../components/settings/TeamSettings.vue'),
			},
			{
				name: 'SettingsDeveloper',
				path: 'developer',
				component: () =>
					import('../components/settings/DeveloperSettings.vue'),
			},
			{
				name: 'SettingsTeamSSH',
				path: 'team-ssh',
				component: () =>
					import('../components/settings/TeamSSHAccess.vue'),
			},
			{
				name: 'SettingsPermission',
				path: 'permissions',
				component: () =>
					import('../components/settings/SettingsPermissions.vue'),
				redirect: { name: 'SettingsPermissionRoles' },
				children: [
					{
						path: 'roles',
						name: 'SettingsPermissionRoles',
						component: () => import('../components/settings/RoleList.vue'),
					},
					{
						name: 'SettingsPermissionRolePermissions',
						path: 'roles/:id',
						component: () => import('../components/settings/Role.vue'),
						props: true,
					},
				],
			},
		],
	},
];
