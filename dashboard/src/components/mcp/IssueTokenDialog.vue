<template>
	<Dialog v-model="show" :options="dialogOptions">
		<template #body-content>
			<div class="space-y-4">
				<!-- Top section: 3-col grid for form fields -->
				<div class="grid grid-cols-1 gap-4 md:grid-cols-3">
					<FormControl
						label="Label (what this token is for)"
						v-model="form.label"
						required
						autocomplete="off"
					/>
					<FormControl
						label="TTL (days, 1–90)"
						type="number"
						v-model="form.ttlDays"
						:min="1"
						:max="90"
					/>
					<div class="space-y-1">
						<FormControl
							v-if="form.authMethod === 'password'"
							label="Your password (re-auth to issue)"
							type="password"
							v-model="form.password"
							required
							autocomplete="new-password"
						/>
						<div v-else class="flex items-end gap-2">
							<FormControl
								label="Email OTP (6 digits)"
								type="text"
								v-model="form.otp"
								required
								autocomplete="one-time-code"
								class="flex-1"
							/>
							<Button
								size="sm"
								:loading="sendingOtp"
								:disabled="otpCooldown > 0"
								@click="sendOtp"
							>
								{{ otpCooldown > 0 ? `Resend (${otpCooldown}s)` : (otpSent ? 'Resend code' : 'Send code') }}
							</Button>
						</div>
						<button
							type="button"
							class="text-xs text-blue-600 hover:underline"
							@click="toggleAuthMethod"
						>
							{{ form.authMethod === 'password'
								? 'Forgot password? Use email OTP instead'
								: 'Use password instead' }}
						</button>
						<div v-if="otpSent && form.authMethod === 'otp'" class="text-xs text-green-700">
							Code sent — valid for 10 minutes.
						</div>
					</div>
				</div>

				<!-- Risky tools enabled toggle (full width — it's important) -->
				<div class="rounded border border-amber-200 bg-amber-50 p-3">
					<label class="flex items-start gap-2 cursor-pointer">
						<input
							type="checkbox"
							v-model="form.riskyToolsEnabled"
							class="mt-0.5"
						/>
						<div class="flex-1">
							<div class="text-sm font-medium text-amber-900">
								Enable risky (high-risk) tools
								<span class="text-xs font-normal text-amber-700">
									— required for site_run_python, site_run_sql, bench_run_repo_script
								</span>
							</div>
							<div class="mt-0.5 text-xs text-amber-800">
								Non-System Users get a <code class="rounded bg-amber-100 px-1">pending</code> token
								that must be approved via Admin Panel → MCP.
							</div>
						</div>
					</label>
				</div>

				<!-- Scope picker: search + presets + grouped categories (ToolScopePicker.vue) -->
				<ToolScopePicker v-model="form.scope">
					<template #notice>
						<div
							v-if="riskyMissingFlag"
							class="mb-2 rounded border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800"
						>
							<strong>Heads-up:</strong> you've selected high-risk tools
							(<code class="rounded bg-red-100 px-1">{{ riskyMissingFlag.join(', ') }}</code>) but
							<strong>Enable risky tools</strong> is unchecked. Calls to these tools will fail with
							PermissionError until you enable risky tools above.
						</div>
					</template>
				</ToolScopePicker>

				<!-- Resource scoping: 2-col multi-select chip pickers -->
				<div class="grid grid-cols-1 gap-4 md:grid-cols-2">
					<MultiSelectChips
						label="Allowed Release Groups"
						placeholder="Search benches by name or title..."
						hint="Empty = inherit your full RG access."
						v-model="form.allowedRGs"
						:options="rgOptions"
						:loading="loadingRGs"
					/>
					<div class="space-y-3">
						<MultiSelectChips
							label="Allowed Sites"
							placeholder="Search sites..."
							hint="Empty = inherit your full site access. Confidential sites are never included by empty."
							v-model="form.allowedSites"
							:options="siteOptions"
							:loading="loadingSites"
						/>
						<div v-if="confidentialPicked.length" class="space-y-1">
							<FormControl
								label="Admin PIN"
								type="password"
								v-model="form.confidentialPin"
								required
								autocomplete="new-password"
							/>
							<div class="text-xs text-gray-500">
								Unlocks <strong>{{ confidentialPicked.map(shortSite).join(', ') }}</strong> for this
								token. The agent never sees the PIN.
							</div>
						</div>
					</div>
				</div>
				<HandoverPanel v-if="newToken" :token="newToken" :label="form.label || 'agent'" :scope="form.scope" mode="issued" />
				<ErrorMessage :message="errorMsg" />
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue';
import { Dialog, FormControl, ErrorMessage, Button } from 'frappe-ui';
import call from './teamCall.js';
import { TOOL_CATALOG, PRESETS } from './_tool_catalog.js';
import MultiSelectChips from './MultiSelectChips.vue';
import HandoverPanel from './HandoverPanel.vue';
import ToolScopePicker from './ToolScopePicker.vue';

// A new token opens on the deploy tools (owner, 25 Nov 2026); the member's role still limits what it reaches.
const DEFAULT_PRESET = 'All deploy';

const props = defineProps({ modelValue: { type: Boolean, default: false } });
const emit = defineEmits(['update:modelValue', 'issued']);

const show = computed({
	get: () => props.modelValue,
	set: (v) => emit('update:modelValue', v),
});

const form = reactive({
	label: '',
	ttlDays: 7,
	authMethod: 'password', // 'password' | 'otp'
	password: '',
	otp: '',
	scope: [...PRESETS[DEFAULT_PRESET]],
	allowedRGs: [],
	allowedSites: [],
	riskyToolsEnabled: false,
	confidentialPin: '',
});
const submitting = ref(false);
const errorMsg = ref('');
const newToken = ref('');
const sendingOtp = ref(false);
const otpSent = ref(false);
const otpCooldown = ref(0);
let otpTimer = null;

// Resource picker state
const rgOptions = ref([]);
const siteOptions = ref([]);
const loadingRGs = ref(false);
const loadingSites = ref(false);
const confidentialSites = ref(new Set());

const dialogOptions = computed(() => ({
	title: 'Issue MCP Token',
	size: '4xl',
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
	form.otp = '';
	form.authMethod = 'password';
	form.ttlDays = 7;
	form.scope = [...PRESETS[DEFAULT_PRESET]];
	form.allowedRGs = [];
	form.allowedSites = [];
	form.riskyToolsEnabled = false;
	form.confidentialPin = '';
	otpSent.value = false;
	otpCooldown.value = 0;
	if (otpTimer) { clearInterval(otpTimer); otpTimer = null; }
}

function toggleAuthMethod() {
	form.authMethod = form.authMethod === 'password' ? 'otp' : 'password';
	form.password = '';
	form.otp = '';
	errorMsg.value = '';
}

async function sendOtp() {
	if (otpCooldown.value > 0) return;
	errorMsg.value = '';
	sendingOtp.value = true;
	try {
		await call('press.mcp_server.auth.request_email_otp', {
			username: window.frappe?.session?.user || '',
		});
		otpSent.value = true;
		otpCooldown.value = 30;
		otpTimer = setInterval(() => {
			otpCooldown.value -= 1;
			if (otpCooldown.value <= 0) { clearInterval(otpTimer); otpTimer = null; }
		}, 1000);
	} catch (e) {
		errorMsg.value = e?.messages?.[0] || e?.message || String(e);
	} finally {
		sendingOtp.value = false;
	}
}

async function loadResourceOptions() {
	loadingRGs.value = true;
	loadingSites.value = true;
	try {
		const [rgs, sites] = await Promise.all([
			call('press.api.team_resources.list_my_release_groups'),
			call('press.api.team_resources.list_my_sites'),
		]);
		rgOptions.value = (rgs || []).map((r) => ({
			value: r.name,
			label: r.title || r.name,
			sub: r.title && r.title !== r.name ? r.name : '',
		}));
		siteOptions.value = (sites || []).map((s) => ({
			value: s.name,
			label: s.name,
			sub: s.group ? `bench: ${s.group}` : '',
			tag: s.is_confidential ? 'confidential' : '',
			icon: s.is_confidential ? 'lock' : '',
		}));
		confidentialSites.value = new Set((sites || []).filter((s) => s.is_confidential).map((s) => s.name));
	} catch (e) {
		// non-fatal — user can still skip resource scoping
		console.warn('Failed to load RG/Site options:', e);
	} finally {
		loadingRGs.value = false;
		loadingSites.value = false;
	}
}

watch(() => props.modelValue, (v) => {
	if (v) {
		resetState();
		loadResourceOptions();
	}
});


const riskyMissingFlag = computed(() => {
	if (form.riskyToolsEnabled) return null;
	const highInScope = form.scope.filter(
		(t) => TOOL_CATALOG[t]?.risk === 'high',
	);
	return highInScope.length ? highInScope : null;
});

const confidentialPicked = computed(() =>
	form.allowedSites.filter((name) => confidentialSites.value.has(name)),
);

function shortSite(name) {
	return name.split('.')[0];
}


// ---- Submit ----

async function submit() {
	errorMsg.value = '';
	if (!form.label) {
		errorMsg.value = 'Label is required';
		return;
	}
	if (form.authMethod === 'password' && !form.password) {
		errorMsg.value = 'Password is required (or switch to email OTP)';
		return;
	}
	if (form.authMethod === 'otp' && !form.otp) {
		errorMsg.value = 'Enter the 6-digit code we sent to your email';
		return;
	}
	if (riskyMissingFlag.value) {
		errorMsg.value =
			'You selected high-risk tools but did not enable risky tools. Either enable them or remove: '
			+ riskyMissingFlag.value.join(', ');
		return;
	}
	if (confidentialPicked.value.length && !form.confidentialPin) {
		errorMsg.value = 'Enter the Admin PIN to unlock ' + confidentialPicked.value.map(shortSite).join(', ');
		return;
	}
	const days = Math.max(1, Math.min(90, parseInt(form.ttlDays) || 7));
	submitting.value = true;
	try {
		const result = await call('press.mcp_server.auth.issue_token', {
			username: window.frappe?.session?.user || '',
			password: form.authMethod === 'password' ? form.password : '',
			otp: form.authMethod === 'otp' ? form.otp : '',
			scope: form.scope,
			ttl_minutes: days * 24 * 60,
			label: form.label,
			allowed_release_groups: form.allowedRGs,
			allowed_sites: form.allowedSites,
			risky_tools_enabled: form.riskyToolsEnabled ? 1 : 0,
			confidential_pin: confidentialPicked.value.length ? form.confidentialPin : '',
		});
		newToken.value = result.token;
	} catch (e) {
		form.confidentialPin = '';
		errorMsg.value = e?.messages?.[0] || e?.message || String(e);
	} finally {
		submitting.value = false;
	}
}
</script>
