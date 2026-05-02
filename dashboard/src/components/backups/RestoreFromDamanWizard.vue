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
				<T3AutoProvisionPanel
					v-if="isT3 && lastPlanName"
					:restore-plan="lastPlanName"
					:defaults="{ cluster: matchPreview.suggested_cluster, server: matchPreview.suggested_server }"
					@started="onT3Started"
				/>
				<div
					v-if="isT3 && !lastPlanName"
					class="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700"
				>
					Preparing T3 cold provision...
				</div>
				<div
					v-if="isT4"
					class="rounded border border-red-200 bg-red-50 p-3 text-sm"
				>
					<div class="mb-2 font-semibold text-red-800">Apps not in Press App registry:</div>
					<ul class="space-y-2">
						<li v-for="app in t4MissingApps" :key="app.name" class="flex items-center justify-between">
							<span class="font-mono text-xs">{{ app.name }}</span>
							<Button label="+ Register" size="sm" @click="onRegisterApp(app)" />
						</li>
					</ul>
				</div>
				<Button
					v-if="matchPreview"
					label="Refresh tier"
					variant="ghost"
					size="sm"
					@click="onRefreshTier"
				/>
			</div>
			<ErrorMessage class="mt-2" :message="errorMessage" />
		</template>
		<template #actions>
			<Button
				v-if="!isT3"
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
import T3AutoProvisionPanel from './T3AutoProvisionPanel.vue';

export default {
	name: 'RestoreFromDamanWizard',
	components: { T3AutoProvisionPanel },
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
			lastPlanName: null,
		};
	},
	mounted() {
		if (this.prefilledClient) {
			this.$resources.runLogs.submit({ client: this.prefilledClient, limit: 20 });
		}
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
					this.lastPlanName = null;
					if (data && data.tier && data.tier.startsWith('T3')) {
						this.$resources.startCreateNewRestore.submit({
							backup_run_log: this.selectedRunLog,
							target_site_name: this.targetSiteName || null,
						});
					}
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
					if (this.isT3) {
						this.lastPlanName = data.restore_plan;
						return;
					}
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
		isT3() {
			return !!(this.matchPreview && this.matchPreview.tier && this.matchPreview.tier.startsWith('T3'));
		},
		isT4() {
			return !!(this.matchPreview && this.matchPreview.tier && this.matchPreview.tier.startsWith('T4'));
		},
		t4MissingApps() {
			if (!this.matchPreview || !this.matchPreview.reasons) return [];
			const reasonText = this.matchPreview.reasons.find((r) => /not in.*App registry:/i.test(r)) || '';
			const m = reasonText.match(/:\s*(.+)$/);
			if (!m) return [];
			return m[1].split(',').map((s) => s.trim()).filter(Boolean).map((name) => ({ name, branch: 'master' }));
		},
	},
	watch: {
		selectedClient(newVal, oldVal) {
			if (newVal === oldVal) return;
			this.selectedRunLog = null;
			this.matchPreview = null;
			this.lastPlanName = null;
			if (newVal) this.$resources.runLogs.submit({ client: newVal, limit: 20 });
		},
		selectedRunLog(newVal, oldVal) {
			if (newVal === oldVal) return;
			this.matchPreview = null;
			this.lastPlanName = null;
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
		onRefreshTier() {
			if (this.selectedRunLog) {
				this.matchPreview = null;
				this.lastPlanName = null;
				this.$resources.previewMatch.submit({ backup_run_log: this.selectedRunLog });
			}
		},
		onRegisterApp(app) {
			const url = `/dashboard/apps/new?name=${encodeURIComponent(app.name)}&branch=${encodeURIComponent(app.branch)}`;
			window.open(url, '_blank');
		},
		onT3Started(data) {
			this.show = false;
			this.$emit('success', data);
			if (data.restore_plan) {
				window.open(`/app/restore-plan/${data.restore_plan}`, '_blank');
			}
		},
	},
};
</script>
