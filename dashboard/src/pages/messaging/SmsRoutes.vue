<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header><Breadcrumbs :items="crumbs" /></Header>
		</div>
		<div class="flex-1 overflow-auto p-5">
			<div class="mb-4 flex items-center gap-2">
				<h1 class="text-lg font-semibold text-gray-900">SMS routes</h1>
				<div class="flex-1" />
				<Button variant="solid" label="Save" :loading="saving" @click="save" />
			</div>
			<div v-if="error" class="rounded-lg border border-red-200 bg-red-50 p-4 text-base text-red-700">
				{{ error }}
			</div>
			<div v-else class="overflow-x-auto rounded-lg border border-gray-200">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-200 bg-gray-50 text-left text-xs text-gray-500">
							<th class="px-3 py-2 font-medium">Country</th>
							<th class="px-3 py-2 font-medium">Provider</th>
							<th class="px-3 py-2 font-medium">Sender</th>
							<th class="px-3 py-2 text-right font-medium">Price per SMS (USD)</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="r in rows" :key="r.country" class="border-b border-gray-100 last:border-0">
							<td class="px-3 py-2">{{ countryName(r.country) }}</td>
							<td class="px-3 py-2">
								<FormControl
									v-model="r.provider"
									type="select"
									:options="providers"
									:aria-label="`Provider for ${countryName(r.country)}`"
									class="w-48 text-sm"
								/>
							</td>
							<td class="px-3 py-2 text-gray-500">{{ r.provider === 'Google Firebase' ? "Google's own" : '' }}</td>
							<td class="px-3 py-2">
								<div class="flex justify-end">
									<FormControl
										v-model="r.price"
										type="number"
										step="0.01"
										min="0"
										:aria-label="`Price for ${countryName(r.country)}`"
										class="w-28 text-sm"
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
import { onMounted, ref } from 'vue';
import { Breadcrumbs, Button, FormControl } from 'frappe-ui';
import { toast } from 'vue-sonner';
import Header from '../../components/Header.vue';
import { call, countryName, errorText } from './sms-api.js';

const crumbs = [
	{ label: 'Communications', route: { name: 'Telephony' } },
	{ label: 'SMS', route: { name: 'SMS Sites' } },
	{ label: 'Routes', route: { name: 'SMS Routes' } },
];

const rows = ref([]);
const providers = ref([]);
const saving = ref(false);
const error = ref('');

async function load() {
	try {
		const out = await call('get_routes');
		rows.value = out.rows;
		providers.value = out.providers;
	} catch (e) {
		error.value = errorText(e);
	}
}

async function save() {
	saving.value = true;
	try {
		await call('save_routes', { rows: JSON.stringify(rows.value) });
		toast.success('Routes saved. They apply to SMS sent from now on.');
	} catch (e) {
		toast.error(errorText(e));
	} finally {
		saving.value = false;
	}
}

onMounted(load);
</script>
