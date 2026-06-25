<template>
	<div class="rounded-lg border border-gray-200 bg-white">
		<div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
			<p class="text-sm font-semibold">Over-deployment watch</p>
			<span class="text-xs text-gray-400">same key seen on more than one domain</span>
		</div>
		<div v-if="loading" class="py-8 text-center text-sm text-gray-400">Loading…</div>
		<div v-else-if="error" class="py-8 text-center text-sm text-red-500">{{ error }}</div>
		<div v-else-if="!rows.length" class="py-8 text-center text-sm text-gray-400">
			No heartbeats recorded yet.
		</div>
		<table v-else class="w-full text-sm">
			<thead class="border-b border-gray-200 bg-gray-50 text-xs uppercase text-gray-500">
				<tr>
					<th class="px-4 py-2 text-left">License key</th>
					<th class="px-4 py-2 text-left">Customer</th>
					<th class="px-4 py-2 text-left">Seen on</th>
					<th class="px-4 py-2 text-left">Last check</th>
					<th class="px-4 py-2"></th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="r in rows" :key="r.license_key" class="border-b border-gray-50 last:border-0">
					<td class="px-4 py-2 font-mono text-xs">{{ r.license_key }}</td>
					<td class="px-4 py-2">{{ r.customer || '-' }}</td>
					<td class="px-4 py-2">
						<Badge
							:label="`${r.site_count} ${r.site_count === 1 ? 'domain' : 'domains'}`"
							:theme="r.site_count > 1 ? 'red' : 'green'"
						/>
						<span v-if="r.site_count > 1" class="ml-2 font-mono text-xs text-gray-400">{{ r.sites }}</span>
					</td>
					<td class="px-4 py-2 text-gray-500">{{ fmtDate(r.last_checked) }}</td>
					<td class="px-4 py-2 text-right">
						<Button v-if="r.site_count > 1" size="sm" theme="red" variant="solid" @click="onRevoke(r)">
							Revoke
						</Button>
						<Button v-else size="sm" variant="outline" :disabled="true">OK</Button>
					</td>
				</tr>
			</tbody>
		</table>
	</div>
</template>

<script>
import { Button, Badge } from 'frappe-ui';
import { toast } from 'vue-sonner';
import { listHeartbeat, revokeLicense, fmtDate } from './tesseraApi.js';

export default {
	name: 'TesseraHeartbeat',
	components: { Button, Badge },
	setup() {
		return { fmtDate };
	},
	data() {
		return {
			loading: false,
			error: '',
			rows: [],
		};
	},
	mounted() {
		this.load();
	},
	methods: {
		async load() {
			this.loading = true;
			this.error = '';
			try {
				this.rows = (await listHeartbeat()) || [];
			} catch (e) {
				this.error = e?.messages?.[0] || 'Failed to load heartbeat data.';
				toast.error('Failed to load heartbeat data');
			}
			this.loading = false;
		},
		async onRevoke(r) {
			if (!confirm(`Revoke ${r.license_key}? It is deployed on ${r.site_count} domains.`)) return;
			try {
				await revokeLicense(r.license_key);
				toast.success('License revoked');
				await this.load();
			} catch (e) {
				toast.error(e?.messages?.[0] || 'Revoke failed');
			}
		},
	},
};
</script>
