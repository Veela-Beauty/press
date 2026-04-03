<template>
	<div class="p-4">
		<!-- Tabs -->
		<div class="mb-4 flex gap-0 border-b border-gray-200">
			<button v-for="tab in tabs" :key="tab.id" class="border-b-2 px-4 py-2 text-sm font-medium transition-colors"
				:class="activeTab === tab.id ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
				@click="activeTab = tab.id">{{ tab.label }}</button>
		</div>

		<!-- Quotas & Features -->
		<div v-if="activeTab === 'quotas'">
			<p class="mb-3 text-sm font-semibold text-gray-700">Resource Quotas</p>
			<div class="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
				<div class="rounded-lg border border-gray-100 bg-gray-50 p-3">
					<p class="text-xs text-gray-500">Max Sites</p>
					<div class="mt-1 flex items-center gap-2">
						<span class="text-lg font-bold">{{ team.site_count }}</span>
						<span class="text-gray-400">/</span>
						<input type="number" v-model.number="quotas.max_sites" class="w-16 rounded border border-gray-200 px-2 py-1 text-center text-sm" min="0">
					</div>
				</div>
				<div class="rounded-lg border border-gray-100 bg-gray-50 p-3">
					<p class="text-xs text-gray-500">Max Benches</p>
					<div class="mt-1 flex items-center gap-2">
						<span class="text-lg font-bold">{{ team.bench_count }}</span>
						<span class="text-gray-400">/</span>
						<input type="number" v-model.number="quotas.max_benches" class="w-16 rounded border border-gray-200 px-2 py-1 text-center text-sm" min="0">
					</div>
				</div>
				<div class="rounded-lg border border-gray-100 bg-gray-50 p-3">
					<p class="text-xs text-gray-500">Max Disk (GB)</p>
					<input type="number" v-model.number="quotas.max_disk_gb" class="mt-1 w-20 rounded border border-gray-200 px-2 py-1 text-center text-sm" min="0">
				</div>
				<div class="rounded-lg border border-gray-100 bg-gray-50 p-3">
					<p class="text-xs text-gray-500">Sites by Type</p>
					<div class="mt-1 flex flex-wrap gap-1">
						<Badge v-for="(cnt, typ) in team.site_type_counts" :key="typ" :label="`${cnt} ${typ}`"
							:theme="{ Production: 'blue', Staging: 'orange', Dev: 'green', Demo: 'purple' }[typ] || 'gray'" />
					</div>
				</div>
			</div>

			<p class="mb-2 text-sm font-semibold text-gray-700">Allowed Site Types</p>
			<div class="mb-4 flex gap-2">
				<label v-for="t in ['Production', 'Staging', 'Dev', 'Demo']" :key="t"
					class="flex cursor-pointer items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm"
					:class="allowedTypes.includes(t) ? 'border-blue-500 bg-blue-50' : 'border-gray-200'">
					<input type="checkbox" :checked="allowedTypes.includes(t)" @change="toggleType(t)" class="accent-blue-500"> {{ t }}
				</label>
			</div>

			<p class="mb-2 text-sm font-semibold text-gray-700">Feature Access</p>
			<div class="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
				<div v-for="(feat, fid) in features" :key="fid"
					class="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
					<span class="text-sm"><i :class="'fa fa-' + feat.icon" :style="{ color: feat.color, marginRight: '6px' }"></i>{{ feat.label }}</span>
					<label class="relative inline-block h-5 w-9 cursor-pointer">
						<input type="checkbox" class="peer sr-only" :checked="enabledFeatures[fid]" @change="toggleFeature(fid)">
						<span class="absolute inset-0 rounded-full bg-gray-300 transition-colors peer-checked:bg-blue-500"></span>
						<span class="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform peer-checked:translate-x-4"></span>
					</label>
				</div>
			</div>

			<div class="text-right">
				<Button variant="solid" size="sm" :loading="saving" @click="saveQuotas">Save Changes</Button>
			</div>
		</div>

		<!-- Members -->
		<div v-if="activeTab === 'members'">
			<div class="mb-3 flex items-center justify-between">
				<p class="text-sm font-semibold text-gray-700">Team Members</p>
			</div>
			<div v-if="membersLoading" class="py-4 text-center text-sm text-gray-400">Loading...</div>
			<table v-else class="w-full text-sm">
				<thead class="border-b bg-gray-50 text-xs uppercase text-gray-500"><tr><th class="px-3 py-2 text-left">User</th><th class="px-3 py-2 text-left">Joined</th><th class="px-3 py-2 text-right">Actions</th></tr></thead>
				<tbody>
					<tr v-for="m in members" :key="m.user" class="border-b border-gray-50">
						<td class="px-3 py-2"><div class="font-medium">{{ m.full_name || m.user }}</div><div class="text-xs text-gray-400">{{ m.user }}</div></td>
						<td class="px-3 py-2 text-xs text-gray-500">{{ m.joined?.split(' ')[0] }}</td>
						<td class="px-3 py-2 text-right">
							<Button size="sm" variant="outline" @click="openResetPw(m.user)">Reset Password</Button>
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<!-- Sites -->
		<div v-if="activeTab === 'sites'">
			<div v-if="sitesLoading" class="py-4 text-center text-sm text-gray-400">Loading...</div>
			<table v-else class="w-full text-sm">
				<thead class="border-b bg-gray-50 text-xs uppercase text-gray-500"><tr><th class="px-3 py-2 text-left">Site</th><th class="px-3 py-2 text-left">Type</th><th class="px-3 py-2 text-left">Status</th><th class="px-3 py-2 text-left">Bench</th><th class="px-3 py-2 text-right">Actions</th></tr></thead>
				<tbody>
					<tr v-for="s in sites" :key="s.name" class="border-b border-gray-50">
						<td class="px-3 py-2 font-medium">{{ s.name }}</td>
						<td class="px-3 py-2"><Badge :label="s.site_type || 'Production'" :theme="{ Production: 'blue', Staging: 'orange', Dev: 'green', Demo: 'purple' }[s.site_type] || 'gray'" /></td>
						<td class="px-3 py-2"><Badge :label="s.status" :theme="s.status === 'Active' ? 'green' : s.status === 'Suspended' ? 'red' : 'gray'" /></td>
						<td class="px-3 py-2 text-xs text-gray-500">{{ s.group }}</td>
						<td class="px-3 py-2 text-right">
							<Button v-if="s.status === 'Active'" size="sm" variant="outline" @click="suspendSite(s.name)">Suspend</Button>
							<Button v-if="s.status === 'Suspended'" size="sm" variant="outline" theme="green" @click="unsuspendSite(s.name)">Unsuspend</Button>
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<!-- Benches -->
		<div v-if="activeTab === 'benches'">
			<div v-if="benchesLoading" class="py-4 text-center text-sm text-gray-400">Loading...</div>
			<table v-else class="w-full text-sm">
				<thead class="border-b bg-gray-50 text-xs uppercase text-gray-500"><tr><th class="px-3 py-2 text-left">Bench</th><th class="px-3 py-2 text-left">Version</th><th class="px-3 py-2 text-right">Sites</th><th class="px-3 py-2 text-left">Dev</th><th class="px-3 py-2 text-left">Servers</th></tr></thead>
				<tbody>
					<tr v-for="b in benches" :key="b.name" class="border-b border-gray-50">
						<td class="px-3 py-2 font-medium">{{ b.title || b.name }}</td>
						<td class="px-3 py-2">{{ b.version }}</td>
						<td class="px-3 py-2 text-right">{{ b.site_count }}</td>
						<td class="px-3 py-2"><Badge v-if="b.is_dev" label="Dev" theme="green" /></td>
						<td class="px-3 py-2 text-xs text-gray-500">{{ (b.servers || []).map(s => s.split('.')[0]).join(', ') }}</td>
					</tr>
				</tbody>
			</table>
		</div>

		<!-- Reset Password Dialog -->
		<Dialog :options="{ title: 'Reset Password', size: 'sm' }" v-model="showResetPw">
			<template #body-content>
				<div class="space-y-3">
					<FormControl label="User" :modelValue="resetPwUser" disabled />
					<FormControl label="New Password" type="password" v-model="resetPwValue" placeholder="Enter new password" />
				</div>
			</template>
			<template #actions>
				<Button variant="solid" theme="red" :loading="resettingPw" @click="doResetPw">Reset Password</Button>
			</template>
		</Dialog>
	</div>
</template>

<script>
import { call } from 'frappe-ui';
import { toast } from 'vue-sonner';

const API = 'press.api.admin_panel';

export default {
	name: 'TeamDetail',
	props: { team: Object, features: Object },
	emits: ['updated'],
	data() {
		return {
			activeTab: 'quotas',
			tabs: [
				{ id: 'quotas', label: 'Quotas & Features' },
				{ id: 'members', label: `Members (${this.team.member_count})` },
				{ id: 'sites', label: `Sites (${this.team.site_count})` },
				{ id: 'benches', label: `Benches (${this.team.bench_count})` },
			],
			quotas: { max_sites: this.team.max_sites || 0, max_benches: this.team.max_benches || 0, max_disk_gb: this.team.max_disk_gb || 0 },
			allowedTypes: (this.team.allowed_site_types || '').split('\n').filter(Boolean),
			enabledFeatures: { ...(this.team.features || {}) },
			saving: false,
			members: [], membersLoading: false,
			sites: [], sitesLoading: false,
			benches: [], benchesLoading: false,
			showResetPw: false, resetPwUser: '', resetPwValue: '', resettingPw: false,
		};
	},
	watch: {
		activeTab(tab) {
			if (tab === 'members' && !this.members.length) this.loadMembers();
			if (tab === 'sites' && !this.sites.length) this.loadSites();
			if (tab === 'benches' && !this.benches.length) this.loadBenches();
		},
	},
	methods: {
		toggleType(t) {
			const idx = this.allowedTypes.indexOf(t);
			if (idx >= 0) this.allowedTypes.splice(idx, 1);
			else this.allowedTypes.push(t);
		},
		toggleFeature(fid) {
			this.enabledFeatures[fid] = !this.enabledFeatures[fid];
		},
		async saveQuotas() {
			this.saving = true;
			try {
				await call(`${API}.update_team_quotas`, {
					team: this.team.name,
					max_sites: this.quotas.max_sites,
					max_benches: this.quotas.max_benches,
					max_disk_gb: this.quotas.max_disk_gb,
					allowed_site_types: this.allowedTypes.join('\n'),
					enabled_features: JSON.stringify(this.enabledFeatures),
				});
				toast.success('Quotas saved');
				this.$emit('updated');
			} catch (e) { toast.error('Failed to save'); }
			this.saving = false;
		},
		async loadMembers() {
			this.membersLoading = true;
			this.members = await call(`${API}.get_team_members`, { team: this.team.name });
			this.membersLoading = false;
		},
		async loadSites() {
			this.sitesLoading = true;
			this.sites = await call(`${API}.get_team_sites`, { team: this.team.name });
			this.sitesLoading = false;
		},
		async loadBenches() {
			this.benchesLoading = true;
			this.benches = await call(`${API}.get_team_benches`, { team: this.team.name });
			this.benchesLoading = false;
		},
		openResetPw(user) { this.resetPwUser = user; this.resetPwValue = ''; this.showResetPw = true; },
		async doResetPw() {
			if (!this.resetPwValue) return;
			this.resettingPw = true;
			try {
				await call(`${API}.reset_user_password`, { user: this.resetPwUser, new_password: this.resetPwValue });
				toast.success('Password reset');
				this.showResetPw = false;
			} catch (e) { toast.error(e.messages?.[0] || 'Failed'); }
			this.resettingPw = false;
		},
		async suspendSite(site) {
			if (!confirm(`Suspend ${site}?`)) return;
			await call('press.api.client.run_doc_method', { dt: 'Site', dn: site, method: 'suspend' });
			toast.success('Site suspended');
			this.loadSites();
		},
		async unsuspendSite(site) {
			await call('press.api.client.run_doc_method', { dt: 'Site', dn: site, method: 'unsuspend' });
			toast.success('Site unsuspended');
			this.loadSites();
		},
	},
};
</script>
