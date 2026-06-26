<template>
	<div class="space-y-4">
		<!-- Licensed users for the selected license -->
		<div class="rounded-lg border border-gray-200 bg-white">
			<div class="flex flex-wrap items-center gap-2 border-b border-gray-100 px-4 py-3">
				<p class="text-sm font-semibold">Licensed users</p>
				<span class="flex-1"></span>
				<select
					v-model="selectedName"
					class="min-w-[240px] rounded-lg border border-gray-200 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
					@change="loadDetail"
				>
					<option v-for="l in licenses" :key="l.name" :value="l.name">
						{{ l.customer || l.company || l.site_url }} · {{ l.app }} · {{ l.tier }}
					</option>
				</select>
				<span v-if="detail" class="text-xs text-gray-500">
					{{ seats.length }} / {{ detail.seats || 0 }} seats
				</span>
			</div>
			<div class="px-4 py-3">
				<div v-if="loading" class="py-4 text-center text-sm text-gray-400">Loading…</div>
				<div v-else-if="!detail" class="py-4 text-center text-sm text-gray-400">
					Select a license to manage its allowlist.
				</div>
				<div v-else class="flex flex-wrap gap-2">
					<span
						v-for="u in seats"
						:key="u.email || u.name"
						class="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs text-gray-700"
					>
						{{ u.email }}
						<button class="text-gray-400 hover:text-red-500" @click="onRemove(u.email)">&times;</button>
					</span>
					<button
						class="inline-flex items-center gap-1 rounded-full border border-dashed border-gray-300 px-3 py-1 text-xs text-gray-500 hover:border-blue-400 hover:text-blue-500"
						@click="onAdd"
					>
						<lucide-plus class="h-3 w-3" /> add user
					</button>
				</div>
			</div>
		</div>

		<!-- Change requests (static inbox per spec) -->
		<div class="rounded-lg border border-gray-200 bg-white">
			<div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
				<p class="text-sm font-semibold">Change requests</p>
				<Badge :label="`${requests.length} pending`" theme="orange" />
			</div>
			<div class="divide-y divide-gray-50">
				<div v-for="(r, i) in requests" :key="i" class="flex items-center gap-2 px-4 py-2.5 text-sm">
					<span><b>{{ r.type }}</b> {{ r.email }} <span class="text-gray-400">· {{ r.note }}</span></span>
					<span class="flex-1"></span>
					<Button size="sm" variant="outline">Reject</Button>
					<Button size="sm" variant="solid">Approve</Button>
				</div>
			</div>
			<p class="px-4 py-3 text-xs text-gray-400">
				We own the allowlist; clients request changes here. Approving pushes the new list to the next token.
			</p>
		</div>
	</div>
</template>

<script>
import { Button, Badge } from 'frappe-ui';
import { toast } from 'vue-sonner';
import { listLicenses, getLicense, addSeat, removeSeat } from './tesseraApi.js';

export default {
	name: 'TesseraSeats',
	components: { Button, Badge },
	data() {
		return {
			licenses: [],
			selectedName: '',
			detail: null,
			loading: false,
			// Static change-request inbox (per spec; later replaced by a real inbox).
			requests: [
				{ type: 'Add', email: 'sara@acme.com', note: 'requested by Acme admin' },
				{ type: 'Remove', email: 'omar@acme.com', note: 'left the company' },
			],
		};
	},
	computed: {
		seats() {
			return this.detail ? this.detail.ts_licensed_users || [] : [];
		},
	},
	mounted() {
		this.loadLicenses();
	},
	methods: {
		async loadLicenses() {
			try {
				this.licenses = (await listLicenses()) || [];
				if (this.licenses.length && !this.selectedName) {
					this.selectedName = this.licenses[0].name;
					await this.loadDetail();
				}
			} catch (e) {
				toast.error('Failed to load licenses');
			}
		},
		async loadDetail() {
			if (!this.selectedName) return;
			this.loading = true;
			try {
				this.detail = await getLicense(this.selectedName);
			} catch (e) {
				toast.error('Failed to load license detail');
			}
			this.loading = false;
		},
		async onAdd() {
			const email = window.prompt('Add user email to the allowlist');
			if (!email) return;
			try {
				await addSeat(this.detail.license_key, email.trim());
				toast.success('Seat added');
				await this.loadDetail();
			} catch (e) {
				toast.error(e?.messages?.[0] || 'Add failed');
			}
		},
		async onRemove(email) {
			try {
				await removeSeat(this.detail.license_key, email);
				toast.success('Seat removed');
				await this.loadDetail();
			} catch (e) {
				toast.error(e?.messages?.[0] || 'Remove failed');
			}
		},
	},
};
</script>
