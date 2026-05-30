<template>
	<div class="flex min-h-screen items-center justify-center bg-gray-50 px-4">
		<div class="w-full max-w-sm rounded-lg border bg-white p-6 shadow-sm">
			<h1 class="text-lg font-semibold text-gray-900">Confirm Admin PIN Change</h1>
			<p class="mt-2 text-sm text-gray-600">
				Confirming activates the new confidential-site admin PIN.
			</p>

			<div v-if="state === 'confirming'" class="mt-5 text-sm text-gray-500">
				Confirming…
			</div>

			<div
				v-else-if="state === 'done'"
				class="mt-5 rounded-md bg-green-50 p-3 text-sm text-green-700"
			>
				The new admin PIN is now active. You can close this page.
			</div>

			<div
				v-else-if="state === 'error'"
				class="mt-5 rounded-md bg-red-50 p-3 text-sm text-red-700"
			>
				{{ errorMessage }}
			</div>

			<Button
				v-if="state === 'error'"
				class="mt-4 w-full"
				variant="solid"
				@click="confirm"
			>
				Try again
			</Button>
		</div>
	</div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { call, Button } from 'frappe-ui';

const route = useRoute();
const state = ref('confirming');
const errorMessage = ref('');

async function confirm() {
	state.value = 'confirming';
	try {
		await call('press.api.security.confirm_admin_pin_change', {
			token: route.params.token,
		});
		state.value = 'done';
	} catch (e) {
		errorMessage.value =
			e?.messages?.join(', ') || e?.message || 'Could not confirm the PIN change.';
		state.value = 'error';
	}
}

onMounted(confirm);
</script>
