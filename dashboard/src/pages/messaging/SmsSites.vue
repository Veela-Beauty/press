<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header><Breadcrumbs :items="crumbs" /></Header>
		</div>
		<div class="flex-1 overflow-auto p-5">
			<div class="mb-4 flex items-center gap-2">
				<h1 class="text-lg font-semibold text-gray-900">SMS sites</h1>
				<div class="flex-1" />
				<FormControl v-model="q" type="text" placeholder="Search sites..." class="w-44 text-sm" />
			</div>
			<div v-if="error" class="rounded-lg border border-red-200 bg-red-50 p-4 text-base text-red-700">
				{{ error }}
			</div>
			<div v-else class="overflow-x-auto rounded-lg border border-gray-200">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-200 bg-gray-50 text-left text-xs text-gray-500">
							<th class="px-3 py-2 font-medium">Site</th>
							<th class="px-3 py-2 font-medium">Client</th>
							<th class="px-3 py-2 text-right font-medium">SMS this month</th>
							<th class="px-3 py-2 text-right font-medium">SMS codes</th>
						</tr>
					</thead>
					<tbody>
						<tr v-if="!loading && rows.length === 0">
							<td colspan="4" class="px-3 py-8 text-center text-gray-400">No Basher sites match.</td>
						</tr>
						<tr v-for="s in rows" :key="s.site" class="border-b border-gray-100 last:border-0">
							<td class="px-3 py-2">{{ s.site }}</td>
							<td class="px-3 py-2">{{ s.client }}</td>
							<td class="px-3 py-2 text-right tabular-nums">{{ s.sms_this_month }}</td>
							<td class="px-3 py-2">
								<div class="flex items-center justify-end gap-2">
									<Badge :theme="s.on ? 'green' : 'gray'" :label="s.on ? 'On' : 'Off'" />
									<Switch
										:model-value="s.on"
										:disabled="busy === s.site"
										:aria-label="`SMS codes for ${s.site}`"
										@update:model-value="(v) => flip(s, v)"
									/>
								</div>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { Badge, Breadcrumbs, FormControl, Switch } from 'frappe-ui';
import { toast } from 'vue-sonner';
import Header from '../../components/Header.vue';
import { call, errorText } from './sms-api.js';

const crumbs = [
	{ label: 'Communications', route: { name: 'Telephony' } },
	{ label: 'SMS', route: { name: 'SMS Sites' } },
	{ label: 'Sites', route: { name: 'SMS Sites' } },
];

const sites = ref([]);
const q = ref('');
const loading = ref(true);
const busy = ref('');
const error = ref('');
const rows = computed(() =>
	sites.value.filter((s) => !q.value || `${s.site} ${s.client}`.toLowerCase().includes(q.value.toLowerCase())),
);

async function load() {
	try {
		sites.value = await call('list_sites');
	} catch (e) {
		error.value = errorText(e);
	} finally {
		loading.value = false;
	}
}

async function flip(s, on) {
	busy.value = s.site;
	try {
		await call('set_sms_codes', { site: s.site, on: on ? 1 : 0 });
		s.on = on;
		toast.success(`SMS codes ${on ? 'on' : 'off'} for ${s.site}. The site follows within a minute.`);
	} catch (e) {
		toast.error(errorText(e));
	} finally {
		busy.value = '';
	}
}

onMounted(load);
</script>
