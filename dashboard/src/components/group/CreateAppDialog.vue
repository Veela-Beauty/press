<template>
	<Dialog
		:options="{ title: 'Create New App', size: 'lg' }"
		v-model="show"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					label="App Name"
					v-model="appName"
					placeholder="my_custom_app"
					description="Lowercase, underscores only. This becomes the Python module name."
					@input="appName = $event.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_')"
				/>
				<FormControl
					label="App Title"
					v-model="appTitle"
					placeholder="My Custom App"
					description="Human-readable title shown in the UI."
				/>
				<FormControl
					label="Description"
					v-model="appDescription"
					placeholder="A brief description of what this app does"
				/>
				<div>
					<label class="block text-xs text-gray-600 mb-1.5">GitHub Account</label>
					<div v-if="loadingOwners" class="text-sm text-gray-500">Loading accounts...</div>
					<div v-else class="flex flex-col gap-2">
						<button
							v-for="owner in githubOwners"
							:key="owner.login"
							class="flex items-center gap-3 rounded-lg border px-3 py-2 text-left text-sm transition-colors"
							:class="githubOwner === owner.login
								? 'border-blue-500 bg-blue-50 text-blue-900'
								: 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'"
							@click="githubOwner = owner.login"
						>
							<img v-if="owner.avatar" :src="owner.avatar" class="h-6 w-6 rounded-full" />
							<div v-else class="flex h-6 w-6 items-center justify-center rounded-full bg-gray-200 text-xs">
								{{ owner.login[0].toUpperCase() }}
							</div>
							<span class="font-medium">{{ owner.login }}</span>
							<Badge size="sm" :label="owner.type" :theme="owner.type === 'User' ? 'blue' : 'green'" />
						</button>
					</div>
					<p class="mt-1.5 text-xs text-gray-500">The repo will be created under this account.</p>
				</div>
			</div>
		</template>
		<template #actions>
			<Button
				variant="solid"
				:loading="creating"
				:disabled="!appName || !appTitle || !githubOwner"
				@click="createApp"
			>
				<template #prefix>
					<lucide-plus class="h-4 w-4" />
				</template>
				Create & Register App
			</Button>
		</template>
	</Dialog>
</template>

<script>
import { createResource } from 'frappe-ui';
import { toast } from 'vue-sonner';

export default {
	name: 'CreateAppDialog',
	props: ['group'],
	emits: ['success'],
	data() {
		return {
			show: true,
			creating: false,
			loadingOwners: true,
			appName: '',
			appTitle: '',
			appDescription: '',
			githubOwner: '',
			githubOwners: [],
		};
	},
	mounted() {
		createResource({
			url: 'press.api.create_app.get_github_owners',
		})
			.fetch()
			.then((owners) => {
				this.githubOwners = owners;
				if (owners.length) this.githubOwner = owners[0].login;
				this.loadingOwners = false;
			})
			.catch(() => {
				this.loadingOwners = false;
				toast.error('Failed to load GitHub accounts');
			});
	},
	methods: {
		createApp() {
			this.creating = true;
			createResource({
				url: 'press.api.create_app.create_app',
				params: {
					app_name: this.appName,
					app_title: this.appTitle,
					github_owner: this.githubOwner,
					description: this.appDescription,
					bench_group: this.group?.name || '',
				},
			})
				.fetch()
				.then((result) => {
					this.creating = false;
					this.show = false;
					toast.success(`App "${this.appTitle}" created and registered`);
					this.$emit('success', result);
				})
				.catch((err) => {
					this.creating = false;
					toast.error(err.messages?.[0] || 'Failed to create app');
				});
		},
	},
};
</script>
