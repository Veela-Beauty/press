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

				<!-- Risky tools enabled toggle -->
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
									— required for tools like site_run_python, site_run_sql, bench_run_repo_script
								</span>
							</div>
							<div class="mt-0.5 text-xs text-amber-800">
								If you (or your token holder) is not a System User, the token will start in
								<code class="rounded bg-amber-100 px-1">pending</code> state and must be approved
								via Admin Panel → MCP.
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
							<div class="grid grid-cols-1 gap-1 sm:grid-cols-2">
								<label
									v-for="tool in visibleToolsByCategory(cat.id)"
									:key="tool"
									class="inline-flex items-center gap-2 text-sm cursor-pointer hover:bg-white/60 rounded px-1 py-0.5"
									:title="TOOL_CATALOG[tool].desc"
								>
									<input
										type="checkbox"
										:value="tool"
										v-model="form.scope"
									/>
									<span class="font-mono text-xs text-gray-800">{{ tool }}</span>
									<span :class="riskBadgeClass(TOOL_CATALOG[tool].risk)">
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
import { Dialog, FormControl, ErrorMessage, Button, call } from 'frappe-ui';
import {
	TOOL_CATEGORIES,
	TOOL_CATALOG,
	ALL_TOOLS,
	PRESETS,
	riskBadgeClass,
	categoryBorderClass,
} from './_tool_catalog.js';

function parseList(raw) {
	if (!raw) return [];
	return raw.split(',').map((s) => s.trim()).filter(Boolean);
}

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
	riskyToolsEnabled: false,
});
const submitting = ref(false);
const errorMsg = ref('');
const newToken = ref('');
const search = ref('');

const dialogOptions = computed(() => ({
	title: 'Issue MCP Token',
	size: 'xl',
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
	form.riskyToolsEnabled = false;
	search.value = '';
}

watch(() => props.modelValue, (v) => {
	if (v) resetState();
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
	if (!form.label || !form.password) {
		errorMsg.value = 'Label and password are required';
		return;
	}
	if (riskyMissingFlag.value) {
		errorMsg.value =
			'You selected high-risk tools but did not enable risky tools. Either enable them or remove: '
			+ riskyMissingFlag.value.join(', ');
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
