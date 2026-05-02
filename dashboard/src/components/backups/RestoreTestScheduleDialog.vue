<template>
	<Dialog :options="{ title: existing ? 'Edit Schedule' : 'New Restore Test Schedule' }" v-model="show">
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					label="Backup Client"
					type="select"
					:options="clientOptions"
					v-model="form.client"
					:disabled="!!existing || $resources.clients.loading"
				/>
				<FormControl label="Frequency" type="select" :options="freqOptions" v-model="form.frequency" />
				<FormControl label="Enabled" type="checkbox" v-model="form.enabled" />
				<FormControl label="Notify on Failure (email + webhook)" type="checkbox" v-model="form.notify_on_failure" />
				<FormControl
					label="Archive Test Site After (Hours)"
					type="number"
					v-model="form.archive_after_hours"
					description="Default 24, range 1-168"
				/>
				<FormControl
					label="Extra DocTypes to Spot-Check (JSON list)"
					type="textarea"
					v-model="form.validation_doctypes"
					description='Optional. e.g. ["User", "Sales Invoice"]'
				/>
				<FormControl
					label="Webhook URL (Slack/Discord/Teams) — optional override"
					v-model="form.webhook_url"
					description="Leave blank to use the global Backup Settings.notification_webhook_url. POSTed with Slack-compatible JSON on Failed runs."
				/>
			</div>
			<ErrorMessage class="mt-2" :message="errorMessage" />
		</template>
		<template #actions>
			<Button
				class="w-full"
				label="Save"
				variant="solid"
				theme="blue"
				:loading="$resources.upsert.loading"
				:disabled="!form.client || !form.frequency"
				@click="onSave"
			/>
		</template>
	</Dialog>
</template>
<script>
export default {
	name: 'RestoreTestScheduleDialog',
	props: { existing: { type: Object, default: null } },
	data() {
		return {
			show: true,
			errorMessage: '',
			freqOptions: [
				{ label: 'Daily', value: 'Daily' },
				{ label: 'Weekly', value: 'Weekly' },
				{ label: 'Monthly', value: 'Monthly' },
			],
			form: {
				client: this.existing?.client || '',
				frequency: this.existing?.frequency || 'Weekly',
				enabled: this.existing?.enabled ?? 1,
				notify_on_failure: this.existing?.notify_on_failure ?? 1,
				archive_after_hours: this.existing?.archive_after_hours || 24,
				validation_doctypes: this.existing?.validation_doctypes || '[]',
				webhook_url: this.existing?.webhook_url || '',
			},
		};
	},
	resources: {
		clients() { return { url: 'daman_backup.daman_backup.press_api.list_backup_clients_for_restore', auto: true }; },
		upsert() {
			return {
				url: 'daman_backup.daman_backup.press_api.upsert_restore_test_schedule',
				onSuccess: () => { this.show = false; this.$emit('saved'); },
				onError: (err) => { this.errorMessage = err.message || 'Save failed'; },
			};
		},
	},
	computed: {
		clientOptions() {
			return (this.$resources.clients.data || []).map((c) => ({ label: c.name, value: c.name }));
		},
	},
	methods: {
		onSave() {
			this.$resources.upsert.submit({ ...this.form });
		},
	},
};
</script>
