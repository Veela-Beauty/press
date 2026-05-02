<template>
	<div class="space-y-6 p-6">
		<div class="flex items-center justify-between">
			<h1 class="text-xl font-semibold">Restore Tests</h1>
			<Button label="+ New Schedule" variant="solid" theme="blue" @click="openNewScheduleDialog" />
		</div>

		<div>
			<h2 class="mb-3 text-base font-medium text-gray-700">Schedules</h2>
			<div class="rounded border border-gray-200 bg-white">
				<table class="min-w-full text-sm">
					<thead class="bg-gray-50 text-gray-700">
						<tr>
							<th class="px-4 py-2 text-left">Client</th>
							<th class="px-4 py-2 text-left">Frequency</th>
							<th class="px-4 py-2 text-left">Enabled</th>
							<th class="px-4 py-2 text-left">Last Run</th>
							<th class="px-4 py-2 text-left">Last Status</th>
							<th class="px-4 py-2 text-left">Archive After</th>
							<th class="px-4 py-2 text-left"></th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="s in $resources.schedules.data || []"
							:key="s.name"
							class="border-t border-gray-100 hover:bg-gray-50"
						>
							<td class="px-4 py-2">{{ s.client }}</td>
							<td class="px-4 py-2">{{ s.frequency }}</td>
							<td class="px-4 py-2">
								<Badge :theme="s.enabled ? 'green' : 'gray'" :label="s.enabled ? 'On' : 'Off'" />
							</td>
							<td class="px-4 py-2 text-xs text-gray-500">{{ s.last_run_at || '—' }}</td>
							<td class="px-4 py-2">
								<Badge v-if="s.last_run_status" :theme="statusTheme(s.last_run_status)" :label="s.last_run_status" />
								<span v-else>—</span>
							</td>
							<td class="px-4 py-2">{{ s.archive_after_hours }}h</td>
							<td class="px-4 py-2 text-right">
								<Button label="Edit" variant="ghost" size="sm" @click="openEditDialog(s)" />
								<Button label="Delete" variant="ghost" size="sm" theme="red" @click="onDelete(s)" />
							</td>
						</tr>
						<tr v-if="!($resources.schedules.data || []).length">
							<td colspan="7" class="px-4 py-6 text-center text-gray-500">No schedules yet. Click "+ New Schedule" to create the first one.</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<div>
			<h2 class="mb-3 text-base font-medium text-gray-700">Recent Runs</h2>
			<div class="rounded border border-gray-200 bg-white">
				<table class="min-w-full text-sm">
					<thead class="bg-gray-50 text-gray-700">
						<tr>
							<th class="px-4 py-2 text-left">Run</th>
							<th class="px-4 py-2 text-left">Client</th>
							<th class="px-4 py-2 text-left">Triggered</th>
							<th class="px-4 py-2 text-left">Status</th>
							<th class="px-4 py-2 text-left">Target Site</th>
							<th class="px-4 py-2 text-left">RTO</th>
							<th class="px-4 py-2 text-left">Archived</th>
							<th class="px-4 py-2 text-left"></th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="r in $resources.runs.data || []"
							:key="r.name"
							class="border-t border-gray-100 hover:bg-gray-50"
						>
							<td class="cursor-pointer px-4 py-2 font-mono text-xs" @click="openRun(r.name)">{{ r.name }}</td>
							<td class="cursor-pointer px-4 py-2" @click="openRun(r.name)">{{ r.client }}</td>
							<td class="cursor-pointer px-4 py-2 text-xs text-gray-500" @click="openRun(r.name)">{{ r.triggered_at }}</td>
							<td class="cursor-pointer px-4 py-2" @click="openRun(r.name)"><Badge :theme="statusTheme(r.status)" :label="r.status" /></td>
							<td class="cursor-pointer px-4 py-2 font-mono text-xs" @click="openRun(r.name)">{{ r.target_site || '—' }}</td>
							<td class="cursor-pointer px-4 py-2" @click="openRun(r.name)">{{ r.actual_rto_seconds ? `${Math.round(r.actual_rto_seconds / 60)}m` : '—' }}</td>
							<td class="cursor-pointer px-4 py-2 text-xs text-gray-500" @click="openRun(r.name)">{{ r.archived_at || '—' }}</td>
							<td class="px-4 py-2 text-right">
								<Button
									v-if="r.status === 'Passed' && !r.archived_at && r.target_site"
									label="Auto-Drop"
									variant="ghost"
									size="sm"
									theme="amber"
									@click="openAutoDropDialog(r.target_site)"
								/>
							</td>
						</tr>
						<tr v-if="!($resources.runs.data || []).length">
							<td colspan="8" class="px-4 py-6 text-center text-gray-500">No runs yet — schedules execute on the next hourly tick.</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</div>
</template>
<script>
import { defineAsyncComponent, h } from 'vue';
import { renderDialog, confirmDialog } from '../../utils/components';

export default {
	name: 'RestoreTests',
	resources: {
		schedules() { return { url: 'daman_backup.daman_backup.press_api.list_restore_test_schedules', auto: true }; },
		runs() { return { url: 'daman_backup.daman_backup.press_api.list_restore_test_runs', params: () => ({ limit: 50 }), auto: true }; },
		deleteSchedule() {
			return {
				url: 'daman_backup.daman_backup.press_api.delete_restore_test_schedule',
				onSuccess: () => this.$resources.schedules.reload(),
			};
		},
	},
	methods: {
		statusTheme(status) {
			return ({ Passed: 'green', Failed: 'red', Running: 'blue', Skipped: 'gray' })[status] || 'gray';
		},
		openRun(name) { window.open(`/app/restore-test-run/${name}`, '_blank'); },
		openAutoDropDialog(targetSite) {
			// Press's site-name schema appends the root domain. Try both forms
			// (with + without root) so we match what Press has indexed.
			const fullSite = targetSite.includes('.') ? targetSite : `${targetSite}.sandbox.mvpstorm.com`;
			const Dialog = defineAsyncComponent(() => import('../../components/backups/SiteAutoDropDialog.vue'));
			renderDialog(h(Dialog, {
				site: fullSite,
				onScheduled: () => this.$resources.runs.reload(),
				onCancelled: () => this.$resources.runs.reload(),
			}));
		},
		openNewScheduleDialog() {
			const Dialog = defineAsyncComponent(() => import('../../components/backups/RestoreTestScheduleDialog.vue'));
			renderDialog(h(Dialog, { onSaved: () => this.$resources.schedules.reload() }));
		},
		openEditDialog(s) {
			const Dialog = defineAsyncComponent(() => import('../../components/backups/RestoreTestScheduleDialog.vue'));
			renderDialog(h(Dialog, { existing: s, onSaved: () => this.$resources.schedules.reload() }));
		},
		onDelete(s) {
			confirmDialog({
				title: 'Delete schedule',
				message: `Delete the Restore Test Schedule for ${s.client}? Past run history will be preserved.`,
				primaryAction: {
					label: 'Delete',
					theme: 'red',
					onClick: () => this.$resources.deleteSchedule.submit({ name: s.name }),
				},
			});
		},
	},
};
</script>
