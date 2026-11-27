<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header><Breadcrumbs :items="crumbs" /></Header>
		</div>
		<div class="flex-1 overflow-auto p-5">
			<div class="mb-4 flex items-center gap-2">
				<h1 class="text-lg font-semibold text-gray-900">SMS log</h1>
				<div class="flex-1" />
				<FormControl v-model="team" type="select" :options="teamOptions" class="w-48 text-sm" />
				<FormControl v-model="month" type="month" class="w-40 text-sm" />
			</div>
			<div v-if="error" class="rounded-lg border border-red-200 bg-red-50 p-4 text-base text-red-700">
				{{ error }}
			</div>
			<div v-else class="overflow-x-auto rounded-lg border border-gray-200">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-200 bg-gray-50 text-left text-xs text-gray-500">
							<th class="px-3 py-2 font-medium">Time</th>
							<th class="px-3 py-2 font-medium">Site</th>
							<th class="px-3 py-2 font-medium">Client</th>
							<th class="px-3 py-2 font-medium">Country</th>
							<th class="px-3 py-2 font-medium">Provider</th>
							<th class="px-3 py-2 text-right font-medium">Cost (USD)</th>
						</tr>
					</thead>
					<tbody>
						<tr v-if="loaded && rows.length === 0">
							<td colspan="6" class="px-3 py-8 text-center text-gray-400">No SMS in this month.</td>
						</tr>
						<tr v-for="(r, i) in rows" :key="i" class="border-b border-gray-100 last:border-0">
							<td class="whitespace-nowrap px-3 py-2 tabular-nums">{{ r.time }}</td>
							<td class="px-3 py-2">{{ r.site }}</td>
							<td class="px-3 py-2">{{ r.client }}</td>
							<td class="px-3 py-2">{{ r.country }}</td>
							<td class="px-3 py-2">{{ r.provider }}</td>
							<td class="px-3 py-2 text-right tabular-nums">{{ money(r.cost_usd) }}</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { Breadcrumbs, FormControl } from 'frappe-ui';
import Header from '../../components/Header.vue';
import { call, errorText, money, thisMonth } from './sms-api.js';

const crumbs = [
	{ label: 'Communications', route: { name: 'Telephony' } },
	{ label: 'SMS', route: { name: 'SMS Sites' } },
	{ label: 'Log', route: { name: 'SMS Log' } },
];

const rows = ref([]);
const month = ref(thisMonth());
const team = ref('');
const teams = ref([]);
const loaded = ref(false);
const error = ref('');
const teamOptions = computed(() => [{ label: 'All clients', value: '' }, ...teams.value]);

async function load() {
	try {
		rows.value = await call('sms_log', { month: month.value, team: team.value || null, limit: 200 });
		const cost = await call('cost_by_client', { month: month.value });
		teams.value = cost.rows.map((r) => ({ value: r.team, label: r.client }));
		loaded.value = true;
	} catch (e) {
		error.value = errorText(e);
	}
}

watch([month, team], load);
onMounted(load);
</script>
