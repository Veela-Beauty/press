<template>
	<Dialog :options="{ title: 'Issue License', size: '2xl' }" v-model="show">
		<template #body-content>
			<div class="space-y-3">
				<div class="grid grid-cols-2 gap-3">
					<FormControl label="Customer" v-model="form.customer" placeholder="Acme Industrial" />
					<FormControl label="Site URL (node-lock)" v-model="form.site_url" placeholder="acme.erp.local" />
				</div>
				<div class="grid grid-cols-2 gap-3">
					<FormControl
						label="App"
						type="select"
						v-model="form.app"
						:options="[
							{ label: 'tamkeen', value: 'tamkeen' },
							{ label: 'daman', value: 'daman' },
							{ label: '(other)', value: '' },
						]"
					/>
					<FormControl label="Company (blank = site-wide)" v-model="form.company" placeholder="Acme Industrial" />
				</div>
				<div class="grid grid-cols-2 gap-3">
					<FormControl
						label="Tier"
						type="select"
						v-model="form.tier"
						:options="[
							{ label: 'Trial', value: 'Trial' },
							{ label: 'Basic', value: 'Basic' },
							{ label: 'Pro', value: 'Pro' },
							{ label: 'Enterprise', value: 'Enterprise' },
						]"
					/>
					<FormControl label="Expires on" type="date" v-model="form.expires_on" />
				</div>

				<div>
					<p class="mb-1.5 text-xs font-medium text-gray-600">Features</p>
					<div class="flex flex-wrap gap-4">
						<label v-for="k in FEATURE_KEYS" :key="k" class="flex items-center gap-1.5 text-sm text-gray-700">
							<input type="checkbox" v-model="form.features[k]" class="rounded border-gray-300" />
							{{ k }}
						</label>
					</div>
				</div>

				<div class="grid grid-cols-2 gap-3">
					<FormControl label="Seats (cap)" type="number" v-model="form.seats" />
					<FormControl label="Grace days" type="number" v-model="form.grace_days" />
				</div>

				<FormControl
					label="Licensed users (named allowlist, one email per line)"
					type="textarea"
					v-model="form.licensed_users"
					placeholder="ahmed@acme.com"
				/>
				<p class="text-xs text-gray-400">We own this list; clients request changes via the Seats tab.</p>

				<p v-if="error" class="text-xs text-red-500">{{ error }}</p>
			</div>
		</template>
		<template #actions>
			<div class="flex items-center justify-between">
				<span class="text-xs text-gray-400">Token will be Ed25519-signed and node-locked to the site URL.</span>
				<Button variant="solid" :loading="saving" @click="submit">Issue &amp; generate key</Button>
			</div>
		</template>
	</Dialog>
</template>

<script>
import { Dialog, FormControl, Button } from 'frappe-ui';
import { toast } from 'vue-sonner';
import { issueLicense } from './tesseraApi.js';

const FEATURE_KEYS = ['business_flow_guide', 'watch_tower', 'action_center'];

export default {
	name: 'TesseraIssueDialog',
	components: { Dialog, FormControl, Button },
	props: {
		modelValue: { type: Boolean, default: false },
	},
	emits: ['update:modelValue', 'issued'],
	data() {
		return {
			FEATURE_KEYS,
			saving: false,
			error: '',
			form: this.blankForm(),
		};
	},
	computed: {
		show: {
			get() {
				return this.modelValue;
			},
			set(v) {
				this.$emit('update:modelValue', v);
			},
		},
	},
	methods: {
		blankForm() {
			return {
				customer: '',
				site_url: '',
				app: 'tamkeen',
				company: '',
				tier: 'Pro',
				expires_on: '',
				seats: 25,
				grace_days: 7,
				features: { business_flow_guide: true, watch_tower: true, action_center: false },
				licensed_users: '',
			};
		},
		async submit() {
			this.error = '';
			if (!this.form.customer || !this.form.site_url || !this.form.app) {
				this.error = 'Customer, site URL and app are required.';
				return;
			}
			this.saving = true;
			try {
				const features = FEATURE_KEYS.filter((k) => this.form.features[k]);
				const licensed_users = this.form.licensed_users
					.split('\n')
					.map((s) => s.trim())
					.filter(Boolean);
				await issueLicense({
					customer: this.form.customer,
					site_url: this.form.site_url,
					app: this.form.app,
					company: this.form.company,
					tier: this.form.tier,
					expires_on: this.form.expires_on || null,
					features,
					licensed_users,
					seats: Number(this.form.seats) || 0,
					grace_days: Number(this.form.grace_days) || 0,
				});
				toast.success('License issued');
				this.$emit('issued');
				this.form = this.blankForm();
				this.show = false;
			} catch (e) {
				this.error = e?.messages?.[0] || 'Failed to issue license.';
				toast.error(this.error);
			}
			this.saving = false;
		},
	},
};
</script>
