<template>
	<div class="rounded-lg border border-gray-200 bg-white">
		<div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
			<p class="text-sm font-semibold">Generate offline license file</p>
			<span class="text-xs text-gray-400">for air-gapped client sites</span>
		</div>
		<div class="space-y-4 px-4 py-4">
			<div class="grid grid-cols-2 gap-3">
				<div>
					<label class="mb-1 block text-xs font-medium text-gray-600">License</label>
					<select
						v-model="selectedName"
						class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
					>
						<option v-for="l in licenses" :key="l.name" :value="l.name">
							{{ l.customer || l.company || l.site_url }} · {{ l.app }} · {{ l.tier }}
						</option>
					</select>
				</div>
				<div>
					<label class="mb-1 block text-xs font-medium text-gray-600">Node-lock</label>
					<input
						class="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 font-mono text-sm text-gray-600"
						:value="selected ? selected.site_url : ''"
						readonly
					/>
				</div>
			</div>

			<Button variant="solid" :loading="generating" :disabled="!selected" @click="generate">
				<template #prefix><lucide-lock class="h-4 w-4" /></template>
				Sign &amp; generate
			</Button>
			<p v-if="error" class="text-xs text-red-500">{{ error }}</p>

			<div class="border-t border-gray-100 pt-4">
				<label class="mb-1 block text-xs font-medium text-gray-600">
					Signed file <span class="text-gray-400">- send to the client to paste into Activate offline</span>
				</label>
				<textarea
					class="w-full rounded-lg border border-gray-200 px-3 py-2 font-mono text-xs"
					rows="5"
					readonly
					:value="token"
					placeholder="Click Sign & generate to produce the signed token."
				></textarea>
				<div class="mt-2 flex gap-2">
					<Button size="sm" variant="outline" :disabled="!token" @click="copy">
						<template #prefix><lucide-copy class="h-3.5 w-3.5" /></template>
						Copy
					</Button>
					<Button size="sm" variant="outline" :disabled="!token" @click="download">
						<template #prefix><lucide-download class="h-3.5 w-3.5" /></template>
						Download .tessera
					</Button>
				</div>
			</div>
		</div>
	</div>
</template>

<script>
import { Button } from 'frappe-ui';
import { toast } from 'vue-sonner';
import { listLicenses, generateOfflineFile } from './tesseraApi.js';

export default {
	name: 'TesseraOffline',
	components: { Button },
	data() {
		return {
			licenses: [],
			selectedName: '',
			token: '',
			generating: false,
			error: '',
		};
	},
	computed: {
		selected() {
			return this.licenses.find((l) => l.name === this.selectedName);
		},
	},
	mounted() {
		this.loadLicenses();
	},
	methods: {
		async loadLicenses() {
			try {
				this.licenses = (await listLicenses()) || [];
				if (this.licenses.length) this.selectedName = this.licenses[0].name;
			} catch (e) {
				toast.error('Failed to load licenses');
			}
		},
		async generate() {
			if (!this.selected) return;
			this.generating = true;
			this.error = '';
			this.token = '';
			try {
				const result = await generateOfflineFile(this.selected.license_key);
				this.token = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
			} catch (e) {
				this.error = e?.messages?.[0] || 'Failed to generate the offline file.';
				toast.error(this.error);
			}
			this.generating = false;
		},
		async copy() {
			if (!this.token) return;
			try {
				await navigator.clipboard.writeText(this.token);
				toast.success('Copied to clipboard');
			} catch {
				toast.error('Copy failed; select the text manually.');
			}
		},
		download() {
			if (!this.token) return;
			const blob = new Blob([this.token], { type: 'application/octet-stream' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `${this.selected ? this.selected.license_key : 'license'}.tessera`;
			a.click();
			URL.revokeObjectURL(url);
		},
	},
};
</script>
