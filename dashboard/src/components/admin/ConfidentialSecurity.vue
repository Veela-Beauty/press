<template>
	<div class="rounded-lg border border-gray-200 bg-white">
		<div class="border-b border-gray-100 px-4 py-3">
			<p class="text-sm font-semibold">Confidential Site Admin PIN</p>
			<p class="mt-1 text-xs text-gray-500">
				Sites marked Confidential require this PIN before Login As Administrator.
				A PIN change is confirmed by email before it takes effect.
			</p>
		</div>
		<div class="flex flex-wrap gap-2 px-4 py-3">
			<Button variant="solid" @click="changePin">Change PIN</Button>
			<Button @click="resetPin">Forgot PIN (email reset)</Button>
		</div>
	</div>
</template>

<script setup>
import { call, Button } from 'frappe-ui';
import { confirmDialog } from '../../utils/components';
import { toast } from 'vue-sonner';

function changePin() {
	confirmDialog({
		title: 'Change Admin PIN',
		message:
			'A confirmation link will be emailed. The new PIN only takes effect after the link is clicked.',
		fields: [{ label: 'New PIN', type: 'password', fieldname: 'new_pin' }],
		onSuccess: ({ hide, values }) => {
			if (!values.new_pin || values.new_pin.length < 4) {
				throw new Error('PIN must be at least 4 characters');
			}
			return call('press.api.security.request_admin_pin_change', {
				new_pin: values.new_pin,
			}).then((r) => {
				toast.success(`Confirmation link sent to ${r?.sent_to || 'the alert email'}.`);
				hide();
			});
		},
	});
}

function resetPin() {
	call('press.api.security.request_admin_pin_reset')
		.then((r) => {
			toast.success(`Reset code sent to ${r?.sent_to || 'the alert email'}.`);
			confirmDialog({
				title: 'Reset Admin PIN',
				message: 'Enter the code emailed to you and the new PIN.',
				fields: [
					{ label: 'Reset Code', type: 'text', fieldname: 'otp' },
					{ label: 'New PIN', type: 'password', fieldname: 'new_pin' },
				],
				onSuccess: ({ hide, values }) => {
					if (!values.otp) throw new Error('Reset code is required');
					if (!values.new_pin || values.new_pin.length < 4) {
						throw new Error('PIN must be at least 4 characters');
					}
					return call('press.api.security.confirm_admin_pin_reset', {
						otp: values.otp,
						new_pin: values.new_pin,
					}).then(() => {
						toast.success('Admin PIN reset.');
						hide();
					});
				},
			});
		})
		.catch((e) => toast.error(e?.messages?.join(', ') || 'Failed to send reset code'));
}
</script>
