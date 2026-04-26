<template>
	<Dialog :options="{ title: 'Open in VS Code', size: 'xl' }" v-model="show">
		<template #body-content v-if="$bench.doc">
			<ErrorMessage
				v-if="certificate && !vscodeUrl && vscodeUrlError"
				class="mt-3"
				:message="vscodeUrlError"
			/>
			<div v-if="certificate && vscodeUrl" class="space-y-4">
				<p class="text-base text-gray-700">
					Connect to <strong>{{ bench }}</strong> with your local VS Code Desktop over SSH.
					Run the commands below once, then click <strong>Launch VS Code</strong>.
				</p>

				<div v-if="isWindows" class="space-y-2">
					<h4 class="text-base font-semibold text-gray-700">Step 1</h4>
					<p class="text-base">Set the PowerShell encoding to UTF-8.</p>
					<ClickToCopyField
						textContent="$PSDefaultParameterValues['*: Encoding'] = 'utf8'"
						:breakLines="false"
					/>
				</div>

				<div class="space-y-2">
					<h4 class="text-base font-semibold text-gray-700">
						Step {{ isWindows ? '2' : '1' }}
					</h4>
					<p class="text-base">Store the SSH certificate locally.</p>
					<ClickToCopyField :textContent="certificateCommand" :breakLines="false" />
				</div>

				<div class="space-y-2">
					<h4 class="text-base font-semibold text-gray-700">
						Step {{ isWindows ? '3' : '2' }}
					</h4>
					<p class="text-base">Launch VS Code Desktop. It opens the bench over Remote-SSH.</p>
					<a :href="vscodeUrl" class="block">
						<Button variant="solid" class="w-full">Launch VS Code</Button>
					</a>
					<p class="mt-2 text-xs text-gray-500">
						Doesn't open automatically? Copy and paste this URL in your browser:
					</p>
					<ClickToCopyField :textContent="vscodeUrl" :breakLines="true" />
				</div>

				<div class="flex items-start gap-2 rounded bg-gray-100 p-3 text-sm text-gray-700">
					<FeatherIcon name="info" class="mt-0.5 h-4 w-4 flex-shrink-0" />
					<p>
						The certificate is valid for <strong>6 hours</strong>. Reopen this dialog after it expires.
						Your local SSH key authenticates you — no Code Server password is needed.
					</p>
				</div>
			</div>

			<div v-else class="space-y-3 text-p-base text-gray-700">
				<p v-if="!$bench.doc.user_ssh_key">
					Add an SSH public key in
					<router-link :to="{ name: 'SettingsDeveloper' }" class="underline" @click="show = false">
						Developer Settings
					</router-link>
					before opening this bench in VS Code.
				</p>
				<p v-else-if="!$bench.doc.is_ssh_proxy_setup">
					SSH access is not enabled for this bench. Please contact support.
				</p>
				<template v-else>
					<p>
						You will need an SSH certificate to connect VS Code over Remote-SSH. The certificate
						is signed for your registered SSH key and is valid for 6 hours.
					</p>
					<div v-if="sshKeys.length > 1" class="space-y-2">
						<label class="block text-sm font-semibold text-gray-700">
							Sign certificate for which key?
						</label>
						<div class="space-y-1.5">
							<label
								v-for="key in sshKeys"
								:key="key.name"
								class="flex items-center gap-2 rounded border p-2"
								:class="keyRowClasses(key)"
							>
								<input
									type="radio"
									:value="key.name"
									v-model="selectedSshKey"
									class="accent-blue-600"
									:disabled="key.is_disabled"
								/>
								<div class="flex-1 truncate">
									<div class="text-sm font-medium text-gray-900">
										{{ key.label || '(no label)' }}
									</div>
									<code class="block truncate text-xs text-gray-500">
										{{ key.ssh_fingerprint }}
									</code>
								</div>
								<span
									v-if="key.is_disabled"
									class="rounded bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-700"
									>Disabled</span
								>
							</label>
						</div>
					</div>
					<ErrorMessage class="mt-3" :message="$releaseGroup.generateCertificate.error" />
				</template>
			</div>
		</template>

		<template
			#actions
			v-if="!certificate && $bench.doc?.is_ssh_proxy_setup && $bench.doc?.user_ssh_key"
		>
			<Button
				:loading="$releaseGroup.generateCertificate.loading"
				:disabled="!selectedSshKey || selectedKeyDisabled"
				@click="handleGenerate"
				variant="solid"
				class="w-full"
			>
				{{ selectedKeyDisabled ? 'Selected key is disabled by admin' : 'Generate SSH Certificate' }}
			</Button>
		</template>
	</Dialog>
</template>

<script>
import { getCachedDocumentResource, call, FeatherIcon } from 'frappe-ui';
import ClickToCopyField from '../ClickToCopyField.vue';

export default {
	props: ['bench', 'releaseGroup'],
	components: { FeatherIcon, ClickToCopyField },
	data() {
		return {
			show: true,
			sshKeys: [],
			selectedSshKey: null,
			vscodeUrl: null,
			vscodeUrlError: null,
		};
	},
	resources: {
		bench() {
			return {
				type: 'document',
				doctype: 'Bench',
				name: this.bench,
				onSuccess: (doc) => {
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
			return this.$releaseGroup.getCertificate.data;
		},
		selectedKeyDisabled() {
			const key = this.sshKeys.find((k) => k.name === this.selectedSshKey);
			return key ? !!key.is_disabled : false;
		},
		certificateCommand() {
			if (!this.certificate) return null;
			return `echo '${this.certificate.ssh_certificate?.trim()}' > ~/.ssh/id_${this.certificate.key_type}-cert.pub`;
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
		// Mirrors SSHCertificateDialog.loadSshKeys — keep these two in sync.
		async loadSshKeys() {
			try {
				this.sshKeys = await call('press.api.account.get_user_ssh_keys');
				const activeDefault = this.sshKeys.find((k) => k.is_default && !k.is_disabled);
				const firstActive = this.sshKeys.find((k) => !k.is_disabled);
				this.selectedSshKey = (activeDefault || firstActive || this.sshKeys[0])?.name;
				if (this.selectedSshKey) {
					await this.$releaseGroup.getCertificate.submit({ ssh_key_name: this.selectedSshKey });
					await this.loadVscodeUrl();
				}
			} catch (e) {
				this.sshKeys = [];
			}
		},
		async loadVscodeUrl() {
			this.vscodeUrlError = null;
			try {
				this.vscodeUrl = await call(
					'press.press.doctype.bench.bench_dev_overview.get_vscode_remote_url',
					{ bench_name: this.bench },
				);
			} catch (e) {
				this.vscodeUrl = null;
				this.vscodeUrlError =
					e?.messages?.join(', ') || e?.message || 'Failed to compose VS Code URL';
			}
		},
		async handleGenerate() {
			await this.$releaseGroup.generateCertificate.submit({ ssh_key_name: this.selectedSshKey });
			await this.$releaseGroup.getCertificate.submit({ ssh_key_name: this.selectedSshKey });
			await this.loadVscodeUrl();
		},
	},
};
</script>
