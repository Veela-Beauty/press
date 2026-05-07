<template>
	<div class="flex items-center justify-between gap-1">
		<div>
			<h3 class="text-base font-medium">{{ props.actionLabel }}</h3>
			<p class="mt-1 text-p-base text-gray-600">{{ props.description }}</p>
		</div>
		<Button
			v-if="releaseGroup?.doc"
			class="whitespace-nowrap"
			@click="getBenchActionHandler(props.actionLabel)"
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
import { call, getCachedDocumentResource } from 'frappe-ui';
import { toast } from 'vue-sonner';
import { confirmDialog } from '../../utils/components';
import router from '../../router';

const props = defineProps({
	benchName: { type: String, required: true },
	actionLabel: { type: String, required: true },
	method: { type: String, required: true },
	description: { type: String, required: true },
	buttonLabel: { type: String, required: true },
	group: { type: String, required: false },
	linkedVersionUpgrade: { type: Boolean, required: false, default: false },
});

const releaseGroup = getCachedDocumentResource(
	'Release Group',
	props.benchName,
);

function getBenchActionHandler(action) {
	const actionHandlers = {
		'Rename Bench': onRenameBench,
		'Transfer Bench': onTransferBench,
		'Clone Bench': onCloneBench,
		'Lock Bench': onLockBench,
		'Drop Bench': onDropBench,
	};
	if (actionHandlers[action]) {
		actionHandlers[action].call(this);
	}
}

function onRenameBench() {
	confirmDialog({
		title: 'Rename Bench',
		fields: [
			{
				label: 'Enter new bench name',
				fieldname: 'newBenchName',
			},
		],
		onSuccess({ hide, values }) {
			if (values.newBenchName) {
				toast.promise(
					releaseGroup.setValue.submit(
						{
							title: values.newBenchName,
						},
						{
							onSuccess() {
								hide();
							},
						},
					),
					{
						loading: 'Renaming bench...',
						success: 'Bench renamed successfully',
						error: 'Failed to rename bench',
					},
				);
			} else {
				toast.error('Please enter a valid bench name');
			}
		},
	});
}

function onCloneBench() {
	confirmDialog({
		title: 'Clone Bench',
		message:
			'Create a copy of this bench (Release Group) on the same server with the same apps. The clone will be assigned to your team and a deploy will be queued automatically.',
		fields: [
			{
				label: 'New title for the cloned bench',
				fieldname: 'new_title',
				default: `${releaseGroup.doc?.title || ''} (Clone)`,
			},
			{
				label: 'Lifetime',
				fieldname: 'lifetime',
				fieldtype: 'Select',
				options: [
					{ label: 'Persistent (kept until deleted)', value: 'persistent' },
					{ label: 'Sandbox (auto-deleted after 24h)', value: 'sandbox' },
				],
				default: 'persistent',
			},
		],
		primaryAction: {
			label: 'Clone',
			variant: 'solid',
		},
		onSuccess({ hide, values }) {
			if (!values.new_title) {
				toast.error('Please enter a title for the cloned bench');
				return;
			}
			toast.promise(
				call(
					'press.press.doctype.release_group.release_group_clone.clone_release_group',
					{
						release_group: props.benchName,
						new_title: values.new_title,
						lifetime: values.lifetime || 'persistent',
					},
				).then((newName) => {
					hide();
					router.push(`/groups/${newName}`);
					return newName;
				}),
				{
					loading: 'Cloning bench...',
					success: (newName) => `Cloned bench created: ${newName}`,
					error: (e) =>
						`Failed to clone bench: ${e?.messages?.[0] || e?.message || e}`,
				},
			);
		},
	});
}

function onLockBench() {
	confirmDialog({
		title: 'Lock Bench',
		message:
			'Acquire an advisory lock on this bench. Other agents will see your lock + reason and decide whether to wait or override.',
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
					target_doctype: 'Release Group',
					target_name: props.benchName,
					reason: values.reason,
					ttl_minutes: parseInt(values.ttl) || 30,
					override: values.override ? 1 : 0,
				}).then((result) => {
					hide();
					if (result.status === 'blocked') {
						throw new Error(`Already locked by ${result.holder}: ${result.reason}`);
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

function onTransferBench() {
	confirmDialog({
		title: 'Transfer Bench Ownership',
		fields: [
			{
				label:
					'Enter email address of the team for transfer of bench ownership',
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
				if (!values.email) {
					throw new Error('Please enter a valid email address');
				}

				return releaseGroup.sendTransferRequest
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

function onDropBench() {
	let message = `Are you sure you want to drop the bench <b>${
		releaseGroup.doc.title || releaseGroup.name
	}</b>?`;

	if (props.linkedVersionUpgrade) {
		message = `
			<div class="mb-4 p-3 bg-yellow-50 border-l-4 border-yellow-400 text-yellow-800">
				<p class="font-semibold">Warning</p>
				<p class="mt-1">This bench was created for upgrading your site's version and dropping this will cancel the site upgrade as well.</p>
			</div>
			${message}
		`;
	}

	confirmDialog({
		title: 'Drop Bench',
		message: message,
		fields: [
			{
				label: 'Please type the bench name to confirm',
				fieldname: 'confirmBenchName',
			},
		],
		primaryAction: {
			label: 'Drop',
			theme: 'red',
			onClick: ({ hide, values }) => {
				if (releaseGroup.delete.loading) return;
				if (values.confirmBenchName !== releaseGroup.doc.title) {
					throw new Error('Bench name does not match');
				}
				toast.promise(
					releaseGroup.delete.submit(null, {
						onSuccess: () => {
							hide();
							router.push({ name: 'Release Group List' });
						},
					}),
					{
						loading: 'Dropping bench...',
						success: 'Bench dropped successfully',
						error: (error) =>
							error.messages.length
								? error.messages.join('\n')
								: 'Failed to drop bench',
					},
				);
			},
		},
	});
}
</script>
