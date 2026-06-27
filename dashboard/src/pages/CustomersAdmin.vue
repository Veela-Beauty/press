<template>
	<div class="mx-auto max-w-7xl p-4">
		<div class="mb-4 flex items-center justify-between">
			<h1 class="text-xl font-bold text-gray-900">Customers</h1>
		</div>

		<template v-if="activeMainTab === 'overview'">
			<CustomersOverview />
		</template>
		<template v-if="activeMainTab === 'accounts'">
			<CustomersAccounts />
		</template>
	</div>
</template>

<script>
import CustomersOverview from '../components/customers/CustomersOverview.vue';
import CustomersAccounts from '../components/customers/CustomersAccounts.vue';

export default {
	name: 'CustomersAdmin',
	components: { CustomersOverview, CustomersAccounts },
	data() {
		return {
			activeMainTab: 'overview',
		};
	},
	mounted() {
		this.activeMainTab = this.$route.params.tab || 'overview';
	},
	watch: {
		'$route.params.tab'(v) {
			if (v && v !== this.activeMainTab) this.activeMainTab = v;
		},
	},
};
</script>
