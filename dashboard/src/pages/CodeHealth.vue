<template>
	<div class="mx-auto max-w-7xl p-6">
		<div class="mb-4 flex items-center justify-between">
			<h1 class="text-xl font-bold text-gray-900 dark:text-white">Code Health</h1>
			<div v-if="!benchName" class="text-sm text-gray-500">Select a bench to scan</div>
		</div>

		<!-- Bench selector (if no bench in query) -->
		<div v-if="!benchName" class="rounded-lg border border-gray-200 bg-white p-6 text-center dark:border-gray-700 dark:bg-gray-900">
			<p class="text-gray-500">Open this page from a Site's Dev tab to auto-select a bench, or pass <code>?bench=BENCH_NAME</code> in the URL.</p>
		</div>

		<!-- Code Health dashboard -->
		<BenchCodeHealth v-if="benchName" :bench-name="benchName" />
	</div>
</template>

<script>
import BenchCodeHealth from '../components/BenchCodeHealth.vue';

export default {
	name: 'CodeHealth',
	components: { BenchCodeHealth },
	computed: {
		benchName() {
			return this.$route?.query?.bench || '';
		},
	},
};
</script>
