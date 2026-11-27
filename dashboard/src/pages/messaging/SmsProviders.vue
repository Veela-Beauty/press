<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header><Breadcrumbs :items="crumbs" /></Header>
		</div>
		<div class="flex-1 overflow-auto p-5">
			<div class="mb-4 flex items-center gap-2">
				<h1 class="text-lg font-semibold text-gray-900">SMS providers</h1>
				<div class="flex-1" />
				<Button variant="solid" label="Add provider" @click="edit(null)" />
			</div>
			<div v-if="error" class="rounded-lg border border-red-200 bg-red-50 p-4 text-base text-red-700">
				{{ error }}
			</div>
			<div v-else class="overflow-x-auto rounded-lg border border-gray-200">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-200 bg-gray-50 text-left text-xs text-gray-500">
							<th class="px-3 py-2 font-medium">Provider</th>
							<th class="px-3 py-2 font-medium">How it sends</th>
							<th class="px-3 py-2 font-medium">Sender</th>
							<th class="px-3 py-2 font-medium">Status</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="r in rows"
							:key="r.name"
							class="border-b border-gray-100 last:border-0"
							:class="{ 'cursor-pointer hover:bg-gray-50': r.mode !== 'firebase' }"
							@click="edit(r)"
						>
							<td class="px-3 py-2">{{ r.name }}</td>
							<td class="px-3 py-2">{{ r.mode === 'firebase' ? 'From the phone' : 'From Press' }}</td>
							<td class="px-3 py-2 text-gray-500">{{ r.mode === 'firebase' ? "Google's own" : r.sender_name }}</td>
							<td class="px-3 py-2"><Badge v-bind="status(r)" /></td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<Dialog v-model="open" :options="{ title: form.exists ? form.provider_name : 'Add provider' }">
			<template #body-content>
				<div class="flex flex-col gap-3">
					<FormControl v-model="form.provider_type" type="select" label="Type" :options="types" />
					<FormControl v-if="!form.exists" v-model="form.provider_name" type="text" label="Provider name" />
					<FormControl v-model="form.sender_name" type="text" label="Sender name" />
					<FormControl v-model="form.username" type="text" label="Username" />
					<FormControl v-model="form.password" type="password" label="Password" />
					<FormControl v-model="testTo" type="text" label="Test to" placeholder="+201012345678" />
					<div class="mt-2 flex items-center justify-end gap-2">
						<Button label="Send a test SMS" :disabled="!form.exists || !testTo" @click="test" />
						<Button variant="solid" label="Save" @click="save" />
					</div>
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { Badge, Breadcrumbs, Button, Dialog, FormControl } from 'frappe-ui';
import { toast } from 'vue-sonner';
import Header from '../../components/Header.vue';
import { call, errorText } from './sms-api.js';

const crumbs = [
	{ label: 'Communications', route: { name: 'Telephony' } },
	{ label: 'SMS', route: { name: 'SMS Sites' } },
	{ label: 'Providers', route: { name: 'SMS Providers' } },
];

const types = ['smseg'];
const rows = ref([]);
const open = ref(false);
const form = ref({});
const testTo = ref('');
const error = ref('');
const blank = () => ({
	exists: false,
	provider_name: '',
	provider_type: 'smseg',
	sender_name: 'Basher',
	username: '',
	password: '',
	enabled: 1,
});

const status = (r) => {
	if (r.mode === 'firebase') return { theme: 'green', label: 'Working' };
	return r.has_login && r.enabled ? { theme: 'green', label: 'Ready' } : { theme: 'orange', label: 'Login not added' };
};

async function load() {
	try {
		rows.value = await call('list_providers');
	} catch (e) {
		error.value = errorText(e);
	}
}

function edit(row) {
	if (row && row.mode === 'firebase') return;
	testTo.value = '';
	form.value = row
		? {
				exists: true,
				provider_name: row.name,
				provider_type: row.provider_type,
				sender_name: row.sender_name,
				username: '',
				password: '',
				enabled: row.enabled,
			}
		: blank();
	open.value = true;
}

async function save() {
	try {
		const { exists, ...payload } = form.value;
		if (!payload.username) delete payload.username;
		await call('save_provider', payload);
		open.value = false;
		toast.success(`${payload.provider_name} saved. Pick it for a country on Routes.`);
		load();
	} catch (e) {
		toast.error(errorText(e));
	}
}

async function test() {
	try {
		const out = await call('test_provider', { provider_name: form.value.provider_name, mobile: testTo.value });
		if (out.ok) toast.success(`Test SMS handed to ${form.value.provider_name}.`);
		else toast.error(out.detail);
	} catch (e) {
		toast.error(errorText(e));
	}
}

onMounted(load);
</script>
