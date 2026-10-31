<template>
	<Dialog
		:options="{
			title: 'Take Backup',
			actions: [
				{
					label: 'Start Backup',
					loading: $site?.backup?.loading,
					variant: 'solid',
					onClick: scheduleBackup,
				},
			],
		}"
		v-model="show"
	>
		<template #body-content>
			<div class="flex flex-col gap-3">
				<!-- Always shown: before 0.7.6 the files choice was hidden unless physical backup was enabled -->
				<div class="flex flex-col gap-2" role="radiogroup" aria-label="Backup contents">
					<label
						v-for="option in options"
						:key="option.value"
						class="flex items-start gap-3 rounded-[8px] border px-3 py-2.5"
						:class="[
							choice === option.value
								? 'border-outline-gray-4 bg-surface-gray-2'
								: 'border-outline-gray-2',
							isDisabled(option)
								? 'cursor-not-allowed opacity-50'
								: 'cursor-pointer hover:bg-surface-gray-1',
						]"
					>
						<input
							type="radio"
							class="mt-0.5"
							name="backup-contents"
							:value="option.value"
							v-model="choice"
							:disabled="isDisabled(option)"
						/>
						<span class="flex flex-col gap-0.5">
							<span class="text-base font-medium text-ink-gray-8">{{ option.label }}</span>
							<span class="text-p-sm text-ink-gray-6">{{ option.description }}</span>
						</span>
					</label>
				</div>

				<template v-if="$site?.doc?.allow_physical_backup_by_user">
					<FormControl
						variant="outline"
						type="checkbox"
						label="Physical Backup"
						v-model="isPhysical"
					/>
					<AlertBanner
						v-if="isPhysical"
						title="A physical backup copies the database only, and can cause some downtime depending on its size."
						type="warning"
						:showIcon="false"
					/>
				</template>
			</div>
		</template>
	</Dialog>
</template>

<script>
import { getCachedDocumentResource } from 'frappe-ui';
import { toast } from 'vue-sonner';
import { getToastErrorMessage } from '../../utils/toast';
import AlertBanner from '../AlertBanner.vue';

export default {
	props: ['site', 'onScheduleBackupSuccess'],
	components: {
		AlertBanner,
	},
	data() {
		return {
			show: true,
			isPhysical: false,
			choice: 'full',
			options: [
				{
					value: 'database',
					label: 'Database only',
					description: 'Faster and smaller. Good before a change or an update.',
				},
				{
					value: 'full',
					label: 'Full backup',
					description: 'Database plus public and private files (images, attachments).',
				},
			],
		};
	},
	watch: {
		isPhysical(newValue) {
			if (newValue) this.choice = 'database';
		},
	},
	computed: {
		$site() {
			return getCachedDocumentResource('Site', this.site);
		},
	},
	methods: {
		isDisabled(option) {
			return this.isPhysical && option.value === 'full';
		},
		scheduleBackup() {
			this.$router.push({
				name: 'Site Detail Backups',
				params: { name: this.$site.doc.name },
			});
			let site_backup_promise = this.$site.backup.submit({
				with_files: this.choice === 'full' && !this.isPhysical,
				physical: this.isPhysical,
			});
			toast.promise(site_backup_promise, {
				loading: 'Scheduling backup...',
				success: () => {
					this.show = false;
					if (this.onScheduleBackupSuccess) {
						this.onScheduleBackupSuccess();
					} else {
						this.$router.push({
							name: 'Site Detail Backups',
							params: { name: this.$site.doc.name },
						});
					}
					return 'Backup scheduled successfully.';
				},
				error: (e) => getToastErrorMessage(e),
			});
		},
	},
};
</script>
