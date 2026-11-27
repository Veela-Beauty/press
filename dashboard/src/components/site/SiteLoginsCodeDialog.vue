<template>
	<!-- PRS-SP-17: a 6-digit code before a site login is shown or shared. A user without an authenticator app links one
	     here (same endpoints as Account > Profile), then saves the recovery codes; the code they type also unlocks. -->
	<Dialog
		v-model="show"
		:options="{ title: dialogTitle, actions }"
		:disableOutsideClickToClose="recoveryCodes.length > 0"
	>
		<template #body-content>
			<TFARecoveryCodes v-if="recoveryCodes.length" :recoveryCodes="recoveryCodes" />
			<div v-else class="space-y-4">
				<div v-if="linking" class="space-y-3">
					<ol class="list-decimal space-y-2 pl-5 text-base text-gray-700">
						<li>Install Google Authenticator or Microsoft Authenticator on your phone.</li>
						<li>In the app, add an account and scan this code.</li>
					</ol>
					<div class="flex items-center gap-4">
						<VueQrcode
							v-if="qrUrl"
							:value="qrUrl"
							type="image/png"
							:width="120"
							:color="{ dark: '#000000ff', light: '#ffffffff' }"
						/>
						<p class="text-sm text-gray-600">
							Can't scan? Enter this key in the app:<br />
							<span class="font-mono">{{ setupKey }}</span>
						</p>
					</div>
				</div>
				<FormControl
					v-model="code"
					:label="hint"
					inputmode="numeric"
					autocomplete="one-time-code"
					maxlength="6"
					@keydown.enter="verify"
				/>
				<Button v-if="method === 'app'" variant="ghost" :loading="$resources.sendEmailCode.loading" @click="sendEmail">
					Email me a code instead
				</Button>
				<ErrorMessage :message="error" />
			</div>
		</template>
	</Dialog>
</template>

<script>
import VueQrcode from 'vue-qrcode';
import TFARecoveryCodes from '../settings/profile/TFARecoveryCodes.vue';

export default {
	name: 'SiteLoginsCodeDialog',
	props: {
		modelValue: { type: Boolean, required: true },
		site: { type: String, required: true },
		hasApp: { type: Boolean, default: false },
	},
	emits: ['update:modelValue', 'verified', 'linked'],
	components: { VueQrcode, TFARecoveryCodes },
	data() {
		return { code: '', method: 'app', sentTo: '', error: '', recoveryCodes: [], qrUrl: '', linkedHere: false, unlocked: false };
	},
	computed: {
		show: {
			get() {
				return this.modelValue;
			},
			set(value) {
				if (!value && this.recoveryCodes.length) return; // shown once: only Done closes
				if (!value) this.reset();
				this.$emit('update:modelValue', value);
			},
		},
		linking() {
			return this.method === 'app' && !this.hasApp && !this.linkedHere;
		},
		dialogTitle() {
			if (this.recoveryCodes.length) return 'Save your recovery codes';
			return this.linking ? 'Link an authenticator app (once)' : "Confirm it's you";
		},
		hint() {
			if (this.method === 'email') return `Enter the 6-digit code we emailed to ${this.sentTo}`;
			return this.linking ? '3. Enter the 6-digit code the app shows' : 'Enter the 6-digit code from your authenticator app';
		},
		setupKey() {
			return new URL(this.qrUrl || 'otpauth://x?secret=').searchParams.get('secret') || '';
		},
		actions() {
			if (this.recoveryCodes.length) return [{ label: 'Done', variant: 'solid', onClick: this.done }];
			return [
				{ label: 'Cancel', variant: 'outline', onClick: () => (this.show = false) },
				{ label: 'Verify', variant: 'solid', loading: this.busy, onClick: this.verify },
			];
		},
		busy() {
			return this.$resources.enable2FA.loading || this.$resources.verifyCode.loading;
		},
	},
	watch: {
		modelValue(open) {
			if (open && this.linking && !this.qrUrl) this.$resources.qrUrl.fetch();
		},
	},
	methods: {
		reset() {
			Object.assign(this, { code: '', method: 'app', sentTo: '', error: '', recoveryCodes: [], unlocked: false });
		},
		async verify() {
			this.error = '';
			const code = String(this.code).trim();
			if (!/^\d{6}$/.test(code)) {
				this.error = 'Enter the 6-digit code';
				return;
			}
			if (this.linking) {
				try {
					this.recoveryCodes = (await this.$resources.enable2FA.submit({ totp_code: code })) || [];
					this.linkedHere = true;
					this.$emit('linked');
				} catch (e) {
					this.fail(e);
					return;
				}
				// the recovery codes stay on screen whatever happens next: they are shown once
				this.unlocked = await this.$resources.verifyCode
					.submit({ name: this.site, code, method: 'app', linked: 1 })
					.then(() => true, () => false);
				return;
			}
			try {
				await this.$resources.verifyCode.submit({ name: this.site, code, method: this.method });
				this.finish();
			} catch (e) {
				this.fail(e);
			}
		},
		fail(e) {
			this.code = '';
			this.error = e.messages?.join(' ') || e.message || 'Wrong code';
		},
		done() {
			this.recoveryCodes = [];
			if (this.unlocked) return this.finish();
			this.code = '';
			this.error = 'Enter the newest code from your app to continue';
		},
		finish() {
			this.$emit('verified');
			this.show = false;
		},
		async sendEmail() {
			this.error = '';
			try {
				this.sentTo = (await this.$resources.sendEmailCode.submit({ name: this.site })).sent_to;
				this.method = 'email';
			} catch (e) {
				this.fail(e);
			}
		},
	},
	resources: {
		qrUrl() {
			return {
				url: 'press.api.account.get_2fa_qr_code_url',
				onSuccess(url) {
					this.qrUrl = url;
				},
			};
		},
		enable2FA() {
			return { url: 'press.api.account.enable_2fa' };
		},
		verifyCode() {
			return { url: 'press.api.site_logins.verify_code' };
		},
		sendEmailCode() {
			return { url: 'press.api.site_logins.send_email_code' };
		},
	},
};
</script>
