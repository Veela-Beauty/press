<template>
	<div class="rounded border border-amber-200 bg-amber-50 p-3 text-sm">
		<div class="mb-2 font-semibold text-amber-800">T3 Cold Provision — no matching bench</div>
		<div class="mb-3 text-amber-700">
			No existing bench has all the source apps. We can build a new bench
			automatically. Estimated total RTO: <b>~60-90 min</b> (build ~30-60 min +
			restore ~12-15 min). You'll be emailed when restore completes.
		</div>
		<div class="mb-3 text-amber-800">
			Auto-picked target: <b>{{ defaults.cluster || '—' }}</b> /
			<b>{{ defaults.server || '—' }}</b>
			<a href="#" class="ml-2 text-blue-600 hover:underline" @click.prevent="overrideMode = !overrideMode">
				{{ overrideMode ? 'Cancel override' : 'Override' }}
			</a>
		</div>
		<div v-if="overrideMode" class="mb-3 space-y-2">
			<FormControl label="Cluster" v-model="overrideCluster" />
			<FormControl label="Server" v-model="overrideServer" />
		</div>
		<Button
			label="Auto-provision and restore"
			variant="solid"
			theme="amber"
			:loading="$resources.startT3.loading"
			@click="onProvision"
		/>
		<ErrorMessage class="mt-2" :message="errorMessage" />
	</div>
</template>
<script>
export default {
	name: 'T3AutoProvisionPanel',
	props: {
		restorePlan: { type: String, required: true },
		defaults: { type: Object, default: () => ({ cluster: null, server: null }) },
	},
	data() {
		return {
			overrideMode: false,
			overrideCluster: '',
			overrideServer: '',
			errorMessage: '',
		};
	},
	resources: {
		startT3() {
			return {
				url: 'daman_backup.daman_backup.press_api.start_t3_provision_and_restore',
				onSuccess: (data) => this.$emit('started', data),
				onError: (err) => { this.errorMessage = err.message || 'Provision failed'; },
			};
		},
	},
	methods: {
		onProvision() {
			this.$resources.startT3.submit({
				restore_plan: this.restorePlan,
				cluster: this.overrideMode ? this.overrideCluster : null,
				server: this.overrideMode ? this.overrideServer : null,
			});
		},
	},
};
</script>
