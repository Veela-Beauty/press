<template>
	<Dialog :options="{ title: 'Restore from Daman Backup' }" v-model="show">
		<template #body-content>
			<div
				class="mb-6 flex items-start rounded border border-red-200 bg-red-50 p-4 text-sm text-red-700"
			>
				<lucide-alert-triangle class="mr-3 h-5 w-5 flex-shrink-0" />
				<div>
					This will <b>OVERWRITE</b> {{ site }}'s data, files & apps with the
					selected backup. This action cannot be undone.
				</div>
			</div>
			<div class="space-y-4">
				<FormControl
					label="Backup Client"
					type="select"
					:options="clientOptions"
					v-model="selectedClient"
					:disabled="$resources.clients.loading"
				/>
				<FormControl
					label="Backup Run Log"
					type="select"
					:options="runLogOptions"
					v-model="selectedRunLog"
					:disabled="!selectedClient || $resources.runLogs.loading"
				/>
				<div
					v-if="matchPreview"
					class="rounded border border-gray-200 bg-gray-50 p-3 text-sm"
				>
					<div class="mb-1 font-semibold">{{ matchPreview.tier }}</div>
					<div class="text-gray-600">
						Bench: {{ matchPreview.best_bench || '—' }} · Score:
						{{ matchPreview.score }}
					</div>
					<ul class="mt-2 list-inside list-disc text-xs text-gray-500">
						<li v-for="r in matchPreview.reasons" :key="r">{{ r }}</li>
					</ul>
				</div>
				<FormControl
					label="Skip failing patches (if any patch fails)"
					type="checkbox"
					v-model="skipFailingPatches"
				/>
			</div>
			<ErrorMessage class="mt-2" :message="errorMessage" />
		</template>
		<template #actions>
			<Button
				class="w-full"
				label="Restore"
				variant="solid"
				theme="red"
				:loading="$resources.startOverwriteRestore.loading"
				:disabled="!canRestore"
				@click="onRestoreClick"
			/>
		</template>
	</Dialog>
</template>
<script>
import { confirmDialog } from '../../utils/components';

export default {
	name: 'SiteRestoreFromDamanDialog',
	props: {
		site: { type: String, required: true },
	},
	data() {
		return {
			show: true,
			selectedClient: null,
			selectedRunLog: null,
			matchPreview: null,
			skipFailingPatches: false,
			errorMessage: '',
		};
	},
	resources: {
		clients() {
			return {
				url: 'daman_backup.daman_backup.press_api.list_backup_clients_for_restore',
				auto: true,
			};
		},
		runLogs() {
			return {
				url: 'daman_backup.daman_backup.press_api.list_run_logs_for_client',
				params: () => ({ client: this.selectedClient, limit: 20 }),
				auto: false,
			};
		},
		previewMatch() {
			return {
				url: 'daman_backup.daman_backup.press_api.preview_restore_match',
				onSuccess: (data) => {
					this.matchPreview = data;
				},
				onError: (err) => {
					this.errorMessage = err.message || 'Match preview failed';
				},
			};
		},
		startOverwriteRestore() {
			return {
				url: 'daman_backup.daman_backup.press_api.start_overwrite_restore',
				onSuccess: () => {
					this.show = false;
					this.$emit('success');
				},
				onError: (err) => {
					this.errorMessage = err.message || 'Restore failed';
				},
			};
		},
	},
	computed: {
		clientOptions() {
			return (this.$resources.clients.data || []).map((c) => ({
				label: c.name,
				value: c.name,
			}));
		},
		runLogOptions() {
			return (this.$resources.runLogs.data || []).map((r) => ({
				label: `${r.name} (${r.finished_at}, ${r.upload_size_mb}MB)`,
				value: r.name,
			}));
		},
		canRestore() {
			return (
				this.selectedRunLog &&
				this.matchPreview &&
				typeof this.matchPreview.tier === 'string' &&
				this.matchPreview.tier.startsWith('T1')
			);
		},
	},
	watch: {
		selectedClient(newVal, oldVal) {
			if (newVal === oldVal) return;
			this.selectedRunLog = null;
			this.matchPreview = null;
			if (newVal) this.$resources.runLogs.submit();
		},
		selectedRunLog(newVal, oldVal) {
			if (newVal === oldVal) return;
			this.matchPreview = null;
			if (newVal) {
				this.$resources.previewMatch.submit({
					backup_run_log: newVal,
				});
			}
		},
	},
	methods: {
		onRestoreClick() {
			confirmDialog({
				title: 'Confirm overwrite restore',
				message: `This will OVERWRITE ${this.site} with backup ${this.selectedRunLog}. Continue?`,
				primaryAction: {
					label: 'Yes, overwrite this site',
					theme: 'red',
					onClick: () =>
						this.$resources.startOverwriteRestore.submit({
							target_site: this.site,
							backup_run_log: this.selectedRunLog,
							skip_failing_patches: this.skipFailingPatches,
						}),
				},
			});
		},
	},
};
</script>
