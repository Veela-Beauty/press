<template>
	<Dialog :options="{ title: 'Auto-Drop Restored Site' }" v-model="show">
		<template #body-content>
			<div class="space-y-4">
				<div class="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
					<div class="mb-1 font-semibold">{{ site }}</div>
					<div class="text-xs text-amber-700">
						The site will be archived (and files cleaned by the daily 5 AM
						cleanup cron after 10 days). Use this for one-off demos so the
						bench disk doesn't fill up.
					</div>
				</div>

				<FormControl
					label="Drop after"
					type="select"
					:options="hourOptions"
					v-model="hours"
				/>

				<FormControl
					label="Reason (optional)"
					type="text"
					v-model="reason"
				/>

				<div
					v-if="existingDrop && existingDrop.status === 'Scheduled'"
					class="rounded border border-blue-200 bg-blue-50 p-3 text-xs text-blue-800"
				>
					Already scheduled to drop at <b>{{ existingDrop.drop_at }}</b>
					(by {{ existingDrop.scheduled_by }}). Saving will overwrite.
				</div>
			</div>
			<ErrorMessage class="mt-2" :message="errorMessage" />
		</template>
		<template #actions>
			<Button
				v-if="existingDrop && existingDrop.status === 'Scheduled'"
				class="mr-2"
				label="Cancel scheduled drop"
				variant="outline"
				:loading="$resources.cancelDrop.loading"
				@click="onCancelExisting"
			/>
			<Button
				class="w-full"
				label="Schedule drop"
				variant="solid"
				theme="amber"
				:loading="$resources.scheduleDrop.loading"
				@click="onSchedule"
			/>
		</template>
	</Dialog>
</template>
<script>
export default {
	name: 'SiteAutoDropDialog',
	props: {
		site: { type: String, required: true },
	},
	data() {
		return {
			show: true,
			hours: 4,
			reason: '',
			errorMessage: '',
			existingDrop: null,
			hourOptions: [
				{ label: '1 hour', value: 1 },
				{ label: '4 hours', value: 4 },
				{ label: '8 hours', value: 8 },
				{ label: '24 hours (1 day)', value: 24 },
				{ label: '72 hours (3 days)', value: 72 },
				{ label: '168 hours (1 week)', value: 168 },
			],
		};
	},
	resources: {
		getDrop() {
			return {
				url: 'daman_backup.daman_backup.press_api.get_site_auto_drop',
				params: { site: this.site },
				auto: true,
				onSuccess: (data) => {
					if (data && data.site) this.existingDrop = data;
				},
			};
		},
		scheduleDrop() {
			return {
				url: 'daman_backup.daman_backup.press_api.schedule_site_auto_drop',
				onSuccess: () => {
					this.show = false;
					this.$emit('scheduled');
				},
				onError: (err) => {
					this.errorMessage = err.message || 'Schedule failed';
				},
			};
		},
		cancelDrop() {
			return {
				url: 'daman_backup.daman_backup.press_api.cancel_site_auto_drop',
				onSuccess: () => {
					this.show = false;
					this.$emit('cancelled');
				},
				onError: (err) => {
					this.errorMessage = err.message || 'Cancel failed';
				},
			};
		},
	},
	methods: {
		onSchedule() {
			this.$resources.scheduleDrop.submit({
				site: this.site,
				hours: this.hours,
				reason: this.reason,
			});
		},
		onCancelExisting() {
			this.$resources.cancelDrop.submit({ site: this.site });
		},
	},
};
</script>
