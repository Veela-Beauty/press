<template>
	<!-- PRS-SP-17 Logins and sharing: share login + Administrator login, each behind a 6-digit code (10 minutes), every
	     action in Site Activity. Prototype: ~/docs/prototypes/press-site-logins/index.html -->
	<div v-if="data" class="rounded-md border">
		<div class="flex min-h-12 flex-wrap items-center justify-between gap-2 border-b px-5 py-2">
			<h2 class="text-lg font-medium text-gray-900">Logins and sharing</h2>
			<div class="flex items-center gap-2">
				<span v-if="unlocked" class="rounded bg-green-50 px-2 py-0.5 text-sm text-green-700">Verified for 10 min</span>
				<Button v-if="data.share_user" variant="solid" :loading="busy === 'message'" @click="copyMessage">
					<template #prefix><lucide-copy class="h-4 w-4" /></template>
					Copy share message
				</Button>
				<Dropdown v-if="data.share_user && data.admin_visible" :options="[{ label: 'Reset share password', onClick: reset }]">
					<Button aria-label="More actions"><lucide-more-horizontal class="h-4 w-4" /></Button>
				</Dropdown>
			</div>
		</div>

		<div class="grid grid-cols-1" :class="{ 'lg:grid-cols-2 lg:gap-x-5': data.admin_visible }">
			<section class="py-2">
				<h3 class="px-5 py-2 text-base font-medium text-gray-700">Share login</h3>
				<template v-if="data.share_user">
					<div class="flex items-center px-5 py-2">
						<div class="w-1/3 text-base text-gray-600">User</div>
						<div class="w-2/3 break-all font-mono text-sm text-gray-900">{{ data.share_user }}</div>
					</div>
					<div class="flex items-center px-5 py-1">
						<div class="w-1/3 text-base text-gray-600">Password</div>
						<div class="flex w-2/3 items-center gap-2">
							<span class="break-all font-mono text-sm text-gray-900">{{ revealed.share || '••••••••••••' }}</span>
							<Button :aria-label="revealed.share ? 'Hide share password' : 'Show share password'" @click="toggle('share')">
								<lucide-eye-off v-if="revealed.share" class="h-4 w-4" /><lucide-eye v-else class="h-4 w-4" />
							</Button>
							<Button aria-label="Copy share password" @click="copy('share')"><lucide-copy class="h-4 w-4" /></Button>
						</div>
					</div>
					<div class="flex items-center px-5 py-2">
						<div class="w-1/3 text-base text-gray-600">Role on site</div>
						<div class="w-2/3 text-base text-gray-900">{{ data.role_profile || '-' }}</div>
					</div>
				</template>
				<div v-else class="flex flex-wrap items-center gap-3 px-5 pb-4 pt-1">
					<span class="text-base text-gray-600">No share user yet.</span>
					<Button v-if="data.admin_visible" variant="solid" @click="create">Create share user</Button>
					<span v-else class="text-base text-gray-600">Ask a team admin to create one.</span>
				</div>
			</section>

			<section v-if="data.admin_visible" class="border-t py-2 lg:border-t-0">
				<h3 class="px-5 py-2 text-base font-medium text-gray-700">Administrator</h3>
				<p v-if="data.confidential" class="mx-5 my-1 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-base text-amber-800">
					Confidential site: the password is not shown. Use Login as Administrator with your PIN.
				</p>
				<template v-else>
					<div class="flex items-center px-5 py-2">
						<div class="w-1/3 text-base text-gray-600">User</div>
						<div class="w-2/3 font-mono text-sm text-gray-900">Administrator</div>
					</div>
					<div class="flex items-center px-5 py-1">
						<div class="w-1/3 text-base text-gray-600">Password</div>
						<div class="flex w-2/3 items-center gap-2">
							<span class="break-all font-mono text-sm text-gray-900">{{ revealed.admin || '••••••••••••' }}</span>
							<Button :aria-label="revealed.admin ? 'Hide Administrator password' : 'Show Administrator password'" @click="toggle('admin')">
								<lucide-eye-off v-if="revealed.admin" class="h-4 w-4" /><lucide-eye v-else class="h-4 w-4" />
							</Button>
							<Button aria-label="Copy Administrator password" @click="copy('admin')"><lucide-copy class="h-4 w-4" /></Button>
						</div>
					</div>
				</template>
			</section>
		</div>

		<div class="flex items-center justify-between border-t px-5 pb-1 pt-3">
			<h3 class="text-base font-medium text-gray-700">Access history</h3>
			<router-link :to="`/sites/${site}/activity`" class="text-base text-blue-600 hover:underline">View all in Activity</router-link>
		</div>
		<div class="pb-3">
			<div v-for="(h, i) in data.history" :key="i" class="flex items-center px-5 py-2">
				<div class="w-1/3 text-base text-gray-600">{{ $format.date(h.when, 'D MMM, HH:mm') }}</div>
				<div class="w-2/3 text-base text-gray-900">{{ h.who }} {{ h.what }}</div>
			</div>
			<p v-if="!data.history.length" class="px-5 py-2 text-base text-gray-600">No one has opened these logins yet.</p>
		</div>

		<SiteLoginsCodeDialog
			v-model="codeDialog"
			:site="site"
			:hasApp="data.has_app"
			@verified="onVerified"
			@linked="data.has_app = true"
		/>
		<Dialog v-model="createDialog" :options="{ title: 'Create share user', actions: createActions }">
			<template #body-content>
				<FormControl
					v-model="roleProfile"
					type="select"
					label="Role profile on the site"
					:options="$resources.roleProfiles.data || []"
				/>
				<ErrorMessage class="mt-2" :message="$resources.createUser.error || $resources.roleProfiles.error" />
			</template>
		</Dialog>
	</div>
</template>

<script>
import { toast } from 'vue-sonner';
import { confirmDialog } from '../../utils/components';
import SiteLoginsCodeDialog from './SiteLoginsCodeDialog.vue';

const UNLOCK_MS = 10 * 60 * 1000;

export default {
	name: 'SiteLogins',
	props: { site: { type: String, required: true } },
	components: { SiteLoginsCodeDialog },
	data() {
		return { revealed: { share: '', admin: '' }, unlockedUntil: 0, now: Date.now(), pending: null, codeDialog: false, createDialog: false, roleProfile: '', busy: '' };
	},
	computed: {
		data() {
			return this.$resources.logins.data;
		},
		unlocked() {
			return this.now < this.unlockedUntil;
		},
		createActions() {
			return [
				{ label: 'Cancel', variant: 'outline', onClick: () => (this.createDialog = false) },
				{ label: 'Create', variant: 'solid', loading: this.$resources.createUser.loading, onClick: this.createUser },
			];
		},
	},
	mounted() {
		this.timer = setInterval(() => (this.now = Date.now()), 15000);
	},
	beforeUnmount() {
		clearInterval(this.timer);
	},
	methods: {
		guard(fn) {
			this.now = Date.now();
			if (this.unlocked) return fn();
			this.pending = fn;
			this.codeDialog = true;
		},
		onVerified() {
			this.unlockedUntil = Date.now() + UNLOCK_MS;
			this.now = Date.now();
			const fn = this.pending;
			this.pending = null;
			if (fn) fn();
		},
		async secret(which, purpose) {
			try {
				const out = await this.$resources.secret.submit({ name: this.site, which, purpose });
				this.$resources.logins.reload();
				return out;
			} catch (e) {
				if (e.exc_type === 'PermissionError') this.unlockedUntil = 0;
				toast.error(e.messages?.join(' ') || e.message);
				return null;
			}
		},
		toggle(which) {
			if (this.revealed[which]) {
				this.revealed[which] = '';
				return;
			}
			this.guard(async () => {
				const out = await this.secret(which, 'show');
				if (out) this.revealed[which] = out.password;
			});
		},
		copy(which) {
			this.guard(async () => {
				const out = await this.secret(which, 'copy');
				if (out) this.toClipboard(out.password, 'Password copied');
			});
		},
		copyMessage() {
			this.guard(async () => {
				this.busy = 'message';
				const out = await this.secret('share', 'message');
				this.busy = '';
				if (out) {
					const text = `${this.site}\nOpen: https://${this.site}/login\nUser: ${out.user}\nPassword: ${out.password}`;
					this.toClipboard(text, 'Share message copied');
				}
			});
		},
		async toClipboard(text, message) {
			await navigator.clipboard.writeText(text);
			toast.success(message);
		},
		create() {
			this.guard(() => {
				this.createDialog = true;
				this.$resources.roleProfiles.fetch();
			});
		},
		async createUser() {
			if (!this.roleProfile) return;
			await this.$resources.createUser.submit({ name: this.site, role_profile: this.roleProfile });
			this.createDialog = false;
			this.$resources.logins.reload();
			toast.success('Share user created');
		},
		reset() {
			this.guard(() =>
				confirmDialog({
					title: 'Reset share password?',
					message: 'The current share password stops working. Send the new share message to the people who use it.',
					primaryAction: {
						label: 'Reset password',
						variant: 'solid',
						theme: 'red',
						onClick: async ({ hide }) => {
							await this.$resources.resetPassword.submit({ name: this.site });
							this.revealed.share = '';
							this.$resources.logins.reload();
							hide();
							toast.success('New share password set');
						},
					},
				}),
			);
		},
	},
	resources: {
		logins() {
			return {
				url: 'press.api.site_logins.get_logins',
				params: { name: this.site },
				auto: true,
				onSuccess(d) {
					if (d.unlocked_seconds > 0) this.unlockedUntil = Date.now() + d.unlocked_seconds * 1000;
				},
			};
		},
		secret() {
			return { url: 'press.api.site_logins.get_secret' };
		},
		roleProfiles() {
			return { url: 'press.api.site_logins.role_profiles', params: { name: this.site } };
		},
		createUser() {
			return { url: 'press.api.site_logins.create_share_user' };
		},
		resetPassword() {
			return { url: 'press.api.site_logins.reset_share_password' };
		},
	},
};
</script>
