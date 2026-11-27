<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header><Breadcrumbs :items="crumbs" /></Header>
		</div>
		<div class="flex-1 overflow-auto p-5">
			<div class="mb-4 flex items-center gap-2">
				<h1 class="text-lg font-semibold text-gray-900">SMS cost by client</h1>
				<div class="flex-1" />
				<FormControl v-model="month" type="month" class="w-40 text-sm" />
				<Button label="Export CSV" @click="exportCsv" />
			</div>
			<div v-if="error" class="rounded-lg border border-red-200 bg-red-50 p-4 text-base text-red-700">
				{{ error }}
			</div>
			<div v-else class="overflow-x-auto rounded-lg border border-gray-200">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-200 bg-gray-50 text-left text-xs text-gray-500">
							<th class="px-3 py-2 font-medium">Client</th>
							<th class="px-3 py-2 text-right font-medium">Sites</th>
							<th class="px-3 py-2 text-right font-medium">SMS</th>
							<th class="px-3 py-2 text-right font-medium">Cost (USD)</th>
						</tr>
					</thead>
					<tbody>
						<tr v-if="loaded && data.rows.length === 0">
							<td colspan="4" class="px-3 py-8 text-center text-gray-400">No SMS in this month.</td>
						</tr>
						<tr v-for="r in data.rows" :key="r.team" class="border-b border-gray-100">
							<td class="px-3 py-2">{{ r.client }}</td>
							<td class="px-3 py-2 text-right tabular-nums">{{ r.sites }}</td>
							<td class="px-3 py-2 text-right tabular-nums">{{ r.sms }}</td>
							<td class="px-3 py-2 text-right tabular-nums">{{ money(r.cost_usd) }}</td>
						</tr>
						<tr v-if="data.rows.length" class="bg-gray-50 font-semibold">
							<td class="px-3 py-2">Total</td>
							<td class="px-3 py-2 text-right tabular-nums">{{ data.total.sites }}</td>
							<td class="px-3 py-2 text-right tabular-nums">{{ data.total.sms }}</td>
							<td class="px-3 py-2 text-right tabular-nums">{{ money(data.total.cost_usd) }}</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue';
import { Breadcrumbs, Button, FormControl } from 'frappe-ui';
import Header from '../../components/Header.vue';
import { call, errorText, money, thisMonth } from './sms-api.js';

const crumbs = [
	{ label: 'Communications', route: { name: 'Telephony' } },
	{ label: 'SMS', route: { name: 'SMS Sites' } },
	{ label: 'Cost by client', route: { name: 'SMS Cost by Client' } },
];

const month = ref(thisMonth());
const data = ref({ rows: [], total: { sites: 0, sms: 0, cost_usd: 0 } });
const loaded = ref(false);
const error = ref('');

async function load() {
	try {
		data.value = await call('cost_by_client', { month: month.value });
		loaded.value = true;
	} catch (e) {
		error.value = errorText(e);
	}
}

function exportCsv() {
	const { rows, total } = data.value;
	const lines = [
		['Client', 'Sites', 'SMS', 'Cost (USD)'],
		...rows.map((r) => [r.client, r.sites, r.sms, r.cost_usd.toFixed(2)]),
		['Total', total.sites, total.sms, total.cost_usd.toFixed(2)],
	];
	const csv = lines.map((l) => l.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
	const a = document.createElement('a');
	a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
	a.download = `sms-cost-by-client-${month.value}.csv`;
	a.click();
	URL.revokeObjectURL(a.href);
}

watch(month, load);
onMounted(load);
</script>
