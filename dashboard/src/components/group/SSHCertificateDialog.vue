<template>
	<Dialog
		:options="{
			title: 'SSH Access',
			size: 'xl',
		}"
		v-model="show"
	>
		<template #body-content v-if="$bench.doc">
			<div v-if="certificate" class="space-y-4">
				<div class="space-y-2" v-if="isWindows">
					<h4 class="text-base font-semibold text-gray-700">Step 1</h4>
					<div class="space-y-2">
						<p class="text-base">
							Execute the following shell command to set the encoding to UTF-8.
						</p>
						<ClickToCopyField
							textContent="$PSDefaultParameterValues['*: Encoding'] = 'utf8'"
							:breakLines="false"
						/>
					</div>
				</div>
				<div class="space-y-2">
					<h4 class="text-base font-semibold text-gray-700">
						Step {{ isWindows ? '2' : '1' }}
					</h4>
					<div class="space-y-2">
						<p class="text-base">
							Execute the following shell command to store the SSH certificate
							locally.
						</p>
						<ClickToCopyField
							:textContent="certificateCommand"
							:breakLines="false"
						/>
					</div>
				</div>
				<div class="space-y-2">
					<h4 class="text-base font-semibold text-gray-700">
						Step {{ isWindows ? '3' : '2' }}
					</h4>
					<div class="space-y-1">
						<p class="text-base">
							Execute the following shell command to SSH into your bench
						</p>
						<ClickToCopyField :textContent="sshCommand" />
					</div>
				</div>
				<div v-if="sshKeys.length > 1" class="flex items-center justify-between rounded bg-blue-50 p-3 text-sm">
					<span class="text-gray-700">Certificate issued for key: <strong>{{ selectedKeyLabel || selectedKeyFingerprint }}</strong></span>
					<button class="font-medium text-blue-600 hover:underline" @click="reissueForDifferentKey">Reissue for a different key</button>
				</div>
				<div class="flex items-center gap-2 rounded bg-gray-100 p-3">
					<FeatherIcon name="alert-triangle" class="h-4 w-4" />
					<div class="space-y-1 text-base">
						<p>
							Use wisely and only for
							<a
								href="/docs/benches/debugging"
								class="underline"
								target="_blank"
								>debugging</a
							>
							purposes.
						</p>
						<p>
							The changes(app/files) made during the SSH session are not
							guaranteed to persist after the session ends.
						</p>
					</div>
				</div>
			</div>
			<div class="space-y-3 text-p-base text-gray-700" v-else>
				<p v-if="!$bench.doc.user_ssh_key">
					It looks like you haven't added your SSH public key. Go to
					<router-link
						:to="{ name: 'SettingsDeveloper' }"
						class="underline"
						@click="show = false"
					>
						Developer Settings</router-link
					>
					to add your SSH public key.
				</p>
				<p v-else-if="!$bench.doc.is_ssh_proxy_setup">
					SSH access is not enabled for this bench. Please contact support to
					enable access.
				</p>
				<template v-else>
					<p>
						You will need an SSH certificate to get SSH access to your bench. This
						certificate will work only with your public-private key pair and will
						be valid for 6 hours.
					</p>
					<div v-if="sshKeys.length > 1" class="space-y-2">
						<label class="block text-sm font-semibold text-gray-700">Which SSH key should this certificate sign?</label>
						<div class="space-y-1.5">
							<label v-for="key in sshKeys" :key="key.name" class="flex items-center gap-2 rounded border p-2" :class="keyRowClasses(key)">
								<input type="radio" :value="key.name" v-model="selectedSshKey" class="accent-blue-600" :disabled="key.is_disabled" />
								<div class="flex-1 truncate">
									<div class="text-sm font-medium text-gray-900">{{ key.label || '(no label)' }}</div>
									<code class="block truncate text-xs text-gray-500">{{ key.ssh_fingerprint }}</code>
								</div>
								<span v-if="key.is_default" class="rounded bg-green-100 px-1.5 py-0.5 text-xs font-medium text-green-700">Default</span>
								<span v-if="key.is_disabled" class="rounded bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-700">Disabled</span>
							</label>
						</div>
					</div>
					<div v-else-if="sshKeys.length === 1" class="text-xs text-gray-500">
						Using your only registered key: <strong>{{ sshKeys[0].label || sshKeys[0].ssh_fingerprint }}</strong>
						<span v-if="sshKeys[0].is_disabled" class="ml-2 rounded bg-red-100 px-1.5 py-0.5 font-medium text-red-700">Disabled</span>
					</div>
				</template>
				<p>
					Please refer to the
					<a href="/docs/benches/ssh" class="underline" target="_blank"
						>SSH Access documentation</a
					>
					for more details.
				</p>
				<ErrorMessage
					class="mt-3"
					:message="$releaseGroup.generateCertificate.error"
				/>
			</div>
		</template>
		<template
			#actions
			v-if="
				!certificate &&
				$bench.doc?.is_ssh_proxy_setup &&
				$bench.doc?.user_ssh_key
			"
		>
			<Button
				:loading="$releaseGroup.generateCertificate.loading"
				:disabled="!selectedSshKey || selectedKeyDisabled"
				@click="handleGenerate"
				variant="solid"
				class="w-full"
				>{{ selectedKeyDisabled ? 'Selected key is disabled by admin' : 'Generate SSH Certificate' }}</Button
			>
		</template>
	</Dialog>
</template>

<script>
import { getCachedDocumentResource, call } from 'frappe-ui';

export default {
	props: ['bench', 'releaseGroup'],
	data() {
		return {
			show: true,
			sshKeys: [],
			selectedSshKey: null,
			forceKeySelection: false,
		};
	},
	resources: {
		bench() {
			return {
				type: 'document',
				doctype: 'Bench',
				name: this.bench,
				onSuccess(doc) {
					if (doc.is_ssh_proxy_setup && doc.user_ssh_key) {
						this.loadSshKeys();
					}
				},
			};
		},
	},
	computed: {
		$bench() {
			return this.$resources.bench;
		},
		$releaseGroup() {
			return getCachedDocumentResource('Release Group', this.releaseGroup);
		},
		certificate() {
			if (this.forceKeySelection) return null;
			return this.$releaseGroup.getCertificate.data;
		},
		selectedKeyFingerprint() {
			const key = this.sshKeys.find((k) => k.name === this.selectedSshKey);
			return key ? key.ssh_fingerprint : '';
		},
		selectedKeyLabel() {
			const key = this.sshKeys.find((k) => k.name === this.selectedSshKey);
			return key && key.label ? key.label : '';
		},
		selectedKeyDisabled() {
			const key = this.sshKeys.find((k) => k.name === this.selectedSshKey);
			return key ? !!key.is_disabled : false;
		},
		sshCommand() {
			if (!this.$bench.doc) return;
			return `ssh ${this.$bench.doc.name}@${this.$bench.doc.proxy_server} -p 2222`;
		},
		certificateCommand() {
			if (this.certificate) {
				return `echo '${this.certificate.ssh_certificate?.trim()}' > ~/.ssh/id_${
					this.certificate.key_type
				}-cert.pub`;
			}
			return null;
		},
		isWindows() {
			return navigator.userAgent.includes('Windows');
		},
	},
	methods: {
		keyRowClasses(key) {
			const base = ' cursor-pointer hover:bg-gray-50';
			if (key.is_disabled) return 'border-red-200 bg-red-50 cursor-not-allowed opacity-70';
			if (this.selectedSshKey === key.name) return 'border-blue-400 bg-blue-50' + base;
			return 'border-gray-200' + base;
		},
		async loadSshKeys() {
			try {
				this.sshKeys = await call('press.api.account.get_user_ssh_keys');
				// Prefer default key if active; else first non-disabled; else first
				const activeDefault = this.sshKeys.find((k) => k.is_default && !k.is_disabled);
				const firstActive = this.sshKeys.find((k) => !k.is_disabled);
				this.selectedSshKey = (activeDefault || firstActive || this.sshKeys[0])?.name;
				if (this.selectedSshKey) {
					await this.$releaseGroup.getCertificate.submit({ ssh_key_name: this.selectedSshKey });
				}
			} catch (e) {
				this.sshKeys = [];
			}
		},
		async handleGenerate() {
			await this.$releaseGroup.generateCertificate.submit({ ssh_key_name: this.selectedSshKey });
			await this.$releaseGroup.getCertificate.submit({ ssh_key_name: this.selectedSshKey });
			this.forceKeySelection = false;
		},
		reissueForDifferentKey() {
			this.forceKeySelection = true;
		},
	},
};
</script>
