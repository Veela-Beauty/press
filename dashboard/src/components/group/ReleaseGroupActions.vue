<template>
	<div class="mx-auto max-w-3xl space-y-4">
		<!-- Dev Actions — benches in this release group -->
		<div
			v-if="benches.data?.length"
			class="divide-y rounded border border-gray-200 p-5"
		>
			<div class="pb-3 text-lg font-semibold">Dev Actions</div>
			<div
				class="py-3 first:pt-0 last:pb-0"
				v-for="bench in benches.data"
				:key="bench.name"
			>
				<div class="flex items-center justify-between gap-1">
					<div>
						<h3 class="text-base font-medium">{{ bench.name }}</h3>
						<p class="mt-1 text-p-base text-gray-600">
							{{
								bench.is_development_bench
									? 'This bench is marked as a development bench'
									: 'Mark this bench for development use only'
							}}
						</p>
					</div>
					<Button
						class="whitespace-nowrap"
						:loading="devLoading[bench.name]"
						@click="toggleDevBench(bench)"
					>
						<p>{{ bench.is_development_bench ? 'Unset Dev Bench' : 'Mark Dev Bench' }}</p>
					</Button>
				</div>
			</div>
		</div>

		<!-- Standard actions from Release Group doc.actions child table -->
		<div
			v-if="$releaseGroup?.doc?.actions"
			v-for="group in actions"
			:key="group.group"
			class="divide-y rounded border border-gray-200 p-5"
		>
			<div class="pb-3 text-lg font-semibold">{{ group.group }}</div>
			<div
				class="py-3 first:pt-0 last:pb-0"
				v-for="row in group.actions"
				:key="row.action"
			>
				<ReleaseGroupActionCell
					:benchName="releaseGroup"
					:group="group.group"
					:actionLabel="row.action"
					:method="row.doc_method"
					:description="row.description"
					:buttonLabel="row.button_label"
					:linkedVersionUpgrade="$releaseGroup?.doc?.linked_version_upgrade"
				/>
			</div>
		</div>
	</div>
</template>

<script>
import { call, createListResource, getCachedDocumentResource } from 'frappe-ui';
import { toast } from 'vue-sonner';
import ReleaseGroupActionCell from './ReleaseGroupActionCell.vue';

export default {
	props: ['releaseGroup'],
	components: { ReleaseGroupActionCell },
	data() {
		return {
			devLoading: {},
			benches: createListResource({
				doctype: 'Bench',
				fields: ['name', 'status', 'is_development_bench'],
				filters: { group: this.releaseGroup, status: ['not in', ['Archived']] },
				orderBy: 'creation desc',
				auto: true,
			}),
		};
	},
	computed: {
		$releaseGroup() {
			return getCachedDocumentResource('Release Group', this.releaseGroup);
		},
		actions() {
			const groupedActions = this.$releaseGroup.doc.actions.reduce(
				(acc, action) => {
					const group = action.group || 'General Actions';
					if (!acc[group]) acc[group] = [];
					acc[group].push(action);
					return acc;
				},
				{},
			);
			return Object.keys(groupedActions).map((group) => ({
				group,
				actions: groupedActions[group],
			}));
		},
	},
	methods: {
		async toggleDevBench(bench) {
			const enabling = !bench.is_development_bench;
			this.devLoading = { ...this.devLoading, [bench.name]: true };
			try {
				await call('press.api.client.run_doc_method', {
					dt: 'Bench',
					dn: bench.name,
					method: 'set_development_bench',
					args: JSON.stringify({ enable: enabling ? 1 : 0 }),
				});
				toast.success(
					enabling
						? `${bench.name} marked as development bench`
						: `${bench.name} unset from development bench`,
				);
				this.benches.reload();
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to update bench');
			} finally {
				this.devLoading = { ...this.devLoading, [bench.name]: false };
			}
		},
	},
};
</script>
