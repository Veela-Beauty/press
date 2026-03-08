<template>
	<!-- Rebrand: Accurate Systems branded login page -->
	<div class="login-page-bg relative flex min-h-full items-center justify-center">
		<!-- Decorative circles matching prototype -->
		<div class="login-circle-1"></div>
		<div class="login-circle-2"></div>

		<div class="relative z-10 w-full max-w-[480px] px-4 py-8 sm:py-16">
			<div
				class="login-card rounded-xl bg-white p-8 shadow-lg sm:p-10"
				@dblclick="redirectForFrappeioAuth"
			>
				<!-- Logo area -->
				<div class="mb-7 text-center">
					<slot name="logo">
						<FCLogo class="mx-auto inline-block h-14 w-14" />
						<h1 class="mt-3 text-lg font-bold text-gray-900">
							Accurate Systems
						</h1>
						<p class="mt-1 text-sm text-gray-500">
							Cloud Hosting Solutions
						</p>
					</slot>
				</div>

				<!-- Title & Subtitle -->
				<div class="mb-2" v-if="title">
					<span
						class="text-2xl font-bold leading-5 tracking-tight text-gray-900"
					>
						{{ title }}
					</span>
				</div>
				<p
					class="mb-6 break-words text-base font-normal leading-[21px] text-gray-700"
					v-if="subtitle"
				>
					{{ subtitle }}
				</p>

				<!-- Form slot -->
				<slot></slot>
			</div>

			<!-- Footer -->
			<div class="mt-6 text-center text-xs text-gray-400">
				accuratesystems.com.sa
			</div>
			<slot name="footer"></slot>
		</div>
	</div>
</template>

<script>
import { toast } from 'vue-sonner';
import FCLogo from '@/components/icons/FCLogo.vue';

export default {
	name: 'LoginBox',
	props: ['title', 'logo', 'subtitle'],
	components: {
		FCLogo,
	},
	mounted() {
		const params = new URLSearchParams(window.location.search);

		if (params.get('showRemoteLoginError')) {
			toast.error('Token Invalid or Expired');
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
/* Rebrand: Accurate Systems gradient background with decorative elements */
.login-page-bg {
	min-height: 100vh;
	background: linear-gradient(135deg, #F0F5FA 0%, #E0EDFA 50%, #D4E6F9 100%);
	position: relative;
	overflow: hidden;
}
.login-card {
	box-shadow: 0 10px 25px rgba(4, 107, 210, 0.12),
		0 4px 10px rgba(0, 0, 0, 0.06);
}
.login-circle-1 {
	position: absolute;
	top: -200px;
	right: -200px;
	width: 500px;
	height: 500px;
	border-radius: 50%;
	background: radial-gradient(circle, rgba(4,107,210,0.08) 0%, transparent 70%);
	pointer-events: none;
}
.login-circle-2 {
	position: absolute;
	bottom: -150px;
	left: -150px;
	width: 400px;
	height: 400px;
	border-radius: 50%;
	background: radial-gradient(circle, rgba(4,107,210,0.06) 0%, transparent 70%);
	pointer-events: none;
}
</style>
