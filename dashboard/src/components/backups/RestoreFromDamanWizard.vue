<template>
	<Dialog :options="{ title: 'Create New Site from Daman Backup' }" v-model="show">
		<template #body-content>
			<div
				class="mb-4 flex items-start rounded border border-gray-200 bg-gray-50 p-3 text-sm text-gray-600"
			>
				<lucide-info class="mr-2 h-5 w-5 flex-shrink-0" />
				<div>
					This will create a new Press site from the selected backup. Existing
					sites are not modified.
				</div>
			</div>
			<div class="space-y-4">
				<FormControl
					label="Backup Client"
					type="select"
					:options="clientOptions"
					v-model="selectedClient"
					:disabled="$resources.clients.loading || !!prefilledClient"
				/>
				<FormControl
					label="Backup Run Log"
					type="select"
					:options="runLogOptions"
					v-model="selectedRunLog"
					:disabled="!selectedClient || $resources.runLogs.loading"
				/>
				<FormControl
					label="Target Site Name (optional)"
					description="Leave blank to auto-generate <client>-dr-NNN"
					v-model="targetSiteName"
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
			</div>
			<ErrorMessage class="mt-2" :message="errorMessage" />
		</template>
		<template #actions>
			<Button
				class="w-full"
				label="Create Restore Plan"
				variant="solid"
				theme="blue"
				:loading="$resources.startCreateNewRestore.loading"
				:disabled="!selectedRunLog"
				@click="onCreateClick"
			/>
		</template>
	</Dialog>
</template>
<script>
export default {
	name: 'RestoreFromDamanWizard',
	props: {
		prefilledClient: { type: String, default: null },
		prefilledRunLog: { type: String, default: null },
	},
	data() {
		return {
			show: true,
			selectedClient: this.prefilledClient,
			selectedRunLog: this.prefilledRunLog,
			matchPreview: null,
			targetSiteName: '',
			errorMessage: '',
		};
	},
	mounted() {
		if (this.prefilledClient) this.$resources.runLogs.submit();
		if (this.prefilledRunLog) {
			this.$resources.previewMatch.submit({
				backup_run_log: this.prefilledRunLog,
			});
		}
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
		startCreateNewRestore() {
			return {
				url: 'daman_backup.daman_backup.press_api.start_create_new_restore',
				onSuccess: (data) => {
					this.show = false;
					this.$emit('success', data);
					if (data.restore_plan) {
						window.open(`/app/restore-plan/${data.restore_plan}`, '_blank');
					}
				},
				onError: (err) => {
					this.errorMessage = err.message || 'Create restore failed';
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
		onCreateClick() {
			this.$resources.startCreateNewRestore.submit({
				backup_run_log: this.selectedRunLog,
				target_site_name: this.targetSiteName || null,
			});
		},
	},
};
</script>
