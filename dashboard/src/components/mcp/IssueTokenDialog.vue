<template>
	<Dialog v-model="show" :options="dialogOptions">
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					label="Label (what this token is for)"
					v-model="form.label"
					required
					autocomplete="off"
				/>
				<FormControl
					label="TTL (minutes, max 1440)"
					type="number"
					v-model="form.ttl"
				/>
				<FormControl
					label="Your password (re-auth to issue)"
					type="password"
					v-model="form.password"
					required
					autocomplete="new-password"
				/>
				<div>
					<label class="text-sm font-medium text-gray-700">Scope (tools this token can call)</label>
					<div class="mt-2 grid grid-cols-2 gap-2">
						<label v-for="t in availableTools" :key="t" class="inline-flex items-center text-sm">
							<input type="checkbox" :value="t" v-model="form.scope" class="mr-2" />
							{{ t }}
						</label>
					</div>
				</div>
				<FormControl
					label="Allowed Release Groups (comma-separated names; leave empty to inherit your full access)"
					type="textarea"
					v-model="form.allowedRGs"
					placeholder="bench-A, bench-B"
				/>
				<FormControl
					label="Allowed Sites (comma-separated full site names; leave empty to inherit your full access)"
					type="textarea"
					v-model="form.allowedSites"
					placeholder="site1.example.com, site2.example.com"
				/>
				<div v-if="newToken" class="rounded border border-amber-300 bg-amber-50 p-3">
					<div class="text-sm font-medium text-amber-900">Copy this token NOW. You won't see it again.</div>
					<code class="mt-1 block break-all text-xs text-amber-900">{{ newToken }}</code>
				</div>
				<ErrorMessage :message="errorMsg" />
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue';
import { Dialog, FormControl, ErrorMessage, call } from 'frappe-ui';

function parseList(raw) {
	if (!raw) return [];
	return raw.split(',').map((s) => s.trim()).filter(Boolean);
}

const AVAILABLE_TOOLS = [
	'clone_bench', 'clone_site', 'move_site_to_release_group',
	'lock_acquire', 'lock_release', 'lock_status',
	'list_release_groups', 'list_sites',
	'list_my_tokens', 'revoke_my_token',
];

const props = defineProps({ modelValue: { type: Boolean, default: false } });
const emit = defineEmits(['update:modelValue', 'issued']);

const show = computed({
	get: () => props.modelValue,
	set: (v) => emit('update:modelValue', v),
});

const form = reactive({
	label: '',
	ttl: 60,
	password: '',
	scope: ['list_release_groups', 'list_sites', 'list_my_tokens'],
	allowedRGs: '',
	allowedSites: '',
});
const submitting = ref(false);
const errorMsg = ref('');
const newToken = ref('');
const availableTools = AVAILABLE_TOOLS;

const dialogOptions = computed(() => ({
	title: 'Issue MCP Token',
	size: 'md',
	actions: [
		{
			label: newToken.value ? 'Done' : 'Issue Token',
			variant: 'solid',
			loading: submitting.value,
			onClick: () => (newToken.value ? close() : submit()),
		},
	],
}));

function close() {
	emit('update:modelValue', false);
	if (newToken.value) emit('issued');
	resetState();
}

function resetState() {
	newToken.value = '';
	errorMsg.value = '';
	form.label = '';
	form.password = '';
	form.ttl = 60;
	form.scope = ['list_release_groups', 'list_sites', 'list_my_tokens'];
	form.allowedRGs = '';
	form.allowedSites = '';
}

watch(() => props.modelValue, (v) => {
	if (v) resetState();
});

async function submit() {
	errorMsg.value = '';
	if (!form.label || !form.password) {
		errorMsg.value = 'Label and password are required';
		return;
	}
	submitting.value = true;
	try {
		const result = await call('press.mcp_server.auth.issue_token', {
			username: window.frappe?.session?.user || '',
			password: form.password,
			scope: form.scope,
			ttl_minutes: parseInt(form.ttl) || 60,
			label: form.label,
			allowed_release_groups: parseList(form.allowedRGs),
			allowed_sites: parseList(form.allowedSites),
		});
		newToken.value = result.token;
	} catch (e) {
		errorMsg.value = e?.messages?.[0] || e?.message || String(e);
	} finally {
		submitting.value = false;
	}
}
</script>
