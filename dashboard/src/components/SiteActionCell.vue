<template>
	<div class="flex items-center justify-between gap-1">
		<div>
			<h3 class="text-base font-medium">{{ props.actionLabel }}</h3>
			<p class="mt-1 text-p-base text-gray-600">{{ props.description }}</p>
		</div>
		<Button
			v-if="site?.doc"
			class="whitespace-nowrap"
			@click="getSiteActionHandler(props.actionLabel)"
		>
			<p
				:class="
					group === 'Dangerous Actions' ? 'text-red-600' : 'text-gray-800'
				"
			>
				{{ props.buttonLabel }}
			</p>
		</Button>
	</div>
</template>

<script setup>
import { getCachedDocumentResource, call } from 'frappe-ui';
import { defineAsyncComponent, h } from 'vue';
import { toast } from 'vue-sonner';
import { confirmDialog, renderDialog } from '../utils/components';
import { getToastErrorMessage } from '../utils/toast';
import router from '../router';
import { isLastSite } from '../data/team';
import CommunicationInfoDialog from './CommunicationInfoDialog.vue';

const props = defineProps({
	siteName: { type: String, required: true },
	actionLabel: { type: String, required: true },
	method: { type: String, required: true },
	description: { type: String, required: true },
	buttonLabel: { type: String, required: true },
	group: { type: String, required: false },
});

const site = getCachedDocumentResource('Site', props.siteName);

function getSiteActionHandler(action) {
	const actionDialogs = {
		'Restore with files': defineAsyncComponent(
			() => import('./SiteDatabaseRestoreDialog.vue'),
		),
		'Restore from an existing site': defineAsyncComponent(
			() => import('./site/SiteDatabaseRestoreFromURLDialog.vue'),
		),
		'Restore from Daman Backup': defineAsyncComponent(
			() => import('./site/SiteRestoreFromDamanDialog.vue'),
		),
		'Manage database users': defineAsyncComponent(
			() => import('./SiteDatabaseAccessDialog.vue'),
		),
		'Version upgrade': defineAsyncComponent(
			() => import('./site/SiteVersionUpgradeDialog.vue'),
		),
		'Schedule backup': defineAsyncComponent(
			() => import('./site/SiteScheduleBackup.vue'),
		),
	};
	if (actionDialogs[action]) {
		const dialog = h(actionDialogs[action], { site: site.doc.name });
		renderDialog(dialog);
		return;
	}

	const actionHandlers = {
		'Notification Settings': onNotificationSettings,
		'Activate site': onActivateSite,
		'Deactivate site': onDeactivateSite,
		'Drop site': onDropSite,
		'Migrate site': onMigrateSite,
		'Clone site': onCloneSite,
		'Lock site': onLockSite,
		'Transfer site': onTransferSite,
		'Reset site': onSiteReset,
		'Clear cache': onClearCache,
		'Schedule backup': onScheduleBackup,
	};
	if (actionHandlers[action]) {
		actionHandlers[action].call(this);
	}
}

function onNotificationSettings() {
	return renderDialog(
		h(CommunicationInfoDialog, {
			referenceDoctype: 'Site',
			referenceName: site.doc.name,
		}),
	);
}

function onDeactivateSite() {
	return confirmDialog({
		title: 'Deactivate Site',
		message: `
			Are you sure you want to deactivate this site?<br><br>
			<div class="text-bg-base bg-gray-100 p-2 rounded-md">
			The site will go in an <strong>inactive</strong> state. It won't be accessible and background jobs won't run. 
			<br><br>
			<div class="text-red-600">You will still be charged for it.</div>
			</div>
		`,
		primaryAction: {
			label: 'Deactivate',
			variant: 'solid',
			theme: 'red',
			onClick({ hide }) {
				return site.deactivate.submit().then(hide);
			},
		},
	});
}

function onActivateSite() {
	return confirmDialog({
		title: 'Activate Site',
		message: `
			Are you sure you want to activate this site?
			<br><br>
			<strong>Note: Use this as last resort if site is broken and inaccessible</strong>
		`,
		primaryAction: {
			label: 'Activate',
			variant: 'solid',
			onClick({ hide }) {
				return site.activate.submit().then(hide);
			},
		},
	});
}

function onDropSite() {
	const ArchiveSiteDialog = defineAsyncComponent(
		() => import('./site/ArchiveSiteDialog.vue'),
	);

	return renderDialog(
		h(ArchiveSiteDialog, {
			site: site,
			modelValue: true,
		}),
	);
}

function onMigrateSite() {
	return confirmDialog({
		title: 'Migrate Site',
		message: `
            <span class="rounded-sm bg-gray-100 p-0.5 font-mono text-sm font-semibold">bench migrate</span>
            command will be executed on your site. Are you sure you want to run this
            command? We recommend that you take a database backup before continuing.
        `,
		fields: [
			{
				label: 'Skip patches if they fail during migration (Not recommended)',
				fieldname: 'skipFailingPatches',
				type: 'checkbox',
			},
			{
				label: 'Please type the site name to confirm.',
				fieldname: 'confirmSiteName',
			},
		],
		primaryAction: {
			label: 'Migrate',
			variant: 'solid',
			theme: 'red',
			onClick: ({ hide, values }) => {
				if (values.confirmSiteName !== site.doc.name) {
					throw new Error('Site name does not match');
				}
				return site.migrate
					.submit({ skip_failing_patches: values.skipFailingPatches })
					.then(hide);
			},
		},
	});
}

function onCloneSite() {
	confirmDialog({
		title: 'Clone Site',
		message:
			'Create a copy of this site onto a target bench. Three data modes are supported: latest_backup (use most recent offsite backup, fast), fresh_backup (trigger a new backup first, slowest), or empty (no data, just install apps).',
		fields: [
			{
				label: 'Target Bench (the Bench to host the cloned site)',
				fieldname: 'target_bench',
			},
			{
				label: 'New subdomain (without the root domain)',
				fieldname: 'new_subdomain',
			},
			{
				label: 'Data mode',
				fieldname: 'mode',
				fieldtype: 'Select',
				options: [
					{ label: 'Latest backup (fast, uses most recent offsite backup)', value: 'latest_backup' },
					{ label: 'Fresh backup (slow, triggers new backup first)', value: 'fresh_backup' },
					{ label: 'Empty (no data, just install apps)', value: 'empty' },
				],
				default: 'latest_backup',
			},
		],
		primaryAction: {
			label: 'Clone',
			variant: 'solid',
		},
		onSuccess({ hide, values }) {
			if (!values.target_bench || !values.new_subdomain) {
				toast.error('Target bench and new subdomain are required');
				return;
			}
			toast.promise(
				call('press.press.doctype.site.site_clone.clone_site', {
					site: props.siteName,
					target_bench: values.target_bench,
					new_subdomain: values.new_subdomain,
					mode: values.mode || 'latest_backup',
				}).then((newName) => {
					hide();
					router.push(`/sites/${newName}`);
					return newName;
				}),
				{
					loading: 'Cloning site...',
					success: (newName) => `Cloned site created: ${newName}`,
					error: (e) =>
						`Failed to clone site: ${e?.messages?.[0] || e?.message || e}`,
				},
			);
		},
	});
}

function onLockSite() {
	confirmDialog({
		title: 'Lock Site',
		message:
			'Acquire an advisory lock on this site. Other agents will see your lock + reason.',
		fields: [
			{
				label: 'Reason for locking (required)',
				fieldname: 'reason',
			},
			{
				label: 'TTL (minutes, max 1440)',
				fieldname: 'ttl',
				default: '30',
			},
			{
				label: 'Force override existing lock',
				fieldname: 'override',
				fieldtype: 'Check',
			},
		],
		primaryAction: { label: 'Acquire Lock', variant: 'solid' },
		onSuccess({ hide, values }) {
			if (!values.reason) {
				toast.error('Reason is required');
				return;
			}
			toast.promise(
				call('press.api.lock.acquire', {
					target_doctype: 'Site',
					target_name: props.siteName,
					reason: values.reason,
					ttl_minutes: parseInt(values.ttl) || 30,
					override: values.override ? 1 : 0,
				}).then((result) => {
					hide();
					if (result.status === 'blocked') {
						throw new Error(`Already locked by ${result.holder}: ${result.reason}`);
					}
					if (result.status === 'blocked_by_parent') {
						throw new Error(`Bench is locked by ${result.parent_lock?.holder}; release that first`);
					}
					return result;
				}),
				{
					loading: 'Acquiring lock...',
					success: 'Lock acquired',
					error: (e) => `Could not acquire lock: ${e?.messages?.[0] || e?.message || e}`,
				},
			);
		},
	});
}

function onSiteReset() {
	return confirmDialog({
		title: 'Reset Site',
		message: `
            All the data from your site will be lost. Are you sure you want to reset your database?
        `,
		fields: [
			{
				label: 'Please type the site name to confirm.',
				fieldname: 'confirmSiteName',
			},
		],
		primaryAction: {
			label: 'Reset',
			variant: 'solid',
			theme: 'red',
			onClick: ({ hide, values }) => {
				if (values.confirmSiteName !== site.doc.name) {
					throw new Error('Site name does not match.');
				}
				return site.reinstall.submit().then(hide);
			},
		},
	});
}

function onTransferSite() {
	return confirmDialog({
		title: 'Transfer Site Ownership',
		fields: [
			{
				label: 'Enter email address of the team for transfer of site ownership',
				fieldname: 'email',
			},
			{
				label: 'Reason for transfer',
				fieldname: 'reason',
				type: 'textarea',
			},
		],
		primaryAction: {
			label: 'Transfer',
			variant: 'solid',
			onClick: ({ hide, values }) => {
				return site.sendTransferRequest
					.submit({ team_mail_id: values.email, reason: values.reason || '' })
					.then(() => {
						hide();
						toast.success(
							`Transfer request sent to ${values.email} successfully.`,
						);
					});
			},
		},
	});
}

function onClearCache() {
	return confirmDialog({
		title: 'Clear Cache',
		message: `<span class="rounded-sm bg-gray-100 p-0.5 font-mono text-sm font-semibold">bench clear-cache</span> and
            <span class="rounded-sm bg-gray-100 p-0.5 font-mono text-sm font-semibold">bench clear-website-cache</span> commands
            will be executed on your site. Are you sure you want to run these commands?`,
		primaryAction: {
			label: 'Clear Cache',
			variant: 'solid',
			onClick: ({ hide }) => {
				return site.clearSiteCache.submit().then(hide);
			},
		},
	});
}

function onScheduleBackup() {
	router.push({
		name: 'Site Detail Backups',
		params: { name: site.doc.name },
	});
}
</script>
