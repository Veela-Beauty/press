<template>
	<div class="mx-auto max-w-3xl space-y-4">
		<!-- Developer Mode -->
		<div class="divide-y rounded border border-gray-200 p-5">
			<div class="pb-3 text-lg font-semibold">Developer Mode</div>

			<div class="py-3">
				<div class="flex items-center justify-between gap-1">
					<div>
						<h3 class="text-base font-medium">
							{{
								$site?.doc?.is_development_site
									? 'Developer Mode Enabled'
									: 'Enable Developer Mode'
							}}
						</h3>
						<p class="mt-1 text-p-base text-gray-600">
							{{
								$site?.doc?.is_development_site
									? 'This site is in developer mode. Frappe developer tools and debug features are active.'
									: 'Mark this site as a development site and enable developer_mode in site config.'
							}}
						</p>
					</div>
					<Button
						class="whitespace-nowrap"
						:loading="devModeLoading"
						:variant="$site?.doc?.is_development_site ? 'outline' : 'solid'"
						@click="toggleDevMode"
					>
						<p
							:class="
								$site?.doc?.is_development_site ? 'text-red-600' : 'text-gray-800'
							"
						>
							{{
								$site?.doc?.is_development_site
									? 'Disable Dev Mode'
									: 'Enable Dev Mode'
							}}
						</p>
					</Button>
				</div>
			</div>

			<!-- Info panel when dev mode is active -->
			<div v-if="$site?.doc?.is_development_site" class="py-3">
				<div
					class="rounded bg-blue-50 px-4 py-3 text-sm text-blue-800"
				>
					<p class="font-medium">Dev mode is active on this site:</p>
					<ul class="mt-1 list-inside list-disc space-y-1">
						<li><code class="font-mono">developer_mode = 1</code> is set in site config</li>
						<li>Frappe debug bar and hot-reload are available</li>
						<li>Disable before moving to production</li>
					</ul>
				</div>
			</div>
		</div>
	</div>
</template>

<script>
import { getCachedDocumentResource } from 'frappe-ui';
import { toast } from 'vue-sonner';

export default {
	name: 'SiteDevTab',
	props: {
		site: { type: String, required: true },
	},
	data() {
		return {
			devModeLoading: false,
		};
	},
	computed: {
		$site() {
			return getCachedDocumentResource('Site', this.site);
		},
	},
	methods: {
		async toggleDevMode() {
			const enabling = !this.$site?.doc?.is_development_site;
			this.devModeLoading = true;
			try {
				await this.$site.setDevelopmentMode.submit({ enable: enabling ? 1 : 0 });
				toast.success(
					enabling ? 'Developer mode enabled' : 'Developer mode disabled',
				);
				this.$site.reload();
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed');
			} finally {
				this.devModeLoading = false;
			}
		},
	},
};
</script>
