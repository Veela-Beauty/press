<template>
	<div class="space-y-4 p-6">
		<div class="flex items-center justify-between">
			<h1 class="text-xl font-semibold">DR Restore</h1>
			<Button label="+ New Restore Test" variant="solid" theme="blue" @click="openWizard" />
		</div>
		<div class="rounded border border-gray-200 bg-white">
			<table class="min-w-full text-sm">
				<thead class="bg-gray-50 text-gray-700">
					<tr>
						<th class="px-4 py-2 text-left">Plan</th>
						<th class="px-4 py-2 text-left">Client</th>
						<th class="px-4 py-2 text-left">Run Log</th>
						<th class="px-4 py-2 text-left">Target Site</th>
						<th class="px-4 py-2 text-left">Tier</th>
						<th class="px-4 py-2 text-left">Status</th>
						<th class="px-4 py-2 text-left">RTO</th>
						<th class="px-4 py-2 text-left">Created</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="p in $resources.plans.data || []"
						:key="p.name"
						class="cursor-pointer border-t border-gray-100 hover:bg-gray-50"
						@click="openPlan(p.name)"
					>
						<td class="px-4 py-2 font-mono text-xs">{{ p.name }}</td>
						<td class="px-4 py-2">{{ p.client }}</td>
						<td class="px-4 py-2 font-mono text-xs">{{ p.backup_run_log }}</td>
						<td class="px-4 py-2 font-mono text-xs">{{ p.target_site_name }}</td>
						<td class="px-4 py-2">{{ p.restore_tier }}</td>
						<td class="px-4 py-2">
							<Badge :theme="statusTheme(p.status)" :label="p.status" />
						</td>
						<td class="px-4 py-2">{{ p.actual_rto_formatted || '—' }}</td>
						<td class="px-4 py-2 text-xs text-gray-500">{{ p.creation }}</td>
					</tr>
					<tr v-if="!($resources.plans.data || []).length">
						<td colspan="8" class="px-4 py-6 text-center text-gray-500">
							No restore plans yet. Click "+ New Restore Test" to create the first one.
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>
<script>
import { defineAsyncComponent, h } from 'vue';
import { renderDialog } from '../../utils/components';

export default {
	name: 'DRRestore',
	resources: {
		plans() {
			return {
				url: 'daman_backup.daman_backup.press_api.list_restore_plans',
				params: () => ({ limit: 50 }),
				auto: true,
			};
		},
	},
	methods: {
		statusTheme(status) {
			const map = {
				Passed: 'green',
				Restoring: 'blue',
				Validating: 'blue',
				Planned: 'gray',
				Draft: 'gray',
				Failed: 'red',
			};
			return map[status] || 'gray';
		},
		openPlan(name) {
			window.open(`/app/restore-plan/${name}`, '_blank');
		},
		openWizard() {
			const Wizard = defineAsyncComponent(
				() =>
					import('../../components/backups/RestoreFromDamanWizard.vue'),
			);
			const dialog = h(Wizard, {
				onSuccess: () => this.$resources.plans.reload(),
			});
			renderDialog(dialog);
		},
	},
};
</script>
