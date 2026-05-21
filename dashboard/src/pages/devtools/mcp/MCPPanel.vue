<template>
	<div class="mx-auto max-w-6xl space-y-6 p-6">
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-2xl font-semibold">MCP Tokens & Activity</h1>
				<p class="text-sm text-gray-600">Manage MCP access tokens for AI agents and view recent calls.</p>
			</div>
			<Button variant="solid" @click="showIssueDialog = true">
				<template #prefix><FeatherIcon name="plus" class="h-4 w-4" /></template>
				Issue Token
			</Button>
		</div>

		<MCPTopTabs ref="topTabs" @issue="showIssueDialog = true" />

		<!-- Test Tool Call — pick a tool, fill canonical args from schema, run -->
		<section class="rounded border border-gray-200 bg-white">
			<div class="flex items-center justify-between border-b border-gray-200 p-4">
				<div class="text-base font-semibold">Test Tool Call</div>
				<div class="text-xs text-gray-500">
					Runs against your own user. Use a token to test scope/risk gating.
				</div>
			</div>
			<div class="space-y-3 p-4">
				<div class="grid grid-cols-1 gap-3 md:grid-cols-2">
					<label class="text-xs text-gray-600">
						Token
						<select v-model="testToken" class="mt-1 block w-full rounded border border-gray-300 px-2 py-1.5 text-sm">
							<option value="">— pick a token —</option>
							<option v-for="t in tokens" :key="t.name" :value="t.plaintext_hint || t.name">
								{{ t.label }} ({{ t.name }})
							</option>
						</select>
						<span class="mt-1 block text-[10px] text-gray-500">Stored tokens only carry hashes; paste a full token below if needed.</span>
					</label>
					<label class="text-xs text-gray-600">
						Token (paste plaintext if dropdown can't supply)
						<input
							v-model="testTokenPlaintext"
							type="text"
							placeholder="mcp_..."
							class="mt-1 block w-full rounded border border-gray-300 px-2 py-1.5 font-mono text-xs"
						/>
					</label>
				</div>
				<label class="block text-xs text-gray-600">
					Tool
					<select
						v-model="testTool"
						@change="onTestToolChange"
						class="mt-1 block w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
					>
						<option value="">— pick a tool —</option>
						<option v-for="name in availableTools" :key="name" :value="name">
							{{ name }} {{ toolRisk(name) === 'high' ? '⚠️' : '' }}
						</option>
					</select>
				</label>

				<div v-if="testToolSchema" class="rounded border border-gray-200 bg-gray-50 p-3">
					<div class="mb-2 text-xs font-semibold text-gray-700">{{ testToolDescription }}</div>
					<div v-for="(prop, key) in testToolSchema.properties" :key="key" class="mb-2">
						<label class="block text-xs text-gray-600">
							<span class="font-mono font-medium">{{ key }}</span>
							<span v-if="isRequired(key)" class="ml-1 text-red-600">*</span>
							<span class="ml-2 text-[10px] text-gray-500">{{ prop.type }}</span>
						</label>
						<input
							v-if="prop.type === 'boolean'"
							type="checkbox"
							v-model="testArgs[key]"
							class="mt-1"
						/>
						<textarea
							v-else-if="prop.type === 'object' || prop.type === 'array' || key === 'code' || key === 'query'"
							v-model="testArgs[key]"
							:placeholder="prop.description || ''"
							rows="3"
							class="mt-1 block w-full rounded border border-gray-300 px-2 py-1.5 font-mono text-xs"
						/>
						<select
							v-else-if="prop.enum"
							v-model="testArgs[key]"
							class="mt-1 block w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
						>
							<option value="">—</option>
							<option v-for="v in prop.enum" :key="v" :value="v">{{ v }}</option>
						</select>
						<input
							v-else
							v-model="testArgs[key]"
							type="text"
							:placeholder="prop.description || ''"
							class="mt-1 block w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
						/>
						<div v-if="prop.description" class="mt-0.5 text-[10px] text-gray-500">{{ prop.description }}</div>
					</div>
				</div>

				<div class="flex items-center justify-end gap-2">
					<Button @click="onRunTest" :loading="testRunning" :disabled="!canRunTest" variant="solid">
						Run
					</Button>
				</div>

				<div v-if="testResult" class="rounded border border-gray-200 bg-gray-50 p-3">
					<div class="mb-1 flex items-center gap-2">
						<span :class="testResult.ok ? 'text-green-700' : 'text-red-700'" class="text-xs font-semibold">
							{{ testResult.ok ? '✓ Success' : '✗ ' + (testResult.error_type || 'Error') }}
						</span>
						<span class="text-[10px] text-gray-500">{{ testResult.duration_ms }}ms</span>
					</div>
					<pre class="max-h-64 overflow-auto whitespace-pre-wrap break-words text-[11px] text-gray-700">{{ formatTestResult(testResult) }}</pre>
				</div>
			</div>
		</section>

		<IssueTokenDialog v-model="showIssueDialog" @issued="onTokenIssued" />
	</div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { Button, FeatherIcon, call, toast } from 'frappe-ui';
import IssueTokenDialog from '../../../components/mcp/IssueTokenDialog.vue';
import MCPTopTabs from '../../../components/mcp/MCPTopTabs.vue';
import { TOOL_CATALOG } from '../../../components/mcp/_tool_catalog.js';

// Token list — still needed locally for the Test Tool Call dropdown.
// MCPActiveTokensBody owns its own copy for the cards UI.
const tokens = ref([]);
const showIssueDialog = ref(false);
const topTabs = ref(null);

async function onTokenIssued() {
	// Refresh BOTH local list (for Test Tool Call dropdown) AND the
	// Active Tokens tab body's list (for the cards).
	await loadTokens();
	topTabs.value?.refreshTokens?.();
}

// ---- Test Tool Call form state ----
const testToken = ref('');
const testTokenPlaintext = ref('');
const testTool = ref('');
const testToolSchema = ref(null);
const testToolDescription = ref('');
const testToolRequired = ref([]);
const testArgs = reactive({});
const testRunning = ref(false);
const testResult = ref(null);

const availableTools = computed(() => Object.keys(TOOL_CATALOG).sort());

function toolRisk(name) {
	return TOOL_CATALOG[name]?.risk || 'medium';
}

function isRequired(key) {
	return testToolRequired.value.includes(key);
}

async function onTestToolChange() {
	testResult.value = null;
	testToolSchema.value = null;
	testToolRequired.value = [];
	Object.keys(testArgs).forEach((k) => delete testArgs[k]);

	const token = testTokenPlaintext.value.trim() || testToken.value.trim();
	if (!testTool.value || !token) return;
	try {
		const r = await call('press.mcp_server.server.handle', {
			tool: 'help',
			args: { tool: testTool.value },
			token,
		});
		const data = r?.data || r;
		if (data && data.args_schema) {
			testToolSchema.value = data.args_schema;
			testToolDescription.value = data.description || '';
			testToolRequired.value = data.args_schema.required || data.required_args || [];
		}
	} catch (e) {
		testResult.value = {
			ok: false,
			error: e?.messages?.[0] || e?.message || String(e),
			error_type: 'HelpFetchError',
			duration_ms: 0,
		};
	}
}

const canRunTest = computed(() => {
	if (testRunning.value) return false;
	if (!testTool.value) return false;
	const token = testTokenPlaintext.value.trim() || testToken.value.trim();
	if (!token) return false;
	for (const key of testToolRequired.value) {
		const v = testArgs[key];
		if (v === undefined || v === null || v === '') return false;
	}
	return true;
});

async function onRunTest() {
	testRunning.value = true;
	testResult.value = null;
	const token = testTokenPlaintext.value.trim() || testToken.value.trim();
	// Convert any JSON-shaped strings (for object/array args) before sending
	const argsOut = {};
	for (const [k, v] of Object.entries(testArgs)) {
		if (v === undefined || v === null || v === '') continue;
		const prop = testToolSchema.value?.properties?.[k];
		if (prop && (prop.type === 'object' || prop.type === 'array') && typeof v === 'string') {
			try {
				argsOut[k] = JSON.parse(v);
			} catch (e) {
				testResult.value = {
					ok: false,
					error: `Arg '${k}' must be valid JSON for type ${prop.type}: ${e.message}`,
					error_type: 'ArgParseError',
					duration_ms: 0,
				};
				testRunning.value = false;
				return;
			}
		} else {
			argsOut[k] = v;
		}
	}
	try {
		const r = await call('press.mcp_server.server.handle', {
			tool: testTool.value,
			args: argsOut,
			token,
		});
		testResult.value = r?.data ? r : { ok: true, data: r, duration_ms: 0 };
	} catch (e) {
		testResult.value = {
			ok: false,
			error: e?.messages?.[0] || e?.message || String(e),
			error_type: 'CallError',
			duration_ms: 0,
		};
	} finally {
		testRunning.value = false;
		// Recent Calls tab has its own 10s polling — user will see their
		// test land there within ~10s without us needing to force a refresh.
	}
}

function formatTestResult(r) {
	if (!r) return '';
	if (r.ok === false) return r.error || JSON.stringify(r, null, 2);
	return JSON.stringify(r.data ?? r, null, 2);
}

// loadTokens still lives here because the Test Tool Call dropdown needs
// the list. Token cards / revoke / reissue / scope details all moved to
// MCPActiveTokensBody.vue.
async function loadTokens() {
	try {
		tokens.value = await call('press.mcp_server.dashboard.list_my_tokens');
	} catch (e) {
		toast.error('Failed to load tokens: ' + (e?.message || e));
	}
}

onMounted(() => {
	loadTokens();
});
</script>
