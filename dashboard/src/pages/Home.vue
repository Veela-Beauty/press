<template>
	<div class="sticky top-0 z-10 shrink-0">
		<Header>
			<Breadcrumbs :items="[{ label: 'Home', route: { name: 'Home' } }]" />
			<Dropdown
				:options="[
					{ label: 'Site', handler: () => showBenchPicker = true },
					{ label: 'Bench', route: { name: 'New Release Group' } },
				]"
			>
				<Button
					variant="solid"
					label="Create new"
					:disabled="!$team.doc?.payment_mode"
				>
					<template #suffix>
						<lucide-chevron-down class="h-4 w-4 text-gray-300" />
					</template>
				</Button>
			</Dropdown>
		</Header>
	</div>
	<div class="p-5" v-if="$team?.doc">
		<Onboarding v-if="!$team.doc?.onboarding.complete" />
		<HomeSummary v-else />
	</div>

	<Dialog
		v-model="showBenchPicker"
		:options="{ title: 'Create New Site', size: 'lg' }"
	>
		<template #body-content>
			<p class="text-sm text-gray-600 mb-4">
				Choose an existing bench to add a site, or create a new bench first.
			</p>
			<div v-if="benchesLoading" class="py-8 text-center text-gray-500">
				Loading benches...
			</div>
			<div v-else-if="activeBenches.length" class="space-y-2 overflow-y-auto" style="max-height: 400px">
				<button
					v-for="b in activeBenches"
					:key="b.name"
					@click="goToBenchNewSite(b.name)"
					class="w-full flex items-center justify-between rounded-lg border border-gray-200 p-4 text-left hover:border-gray-900 hover:bg-gray-50 transition-colors cursor-pointer"
				>
					<div>
						<div class="text-sm font-medium text-gray-900">{{ b.title }}</div>
						<div class="text-xs text-gray-500 mt-1">
							{{ b.version }}
						</div>
					</div>
					<lucide-chevron-right class="h-4 w-4 text-gray-400" />
				</button>
			</div>
			<div v-else class="py-8 text-center text-gray-500">
				No active benches found. Create a bench first.
			</div>
			<div class="mt-4 pt-4 border-t border-gray-100">
				<router-link
					:to="{ name: 'New Site' }"
					class="text-sm text-blue-600 hover:text-blue-800 font-medium"
					@click="showBenchPicker = false"
				>
					Or create a new bench + site
				</router-link>
			</div>
		</template>
	</Dialog>
</template>

<script>
import { defineAsyncComponent } from 'vue';
import Header from '../components/Header.vue';
import HomeSummary from '../components/HomeSummary.vue';

export default {
	name: 'Home',
	components: {
		Header,
		HomeSummary,
		Onboarding: defineAsyncComponent(
			() => import('../components/Onboarding.vue'),
		),
	},
	data() {
		return {
			showBenchPicker: false,
			benchesLoading: false,
			benchesList: [],
		};
	},
	computed: {
		activeBenches() {
			return this.benchesList.filter(function(b) { return b.status === 'Active'; });
		},
	},
	watch: {
		showBenchPicker(val) {
			if (val && !this.benchesList.length) {
				this.fetchBenches();
			}
		},
	},
	methods: {
		fetchBenches() {
			this.benchesLoading = true;
			var self = this;
			fetch('/api/method/press.api.client.get_list', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'X-Frappe-CSRF-Token': window.csrf_token || '',
				},
				body: JSON.stringify({
					doctype: 'Release Group',
					fields: ['name', 'title', 'version', 'status', 'creation'],
					filters: { enabled: 1 },
					order_by: 'creation desc',
					limit: 50,
				}),
			})
				.then(function(r) { return r.json(); })
				.then(function(data) {
					self.benchesList = data.message || [];
					self.benchesLoading = false;
				})
				.catch(function() {
					self.benchesLoading = false;
				});
		},
		goToBenchNewSite(benchName) {
			this.showBenchPicker = false;
			this.$router.push({
				name: 'Release Group New Site',
				params: { bench: benchName },
			});
		},
	},
};
</script>
