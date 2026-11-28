<template>
	<!-- PRS-SP-22: the site logins' "Confirm it's you" with three ways, before a token is shown, copied, reissued or
	     given more tools. press.mcp_server.token_confirm checks the code and opens 10 minutes. -->
	<Dialog v-model="show" :options="{ title: `Confirm it's you`, actions }">
		<template #body-content>
			<div class="space-y-4">
				<p v-if="reason" class="-mt-2 text-sm text-gray-600">{{ reason }}</p>
				<div class="inline-flex overflow-hidden rounded border border-gray-200 text-sm">
					<button
						v-for="(name, key, i) in WAYS"
						:key="key"
						type="button"
						:class="[
							'px-3 py-1.5',
							i > 0 && 'border-l border-gray-200',
							way === key ? 'bg-gray-900 text-white' : 'bg-white text-gray-700 hover:bg-gray-50',
						]"
						@click="pick(key)"
					>
						{{ name }}
					</button>
				</div>

				<template v-if="way === 'app'">
					<FormControl
						v-if="status.app === 'ready'"
						v-model="code"
						label="Enter the 6-digit code from your authenticator app"
						inputmode="numeric"
						autocomplete="one-time-code"
						maxlength="6"
						@keydown.enter="verify"
					/>
					<p v-else class="text-sm text-gray-600">
						<template v-if="status.app === 'new'">
							Your authenticator app was linked during this login, so it does not count here yet.
						</template>
						<template v-else>No authenticator app is linked to your account.</template>
						Use an email code or your password.
					</p>
				</template>

				<template v-else-if="way === 'email'">
					<div class="flex items-end gap-2">
						<FormControl
							v-model="code"
							:label="sent ? `Enter the 6-digit code we emailed to ${status.email}` : 'Email code'"
							inputmode="numeric"
							autocomplete="one-time-code"
							maxlength="6"
							class="flex-1"
							@keydown.enter="verify"
						/>
						<Button :loading="sending" :disabled="cooldown > 0" @click="sendCode">
							{{ cooldown > 0 ? `Resend (${cooldown}s)` : sent ? 'Resend code' : 'Send code' }}
						</Button>
					</div>
				</template>

				<FormControl
					v-else
					v-model="password"
					label="Your password"
					type="password"
					autocomplete="current-password"
					@keydown.enter="verify"
				/>

				<ErrorMessage :message="error" />
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue';
import { Dialog, FormControl, ErrorMessage, Button } from 'frappe-ui';
import call from './teamCall.js';

const WAYS = { app: 'Authenticator app', email: 'Email code', password: 'Password' };

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	reason: { type: String, default: '' },
});
const emit = defineEmits(['update:modelValue', 'confirmed']);
const show = computed({
	get: () => props.modelValue,
	set: (v) => emit('update:modelValue', v),
});

const status = ref({ app: 'none', email: '' });
const way = ref('app');
const code = ref('');
const password = ref('');
const error = ref('');
const busy = ref(false);
const sending = ref(false);
const sent = ref(false);
const cooldown = ref(0);
let timer = null;

const actions = computed(() => [
	{ label: 'Cancel', variant: 'outline', onClick: () => (show.value = false) },
	{
		label: 'Verify',
		variant: 'solid',
		loading: busy.value,
		disabled: way.value === 'app' && status.value.app !== 'ready',
		onClick: verify,
	},
]);

function pick(key) {
	way.value = key;
	code.value = '';
	password.value = '';
	error.value = '';
}

function stopTimer() {
	if (timer) clearInterval(timer);
	timer = null;
}

async function sendCode() {
	error.value = '';
	sending.value = true;
	try {
		await call('press.mcp_server.auth.request_email_otp', { username: '' });
		sent.value = true;
		cooldown.value = 30;
		stopTimer();
		timer = setInterval(() => {
			cooldown.value -= 1;
			if (cooldown.value <= 0) stopTimer();
		}, 1000);
	} catch (e) {
		error.value = e?.messages?.[0] || e?.message || String(e);
	} finally {
		sending.value = false;
	}
}

async function verify() {
	error.value = '';
	busy.value = true;
	try {
		await call('press.mcp_server.token_confirm.confirm', {
			method: way.value,
			code: code.value,
			password: password.value,
		});
		password.value = '';
		emit('confirmed');
	} catch (e) {
		error.value = e?.messages?.[0] || e?.message || String(e);
	} finally {
		busy.value = false;
	}
}

watch(
	() => props.modelValue,
	async (open) => {
		if (!open) return;
		pick('app');
		sent.value = false;
		cooldown.value = 0;
		stopTimer();
		try {
			status.value = await call('press.mcp_server.token_confirm.confirm_status');
		} catch (e) {
			error.value = e?.messages?.[0] || e?.message || String(e);
		}
		way.value = status.value.app === 'ready' ? 'app' : 'email';
	},
);

onBeforeUnmount(stopTimer);
</script>
