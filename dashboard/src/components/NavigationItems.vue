<template>
	<div>
		<slot :navigation="navigation" />
	</div>
</template>
<script>
import { h } from 'vue';
import DoorOpen from '~icons/lucide/door-open';
import PanelTopInactive from '~icons/lucide/panel-top-inactive';
import Package from '~icons/lucide/package';
import Boxes from '~icons/lucide/boxes';
import Server from '~icons/lucide/server';
import ServerCog from '~icons/lucide/server-cog';
import Phone from '~icons/lucide/phone';
import WalletCards from '~icons/lucide/wallet-cards';
import Key from '~icons/lucide/key';
import Settings from '~icons/lucide/settings';
import App from '~icons/lucide/layout-grid';
import DatabaseZap from '~icons/lucide/database-zap';
import Activity from '~icons/lucide/activity';
import Logs from '~icons/lucide/scroll-text';
import Globe from '~icons/lucide/globe';
import Shield from '~icons/lucide/shield';
import Notification from '~icons/lucide/inbox';
import Code from '~icons/lucide/code';
import Archive from '~icons/lucide/archive';
import Camera from '~icons/lucide/camera';
import FileSearch from '~icons/lucide/file-search';
import ShieldCheck from '~icons/lucide/shield-check';
import HeartPulse from '~icons/lucide/heart-pulse';
import HardDrive from '~icons/lucide/hard-drive';
import Bell from '~icons/lucide/bell';
import Calendar from '~icons/lucide/calendar';
import ListOrdered from '~icons/lucide/list-ordered';
import LayoutDashboard from '~icons/lucide/layout-dashboard';
import PlayCircle from '~icons/lucide/play-circle';
import Users from '~icons/lucide/users';
import Bot from '~icons/lucide/bot';
import FileText from '~icons/lucide/file-text';
import Lock from '~icons/lucide/lock';
import Plug from '~icons/lucide/plug';
import RefreshCw from '~icons/lucide/refresh-cw';
import ShoppingCart from '~icons/lucide/shopping-cart';
import { unreadNotificationsCount } from '../data/notifications';

export default {
	name: 'NavigationItems',
	data() {
		return { backupRunning: false };
	},
	computed: {
		navigation() {
			if (!this.$team?.doc) return [];

			const routeName = this.$route?.name || '';
			const adminTab = this.$route?.params?.tab || '';
			const onboardingComplete = this.$team.doc.onboarding.complete;
			const isSaasUser = this.$team.doc.is_saas_user;
			const enforce2FA = Boolean(
				!this.$team.doc.is_desk_user &&
					this.$team.doc.enforce_2fa &&
					!this.$team.doc.user_info?.is_2fa_enabled,
			);

			return [
				{
					name: 'Welcome',
					icon: () => h(DoorOpen),
					route: '/welcome',
					isActive: routeName === 'Welcome',
					condition: !onboardingComplete,
				},
				{
					name: 'Notifications',
					icon: () => h(Notification),
					route: '/notifications',
					isActive: routeName === 'Press Notification List',
					condition: onboardingComplete && !isSaasUser,
					badge: () => {
						if (unreadNotificationsCount.data > 0) {
							return h(
								'span',
								{
									class: '!ml-auto px-1.5 py-0.5 text-xs text-gray-600',
								},
								unreadNotificationsCount.data > 99
									? '99+'
									: unreadNotificationsCount.data,
							);
						}
					},
					disabled: enforce2FA,
				},
				{
					name: 'Sites',
					icon: () => h(PanelTopInactive),
					route: '/sites',
					isActive:
						['Site List', 'Site Detail', 'New Site'].includes(routeName) ||
						routeName.startsWith('Site Detail'),
					disabled: enforce2FA,
				},
				/* {
					name: 'Benches',
					icon: () => h(Package),
					route: '/benches',
					isActive: routeName.startsWith('Bench'),
					condition: this.$team.doc?.is_desk_user,
					disabled: !onboardingComplete || enforce2FA,
				}, */
				{
					name: 'Benches',
					icon: () => h(Boxes),
					route: onboardingComplete ? '/groups' : '/enable-bench-groups',
					isActive:
						[
							'Release Group List',
							'Release Group Detail',
							'New Release Group',
							'Release Group New Site',
							'Deploy Candidate',
						].includes(routeName) ||
						routeName.startsWith('Release Group Detail') ||
						routeName === 'Enable Benches',
					disabled: enforce2FA,
				},
				{
					name: 'Servers',
					icon: () => h(Server),
					route: onboardingComplete ? '/servers' : '/enable-servers',
					isActive:
						['New Server'].includes(routeName) ||
						routeName.startsWith('Server') ||
						routeName === 'Enable Servers',
					disabled: enforce2FA,
				},
				{
					name: 'Infrastructure',
					icon: () => h(ServerCog),
					route: '/infrastructure',
					isActive: routeName === 'Infrastructure',
					condition: onboardingComplete && !isSaasUser && this.$session.isSystemUser,
					disabled: enforce2FA,
				},
				{
					name: 'Telephony',
					icon: () => h(Phone),
					route: '/telephony',
					isActive: routeName === 'Telephony',
					condition: onboardingComplete && !isSaasUser && this.$session.isSystemUser,
					disabled: enforce2FA,
				},
				{
					name: 'Backups',
					icon: () => h(Archive),
					route: '/backups',
					condition: onboardingComplete && !isSaasUser,
					disabled: enforce2FA,
					children: [
						{
							name: 'Site Backups',
							icon: () => h(PanelTopInactive),
							route: '/backups/sites',
							isActive: routeName === 'Site Backups',
						},
						{
							name: 'Snapshots',
							icon: () => h(Camera),
							route: '/backups/snapshots',
							isActive: routeName === 'Snapshots',
						},
					].filter((item) => item.condition ?? true),
					isActive: ['Site Backups', 'Snapshots'].includes(routeName),
					disabled: enforce2FA,
				},
				{
					name: this.backupRunning ? 'Daman Backup …' : 'Daman Backup',
					icon: () => h(HardDrive),
					route: '/backups/overview',
					condition: onboardingComplete && !isSaasUser && this.$session.isSystemUser && this.hasFeature('daman_backup'),
					disabled: enforce2FA,
					children: [
						{
							name: 'Overview',
							icon: () => h(LayoutDashboard),
							route: '/backups/overview',
							isActive: routeName === 'Daman Overview',
						},
						{
							name: 'Backup Jobs',
							icon: () => h(PlayCircle),
							route: '/backups/servers',
							isActive: routeName === 'Daman Backup Jobs',
						},
						{
							name: 'Job Queue',
							icon: () => h(ListOrdered),
							route: '/backups/jobs',
							isActive: routeName === 'Daman Job Queue',
						},
						{
							name: 'Backup Servers',
							icon: () => h(HardDrive),
							route: '/backups/backup-servers',
							isActive: routeName === 'Daman Backup Servers',
						},
						{
							name: 'Clients',
							icon: () => h(Users),
							route: '/backups/clients',
							isActive: routeName === 'Daman Clients' || routeName === 'Daman Client Detail',
						},
						{
							name: 'Run Log',
							icon: () => h(Logs),
							route: '/backups/run-log',
							isActive: routeName === 'Daman Run Log',
						},
						{
							name: 'DR Restore',
							icon: () => h(PlayCircle),
							route: '/backups/dr-restore',
							isActive: routeName === 'Daman DR Restore',
						},
						{
							name: 'Restore Tests',
							icon: () => h(Calendar),
							route: '/backups/restore-tests',
							isActive: routeName === 'Daman Restore Tests',
						},
						{
							name: 'Alerts',
							icon: () => h(Bell),
							route: '/backups/alerts',
							isActive: routeName === 'Daman Backup Alerts',
						},
					],
					isActive: ['Daman Overview', 'Daman Backup Jobs', 'Daman Job Queue', 'Daman Backup Servers', 'Daman Clients', 'Daman Client Detail', 'Daman Run Log', 'Daman DR Restore', 'Daman Restore Tests', 'Daman Backup Alerts'].includes(routeName),
				},
				{
					name: 'Dev Tools',
					icon: () => h(Code),
					route: '/devtools',
					condition: onboardingComplete && !isSaasUser && this.hasFeature('dev_overview'),
					disabled: enforce2FA,
					children: [
						{
							name: 'Dev Overview',
							icon: () => h(LayoutDashboard),
							route: '/dev-overview',
							isActive: routeName === 'Dev Overview',
						},
						{
							name: 'Code Health',
							icon: () => h(HeartPulse),
							route: '/code-health',
							isActive: routeName === 'Code Health',
						},
						{
							name: 'Log Browser',
							icon: () => h(Logs),
							route: '/log-browser',
							isActive: routeName === 'Log Browser',
						},
						{
							name: 'DB Analyzer',
							icon: () => h(Activity),
							route: '/database-analyzer',
							isActive: routeName === 'DB Analyzer',
						},
						{
							name: 'SQL Playground',
							icon: () => h(DatabaseZap),
							route: '/sql-playground',
							isActive: routeName === 'SQL Playground',
						},
						{
							name: 'Binlog Browser',
							icon: () => h(FileSearch),
							route: '/binlog-browser',
							isActive: routeName === 'Binlog Browser',
							condition: this.$team.doc.is_binlog_indexer_enabled ?? false,
						},
						{
							name: 'MCP Server',
							icon: () => h(Server),
							route: '/dev-tools/mcp',
							isActive: routeName === 'MCP Panel',
						},
					].filter((item) => item.condition ?? true),
					isActive: [
						'Dev Overview',
						'Code Health',
						'Log Browser',
						'DB Analyzer',
						'SQL Playground',
						'Binlog Browser',
						'MCP Panel',
					].includes(routeName),
					disabled: enforce2FA,
				},
				{
					name: 'Marketplace',
					icon: () => h(App),
					route: '/apps',
					isActive: routeName.startsWith('Marketplace'),
					condition:
						this.$team.doc?.is_desk_user ||
						(!!this.$team.doc.is_developer && this.$session.hasAppsAccess),
					disabled: enforce2FA,
				},
				{
					name: 'Billing',
					icon: () => h(WalletCards),
					route: '/billing',
					isActive: routeName.startsWith('Billing'),
					condition:
						this.$team.doc?.is_desk_user || this.$session.hasBillingAccess,
					disabled: enforce2FA,
				},
				{
					name: 'Access Requests',
					icon: () => h(Key),
					route: '/access-requests',
					isActive: routeName === 'Access Requests',
					disabled: enforce2FA,
				},
				{
					name: 'Partnership',
					icon: () => h(Globe),
					route: '/partners',
					isActive: routeName === 'Partnership',
					condition: Boolean(this.$team.doc.erpnext_partner),
					disabled: enforce2FA,
				},
				{
					name: 'Settings',
					icon: () => h(Settings),
					route: '/settings',
					isActive: routeName.startsWith('Settings'),
					disabled: enforce2FA,
				},
				{
					name: 'Partner Admin',
					icon: () => h(Shield),
					route: '/partner-admin',
					isActive: routeName === 'Partner Admin',
					condition: Boolean(this.$team.doc.is_desk_user) && this.hasFeature('partner_admin'),
				},
				{
					name: 'Sanad AI',
					icon: () => h(Bot),
					route: '/admin/ai-governance',
					condition: Boolean(this.$team.doc.is_desk_user),
					children: [
						{
							name: 'AI Governance',
							icon: () => h(ShieldCheck),
							route: '/admin/ai-governance',
							isActive: routeName === 'Admin Panel' && adminTab === 'ai-governance',
						},
						{
							name: 'Usage & Cost',
							icon: () => h(LayoutDashboard),
							route: '/admin/usage-cost',
							isActive: routeName === 'Admin Panel' && adminTab === 'usage-cost',
						},
						{
							name: 'Insights',
							icon: () => h(Activity),
							route: '/admin/insights',
							isActive: routeName === 'Admin Panel' && adminTab === 'insights',
						},
						{
							name: 'Seats',
							icon: () => h(Users),
							route: '/admin/seats',
							isActive: routeName === 'Admin Panel' && adminTab === 'seats',
						},
						{
							name: 'Providers',
							icon: () => h(Plug),
							route: '/admin/providers',
							isActive: routeName === 'Admin Panel' && adminTab === 'providers',
						},
						{
							name: 'Subscriptions',
							icon: () => h(RefreshCw),
							route: '/admin/subscriptions',
							isActive: routeName === 'Admin Panel' && adminTab === 'subscriptions',
						},
						{
							name: 'Escalations',
							icon: () => h(Bell),
							route: '/admin/escalations',
							isActive: routeName === 'Admin Panel' && adminTab === 'escalations',
						},
						{
							name: 'Buy seats',
							icon: () => h(ShoppingCart),
							route: '/admin/buy-seats',
							isActive: routeName === 'Admin Panel' && adminTab === 'buy-seats',
						},
					],
					isActive:
						routeName === 'Admin Panel' &&
						['ai-governance', 'usage-cost', 'insights', 'seats', 'providers', 'subscriptions', 'escalations', 'buy-seats'].includes(adminTab),
				},
				{
					name: 'Admin Panel',
					icon: () => h(ShieldCheck),
					route: '/admin/teams',
					condition: Boolean(this.$team.doc.is_desk_user),
					children: [
						{
							name: 'Teams',
							icon: () => h(Users),
							route: '/admin/teams',
							isActive: routeName === 'Admin Panel' && (adminTab === 'teams' || adminTab === ''),
						},
						{
							name: 'Servers',
							icon: () => h(Server),
							route: '/admin/servers',
							isActive: routeName === 'Admin Panel' && adminTab === 'servers',
						},
						{
							name: 'Policy',
							icon: () => h(FileText),
							route: '/admin/policy',
							isActive: routeName === 'Admin Panel' && adminTab === 'policy',
						},
						{
							name: 'Security',
							icon: () => h(Lock),
							route: '/admin/security',
							isActive: routeName === 'Admin Panel' && adminTab === 'security',
						},
						{
							name: 'MCP',
							icon: () => h(Key),
							route: '/admin/mcp',
							isActive: routeName === 'Admin Panel MCP',
						},
					],
					isActive:
						(routeName === 'Admin Panel' &&
							['', 'teams', 'servers', 'policy', 'security'].includes(adminTab)) ||
						routeName === 'Admin Panel MCP',
				},
			{
				name: 'Tessera',
				icon: () => h(Key),
				route: '/tessera/overview',
				condition: Boolean(this.$team.doc.is_desk_user),
				children: [
					{
						name: 'Overview',
						icon: () => h(LayoutDashboard),
						route: '/tessera/overview',
						isActive: routeName === 'TesseraAdmin' && adminTab === 'overview',
					},
					{
						name: 'Licenses',
						icon: () => h(Key),
						route: '/tessera/licenses',
						isActive: routeName === 'TesseraAdmin' && adminTab === 'licenses',
					},
					{
						name: 'Seats',
						icon: () => h(Users),
						route: '/tessera/seats',
						isActive: routeName === 'TesseraAdmin' && adminTab === 'seats',
					},
					{
						name: 'Heartbeat',
						icon: () => h(Bell),
						route: '/tessera/heartbeat',
						isActive: routeName === 'TesseraAdmin' && adminTab === 'heartbeat',
					},
					{
						name: 'Offline',
						icon: () => h(Plug),
						route: '/tessera/offline',
						isActive: routeName === 'TesseraAdmin' && adminTab === 'offline',
					},
				],
				isActive: routeName === 'TesseraAdmin' && ['overview', 'licenses', 'seats', 'heartbeat', 'offline'].includes(adminTab),
			},
			{
				name: 'Customers',
				icon: () => h(Users),
				route: '/customers/overview',
				condition: Boolean(this.$team.doc.is_desk_user),
				children: [
					{
						name: 'Overview',
						icon: () => h(LayoutDashboard),
						route: '/customers/overview',
						isActive: routeName === 'CustomersAdmin' && adminTab === 'overview',
					},
					{
						name: 'Accounts',
						icon: () => h(Users),
						route: '/customers/accounts',
						isActive: routeName === 'CustomersAdmin' && adminTab === 'accounts',
					},
				],
				isActive: routeName === 'CustomersAdmin' && ['overview', 'accounts'].includes(adminTab),
			},
			].filter((item) => item.condition ?? true);
		},
	},
	mounted() {
		this.$socket.emit('doctype_subscribe', 'Press Notification');
		this.$socket.on('press_notification', (data) => {
			if (data.team === this.$team.doc.name) {
				unreadNotificationsCount.setData((data) => data + 1);
			}
		});
		this.$socket.on('backup_job_started', () => { this.backupRunning = true; });
		this.$socket.on('backup_job_completed', () => { this.backupRunning = false; });
		this.$socket.on('backup_job_failed', () => { this.backupRunning = false; });
	},
	unmounted() {
		this.$socket.off('press_notification');
		this.$socket.off('backup_job_started');
		this.$socket.off('backup_job_completed');
		this.$socket.off('backup_job_failed');
	},
	methods: {
		hasFeature(id) {
			const f = this.$team.doc?.enabled_features;
			if (!f || typeof f !== 'object' || Object.keys(f).length === 0) return true;
			return !!f[id];
		},
	},
};
</script>
