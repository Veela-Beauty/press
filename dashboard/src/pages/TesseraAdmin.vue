<template>
	<div class="mx-auto max-w-7xl p-4">
		<div class="mb-4 flex items-center justify-between">
			<h1 class="text-xl font-bold text-gray-900">Tessera License Manager</h1>
		</div>

		<!-- TAB: Overview (default) -->
		<template v-if="activeMainTab === 'overview'">
			<TesseraOverview />
		</template>

		<!-- TAB: Licenses -->
		<template v-if="activeMainTab === 'licenses'">
			<TesseraLicenses />
		</template>

		<!-- TAB: Seats -->
		<template v-if="activeMainTab === 'seats'">
			<TesseraSeats />
		</template>

		<!-- TAB: Heartbeat -->
		<template v-if="activeMainTab === 'heartbeat'">
			<TesseraHeartbeat />
		</template>

		<!-- TAB: Offline -->
		<template v-if="activeMainTab === 'offline'">
			<TesseraOffline />
		</template>
	</div>
</template>

<script>
import TesseraOverview from '../components/tessera/TesseraOverview.vue';
import TesseraLicenses from '../components/tessera/TesseraLicenses.vue';
import TesseraSeats from '../components/tessera/TesseraSeats.vue';
import TesseraHeartbeat from '../components/tessera/TesseraHeartbeat.vue';
import TesseraOffline from '../components/tessera/TesseraOffline.vue';
import { TAB_STRIP_BASE, tabClass } from '../components/_shared/tabClasses.js';

export default {
	name: 'TesseraAdmin',
	components: { TesseraOverview, TesseraLicenses, TesseraSeats, TesseraHeartbeat, TesseraOffline },
	setup() {
		// Expose shared tab constants to the template.
		return { TAB_STRIP_BASE, tabClass };
	},
	data() {
		return {
			activeMainTab: 'overview',
			mainTabs: [
				{ id: 'overview', label: 'Overview', icon: 'fa fa-tachometer' },
				{ id: 'licenses', label: 'Licenses', icon: 'fa fa-key' },
				{ id: 'seats', label: 'Seats', icon: 'fa fa-users' },
				{ id: 'heartbeat', label: 'Heartbeat', icon: 'fa fa-heartbeat' },
				{ id: 'offline', label: 'Offline', icon: 'fa fa-download' },
			],
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
	methods: {
		goTab(id) {
			this.activeMainTab = id;
			if (this.$route.params.tab !== id) {
				this.$router.replace('/tessera/' + id).catch(() => {});
			}
		},
	},
};
</script>
