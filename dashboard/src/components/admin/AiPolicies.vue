<template>
	<div class="space-y-4">
		<AiPolicyForm v-if="view === 'form'" :key="openName || 'new'" :name="openName" @back="closeForm" @saved="onSaved" />
		<template v-else>
			<div class="flex items-center justify-between">
				<div>
					<h2 class="text-lg font-semibold">Claude Code policies</h2>
					<p class="text-xs text-gray-500">A policy is everything a person gets in Claude Code. Put each person on one in the Seats tab.</p>
				</div>
				<Button variant="solid" @click="openForm(null)">New policy</Button>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4">
				<h3 class="mb-3 text-sm font-semibold">Policies <span class="font-normal text-gray-400">(click a row to open it)</span></h3>
				<table class="w-full text-xs">
					<thead>
						<tr class="border-b border-gray-100 text-left text-gray-500">
							<th class="py-2">Name</th><th>Permission mode</th><th>Route</th><th>Hard model</th><th class="text-right">People using it</th>
						</tr>
					</thead>
					<tbody>
						<template v-if="loading">
							<tr v-for="n in 3" :key="n"><td colspan="5" class="py-2"><div class="h-5 animate-pulse rounded bg-gray-100"></div></td></tr>
						</template>
						<tr
							v-for="p in policies" :key="p.name" tabindex="0"
							class="cursor-pointer border-b border-gray-50 hover:bg-gray-50"
							@click="openForm(p.name)" @keydown.enter="openForm(p.name)"
						>
							<td class="py-2 font-medium text-gray-800">{{ p.name }}</td>
							<td>{{ p.permission_mode }}</td>
							<td>{{ p.route }}</td>
							<td class="font-mono text-gray-500">{{ hardModelLabel(p) }}</td>
							<td class="text-right font-mono">{{ p.people_using }}</td>
						</tr>
						<tr v-if="!loading && policies.length === 0"><td colspan="5" class="py-6 text-center text-gray-400">No policies yet. Click New policy.</td></tr>
					</tbody>
				</table>
			</div>
		</template>
	</div>
</template>

<script>
import { Button, call } from 'frappe-ui';
import { toast } from 'vue-sonner';
import AiPolicyForm from './AiPolicyForm.vue';
import { hardModelLabel } from './policies-derive.js';

export default {
	name: 'AiPolicies',
	components: { Button, AiPolicyForm },
	data() {
		return { policies: [], loading: true, view: 'list', openName: null };
	},
	mounted() { this.load(); },
	methods: {
		async load() {
			this.loading = true;
			try {
				const r = await call('sanad_ai_control_center.policies.list_policies');
				this.policies = r.policies || [];
			} catch (e) { toast.error(e.messages?.[0] || 'Could not load the policies'); }
			this.loading = false;
		},
		openForm(name) { this.openName = name; this.view = 'form'; },
		closeForm() { this.view = 'list'; },
		onSaved() { this.view = 'list'; this.load(); },
		hardModelLabel,
	},
};
</script>
