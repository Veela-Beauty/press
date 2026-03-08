<template>
	<!-- Rebrand: Accurate Systems branded SaaS login -->
	<div class="login-page-bg relative flex min-h-full items-center justify-center">
		<div class="relative z-10 w-full max-w-[420px] px-4 py-8 sm:py-16">
			<div
				class="login-card rounded-xl bg-white p-8 shadow-lg sm:p-10"
				@dblclick="redirectForFrappeioAuth"
			>
				<!-- Logo area -->
				<div class="mb-7 flex flex-col items-center">
					<img
						v-if="logo"
						class="inline-block h-14 w-14 rounded-md"
						:src="logo"
					/>
					<FCLogo v-else class="inline-block h-14 w-14" />
					<h1 class="mt-3 text-lg font-bold text-gray-900">
						Accurate Systems
					</h1>
					<p class="mt-1 text-sm text-gray-500">
						Cloud Hosting Solutions
					</p>
				</div>
				<!-- Title & Subtitle -->
				<div class="mb-7.5 text-center">
					<p class="mb-2 text-2xl font-semibold leading-6 text-gray-900">
						{{ title }}
					</p>
					<p
						class="break-words text-base font-normal leading-[21px] text-gray-700"
						v-if="subtitle"
					>
						<template
							v-if="typeof subtitle === 'object'"
							v-for="line in subtitle"
						>
							{{ line }}<br />
						</template>
						<template v-else>{{ subtitle }}</template>
					</p>
				</div>
				<slot></slot>
			</div>

			<!-- Footer -->
			<div class="mt-6 text-center text-xs text-gray-400">
				accuratesystems.com.sa
			</div>
		</div>
	</div>
</template>

<script>
import FCLogo from '@/components/icons/FCLogo.vue';
import { notify } from '@/utils/toast';

export default {
	name: 'SaaSLoginBox',
	props: ['title', 'subtitle', 'logo'],
	components: {
		FCLogo,
	},
	mounted() {
		const params = new URLSearchParams(window.location.search);

		if (params.get('showRemoteLoginError')) {
			notify({
				title: 'Token Invalid or Expired',
				color: 'red',
				icon: 'x',
			});
		}
	},
	methods: {
		redirectForFrappeioAuth() {
			window.location = '/f-login';
		},
	},
};
</script>

<style scoped>
/* Rebrand: Accurate Systems gradient background */
.login-page-bg {
	min-height: 100vh;
	background: linear-gradient(135deg, #F0F5FA 0%, #E0EDFA 50%, #D4E6F9 100%);
}
.login-card {
	box-shadow: 0 10px 25px rgba(4, 107, 210, 0.12),
		0 4px 10px rgba(0, 0, 0, 0.06);
}
</style>
