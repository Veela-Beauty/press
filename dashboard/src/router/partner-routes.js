// Partner portal routes (moved out of router.js on 2026-11-27 so it stays under 700 lines).
export default [
	{
		name: 'PartnerLeadDetails',
		path: '/partner-lead/:leadId',
		component: () => import('../pages/PartnerLeadDetails.vue'),
		children: [
			{
				name: 'LeadOverview',
				path: '',
				component: () =>
					import('../components/partners/PartnerLeadOverview.vue'),
			},
			{
				name: 'LeadDealDetails',
				path: 'deal-info',
				component: () => import('../components/partners/LeadDealDetails.vue'),
			},
			{
				name: 'LeadFollowUp',
				path: 'follow-up',
				component: () => import('../components/partners/LeadFollowup.vue'),
			},
			{
				name: 'LeadActivities',
				path: 'activities',
				component: () => import('../components/partners/LeadActivities.vue'),
			},
		],
	},
	{
		name: 'Partnership',
		path: '/partners',
		redirect: { name: 'PartnerOverview' },
		component: () => import('../pages/Partners.vue'),
		children: [
			{
				name: 'PartnerOverview',
				path: 'overview',
				component: () => import('../components/partners/PartnerOverview.vue'),
			},
			{
				name: 'PartnerWebsiteDetails',
				path: 'website-details',
				component: () =>
					import('../components/partners/PartnerWebsiteDetails.vue'),
			},
			{
				name: 'PartnerCustomers',
				path: 'customers',
				component: () => import('../components/partners/PartnerCustomers.vue'),
			},
			{
				name: 'PartnerLeads',
				path: 'partner-leads',
				component: () => import('../components/partners/PartnerLeads.vue'),
			},
			{
				name: 'PartnerCertificates',
				path: 'certificates',
				component: () =>
					import('../components/partners/PartnerCertificates.vue'),
			},
			{
				name: 'PartnerResources',
				path: 'resources',
				component: () => import('../components/partners/PartnerResources.vue'),
			},
			{
				name: 'PartnerContributions',
				path: 'contributions',
				component: () =>
					import('../components/partners/PartnerContributionList.vue'),
			},
			{
				name: 'LocalPaymentSetup',
				path: 'local-payment-setup',
				component: () =>
					import('../components/partners/PartnerLocalPaymentSetup.vue'),
			},
			{
				name: 'PartnerPayout',
				path: 'payment-payout',
				component: () => import('../components/partners/PartnerPayout.vue'),
			},
			{
				name: 'PartnerDashboard',
				path: 'partner-dashboard',
				component: () => import('../components/partners/PartnerDashboard.vue'),
			},
		],
	},
	{
		name: 'Partner Admin',
		path: '/partner-admin',
		redirect: { name: 'PartnerList' },
		component: () => import('../pages/PartnerAdmin.vue'),
		children: [
			{
				name: 'PartnerList',
				path: 'partner-list',
				component: () => import('../pages/PartnerList.vue'),
			},
			{
				name: 'CertificateList',
				path: 'certificate-list',
				component: () => import('../pages/PartnerAdminCertificates.vue'),
			},
			{
				name: 'PartnerAdminLeads',
				path: 'partner-admin-lead-list',
				component: () => import('../pages/PartnerAdminLeads.vue'),
			},
			{
				name: 'PartnerAdminResources',
				path: 'admin-resources',
				component: () => import('../components/partners/PartnerResources.vue'),
			},
		],
	},
];
