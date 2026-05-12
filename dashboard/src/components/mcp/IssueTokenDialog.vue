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

				<!-- Scope picker: search + presets + grouped categories -->
				<div>
					<div class="flex items-baseline justify-between gap-2 mb-2">
						<label class="text-sm font-medium text-gray-700">
							Scope (tools this token can call)
						</label>
						<div class="text-xs text-gray-500">
							{{ scopeSummary }}
						</div>
					</div>

					<div class="mb-2 flex flex-wrap items-center gap-2">
						<input
							type="text"
							v-model="search"
							placeholder="Search tools..."
							class="flex-1 min-w-[180px] rounded border border-gray-300 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none"
						/>
						<Button v-for="(_, presetName) in PRESETS" :key="presetName"
							size="sm"
							@click="applyPreset(presetName)"
						>
							{{ presetName }}
						</Button>
						<Button size="sm" theme="gray" @click="clearScope">Clear</Button>
					</div>

					<div
						v-if="riskyMissingFlag"
						class="mb-2 rounded border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800"
					>
						<strong>Heads-up:</strong> you've selected high-risk tools
						(<code class="rounded bg-red-100 px-1">{{ riskyMissingFlag.join(', ') }}</code>) but
						<strong>Enable risky tools</strong> is unchecked. Calls to these tools will fail with
						PermissionError until you enable risky tools above.
					</div>
					<div class="space-y-2 max-h-[420px] overflow-y-auto pr-1">
						<div
							v-for="cat in TOOL_CATEGORIES"
							:key="cat.id"
							class="rounded border p-2"
							:class="categoryBorderClass(cat.tone)"
						>
							<div class="flex items-center justify-between mb-1.5">
								<div class="flex items-center gap-2">
									<span class="text-sm font-semibold text-gray-800">
										{{ cat.label }}
									</span>
									<span class="text-xs text-gray-500">
										({{ visibleToolsByCategory(cat.id).length }} visible · {{ selectedInCategory(cat.id) }} selected)
									</span>
								</div>
								<button
									type="button"
									class="text-xs text-blue-600 hover:underline"
									@click="toggleCategory(cat.id)"
								>
									{{ allCategorySelected(cat.id) ? 'Deselect all' : 'Select all' }}
								</button>
							</div>
							<div class="grid grid-cols-1 gap-x-3 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
								<label
									v-for="tool in visibleToolsByCategory(cat.id)"
									:key="tool"
									class="flex items-start gap-2 cursor-pointer hover:bg-white/60 rounded px-1.5 py-1 min-w-0"
									:title="TOOL_CATALOG[tool].desc"
								>
									<input
										type="checkbox"
										:value="tool"
										v-model="form.scope"
										class="mt-0.5 shrink-0"
									/>
									<span class="flex-1 min-w-0">
										<span class="block text-sm text-gray-800 leading-tight">
											{{ TOOL_CATALOG[tool].label || tool }}
										</span>
										<span class="block font-mono text-[10px] text-gray-400 leading-tight truncate">
											{{ tool }}
										</span>
									</span>
									<span :class="riskBadgeClass(TOOL_CATALOG[tool].risk)" class="shrink-0">
										{{ TOOL_CATALOG[tool].risk }}
									</span>
								</label>
							</div>
							<div
								v-if="visibleToolsByCategory(cat.id).length === 0"
								class="text-xs text-gray-400 italic px-1 py-0.5"
							>
								No tools in this category match your search.
							</div>
						</div>
					</div>

				</div>

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
					<MultiSelectChips
						label="Allowed Sites"
						placeholder="Search sites..."
						hint="Empty = inherit your full site access."
						v-model="form.allowedSites"
						:options="siteOptions"
						:loading="loadingSites"
					/>
				</div>
				<HandoverPanel v-if="newToken" :token="newToken" :label="form.label || 'agent'" :scope="form.scope" mode="issued" />
				<ErrorMessage :message="errorMsg" />
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue';
import { Dialog, FormControl, ErrorMessage, Button, call } from 'frappe-ui';
import {
	TOOL_CATEGORIES,
	TOOL_CATALOG,
	ALL_TOOLS,
	PRESETS,
	riskBadgeClass,
	categoryBorderClass,
} from './_tool_catalog.js';
import MultiSelectChips from './MultiSelectChips.vue';
import HandoverPanel from './HandoverPanel.vue';

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
	scope: ['list_release_groups', 'list_sites', 'list_my_tokens'],
	allowedRGs: [],
	allowedSites: [],
	riskyToolsEnabled: false,
});
const submitting = ref(false);
const errorMsg = ref('');
const newToken = ref('');
const search = ref('');
const sendingOtp = ref(false);
const otpSent = ref(false);
const otpCooldown = ref(0);
let otpTimer = null;

// Resource picker state
const rgOptions = ref([]);
const siteOptions = ref([]);
const loadingRGs = ref(false);
const loadingSites = ref(false);

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
	form.scope = ['list_release_groups', 'list_sites', 'list_my_tokens'];
	form.allowedRGs = [];
	form.allowedSites = [];
	form.riskyToolsEnabled = false;
	search.value = '';
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
		}));
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

// ---- Scope picker helpers ----

function visibleToolsByCategory(catId) {
	const q = search.value.trim().toLowerCase();
	return ALL_TOOLS.filter((tool) => {
		if (TOOL_CATALOG[tool].category !== catId) return false;
		if (!q) return true;
		return (
			tool.toLowerCase().includes(q) ||
			(TOOL_CATALOG[tool].desc || '').toLowerCase().includes(q)
		);
	});
}

function selectedInCategory(catId) {
	return form.scope.filter((t) => TOOL_CATALOG[t]?.category === catId).length;
}

function allCategorySelected(catId) {
	const visible = visibleToolsByCategory(catId);
	if (visible.length === 0) return false;
	return visible.every((t) => form.scope.includes(t));
}

function toggleCategory(catId) {
	const visible = visibleToolsByCategory(catId);
	if (allCategorySelected(catId)) {
		form.scope = form.scope.filter((t) => !visible.includes(t));
	} else {
		const set = new Set(form.scope);
		visible.forEach((t) => set.add(t));
		form.scope = Array.from(set);
	}
}

function applyPreset(presetName) {
	form.scope = [...(PRESETS[presetName] || [])];
}

function clearScope() {
	form.scope = [];
}

const riskyMissingFlag = computed(() => {
	if (form.riskyToolsEnabled) return null;
	const highInScope = form.scope.filter(
		(t) => TOOL_CATALOG[t]?.risk === 'high',
	);
	return highInScope.length ? highInScope : null;
});

const scopeSummary = computed(() => {
	if (form.scope.length === 0) return 'No tools selected';
	const lows = form.scope.filter((t) => TOOL_CATALOG[t]?.risk === 'low').length;
	const meds = form.scope.filter((t) => TOOL_CATALOG[t]?.risk === 'medium').length;
	const highs = form.scope.filter((t) => TOOL_CATALOG[t]?.risk === 'high').length;
	const parts = [];
	if (lows) parts.push(`${lows} read-only`);
	if (meds) parts.push(`${meds} state-changing`);
	if (highs) parts.push(`${highs} high-risk`);
	return `${form.scope.length} tools · ${parts.join(' · ')}`;
});

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
		});
		newToken.value = result.token;
	} catch (e) {
		errorMsg.value = e?.messages?.[0] || e?.message || String(e);
	} finally {
		submitting.value = false;
	}
}
</script>
