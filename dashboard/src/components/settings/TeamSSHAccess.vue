<template>
	<div class="space-y-4">
		<div class="flex items-center justify-between">
			<div>
				<h2 class="text-lg font-semibold text-gray-900">Team SSH Access</h2>
				<p class="text-sm text-gray-500">Control which team members can SSH into benches. Only the team owner can manage these keys.</p>
			</div>
			<Button :loading="loading" @click="loadKeys" variant="outline" size="sm">Refresh</Button>
		</div>

		<div v-if="loading && !keys.length" class="py-12 text-center text-sm text-gray-400">Loading keys...</div>
		<div v-else-if="!loading && !keys.length" class="rounded-lg border border-dashed border-gray-200 bg-gray-50 py-12 text-center text-sm text-gray-500">
			No SSH keys registered by any team member yet.
		</div>

		<div v-else class="overflow-hidden rounded-lg border border-gray-200 bg-white">
			<table class="w-full text-sm">
				<thead class="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
					<tr>
						<th class="px-4 py-2.5 text-left">Team Member</th>
						<th class="px-4 py-2.5 text-left">Key Label</th>
						<th class="px-4 py-2.5 text-left">Fingerprint</th>
						<th class="px-4 py-2.5 text-left">Status</th>
						<th class="px-4 py-2.5 text-right">Actions</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="key in keys" :key="key.name" class="border-b border-gray-50 last:border-0 hover:bg-gray-50">
						<td class="px-4 py-2.5">
							<div class="font-medium">{{ key.user_full_name }}</div>
							<div class="text-xs text-gray-400">{{ key.user }}</div>
						</td>
						<td class="px-4 py-2.5">
							<div class="flex items-center gap-2">
								<input
									v-model="labelEdits[key.name]"
									type="text"
									placeholder="Add label"
									class="w-40 rounded border border-gray-200 bg-white px-2 py-1 text-xs focus:border-blue-500 focus:outline-none"
									@keyup.enter="saveLabel(key)"
									@blur="saveLabel(key)"
								/>
								<span v-if="key.is_default" class="rounded bg-green-100 px-1.5 py-0.5 text-xs font-medium text-green-700">Default</span>
							</div>
						</td>
						<td class="max-w-[220px] truncate px-4 py-2.5"><code class="text-xs text-gray-600">{{ key.ssh_fingerprint }}</code></td>
						<td class="px-4 py-2.5">
							<span v-if="key.is_disabled" class="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700" :title="disabledTooltip(key)">Disabled</span>
							<span v-else class="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">Active</span>
						</td>
						<td class="px-4 py-2.5 text-right">
							<div class="flex justify-end gap-1">
								<Button
									v-if="!key.is_disabled"
									size="sm"
									variant="outline"
									:loading="pending[key.name] === 'disable'"
									@click="toggleDisabled(key, true)"
								>Disable</Button>
								<Button
									v-else
									size="sm"
									variant="outline"
									:loading="pending[key.name] === 'enable'"
									@click="toggleDisabled(key, false)"
								>Enable</Button>
								<Button
									size="sm"
									variant="outline"
									theme="red"
									:loading="pending[key.name] === 'remove'"
									@click="confirmRemove(key)"
								>Remove</Button>
							</div>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

<script>
import { call } from 'frappe-ui';
import { toast } from 'vue-sonner';

export default {
	name: 'TeamSSHAccess',
	data() {
		return {
			keys: [],
			loading: false,
			pending: {},
			labelEdits: {},
		};
	},
	mounted() {
		this.loadKeys();
	},
	methods: {
		async loadKeys() {
			this.loading = true;
			try {
				this.keys = await call('press.api.account.get_team_ssh_keys');
				this.labelEdits = Object.fromEntries(this.keys.map((k) => [k.name, k.label || '']));
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to load team SSH keys');
				this.keys = [];
			} finally {
				this.loading = false;
			}
		},
		disabledTooltip(key) {
			if (!key.is_disabled) return '';
			let msg = 'Disabled';
			if (key.disabled_by) msg += ` by ${key.disabled_by}`;
			if (key.disabled_on) msg += ` on ${new Date(key.disabled_on).toLocaleString()}`;
			return msg;
		},
		async toggleDisabled(key, disabled) {
			this.pending = { ...this.pending, [key.name]: disabled ? 'disable' : 'enable' };
			try {
				await call('press.api.account.set_team_ssh_key_disabled', { key_name: key.name, disabled });
				toast.success(disabled ? `Disabled ${key.user}'s key` : `Enabled ${key.user}'s key`);
				await this.loadKeys();
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to update key');
			} finally {
				this.pending = { ...this.pending, [key.name]: null };
			}
		},
		confirmRemove(key) {
			if (!confirm(`Remove ${key.user}'s SSH key? This cannot be undone.`)) return;
			this.removeKey(key);
		},
		async removeKey(key) {
			this.pending = { ...this.pending, [key.name]: 'remove' };
			try {
				await call('press.api.account.remove_team_ssh_key', { key_name: key.name });
				toast.success(`Removed ${key.user}'s key`);
				await this.loadKeys();
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to remove key');
			} finally {
				this.pending = { ...this.pending, [key.name]: null };
			}
		},
		async saveLabel(key) {
			const newLabel = (this.labelEdits[key.name] || '').trim();
			if (newLabel === (key.label || '')) return;
			try {
				await call('press.api.account.set_ssh_key_label', { key_name: key.name, label: newLabel });
				key.label = newLabel;
				toast.success('Label updated');
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to update label');
				this.labelEdits[key.name] = key.label || '';
			}
		},
	},
};
</script>
