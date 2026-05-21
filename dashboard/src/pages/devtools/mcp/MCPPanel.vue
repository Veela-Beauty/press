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

		<MCPTopTabs />

		<section class="rounded border border-gray-200 bg-white">
			<!-- Header: title + risk summary + search -->
			<div class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 p-4">
				<div class="flex items-baseline gap-4">
					<div class="text-base font-semibold">Active Tokens</div>
					<div class="text-xs text-gray-600">
						<span class="font-semibold">{{ summary.active }}</span> active
						<span v-if="summary.highRisk > 0" class="ml-2 text-red-700">
							· <span class="font-semibold">{{ summary.highRisk }}</span> with high-risk tools
						</span>
						<span v-if="summary.expiringSoon > 0" class="ml-2 text-amber-700">
							· <span class="font-semibold">{{ summary.expiringSoon }}</span> expiring within 24h
						</span>
					</div>
				</div>
				<div class="flex items-center gap-2">
					<input
						type="text"
						v-model="tokenSearch"
						placeholder="Search by label or tool..."
						class="w-56 rounded border border-gray-300 px-3 py-1.5 text-xs focus:border-blue-500 focus:outline-none"
					/>
					<Button size="sm" @click="onPurgeExpired" title="Delete all expired tokens immediately (instead of waiting for the daily cron)">
						Purge expired
					</Button>
				</div>
			</div>

			<!-- Token list (cards, not a wide table) -->
			<div v-if="filteredTokens.length === 0 && tokens.length === 0" class="p-8 text-center text-sm text-gray-500">
				No tokens yet. Click <strong>Issue Token</strong> to create one.
			</div>
			<div v-else-if="filteredTokens.length === 0" class="p-8 text-center text-sm text-gray-500">
				No tokens match "{{ tokenSearch }}".
			</div>
			<ul v-else class="divide-y divide-gray-100">
				<li v-for="t in filteredTokens" :key="t.name" class="p-4">
					<div class="flex items-start justify-between gap-3">
						<!-- Left: label + risk badges + meta -->
						<div class="min-w-0 flex-1">
							<div class="flex items-center gap-2">
								<span class="text-sm font-semibold text-gray-900 truncate">{{ t.label }}</span>
								<span :class="statusClass(t.status)">{{ t.status }}</span>
							</div>
							<!-- Risk badge cluster -->
							<div class="mt-1.5 flex flex-wrap items-center gap-1.5">
								<button
									v-if="(t.scope || []).length === 0"
									type="button"
									class="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-700 hover:bg-gray-200"
									@click="toggleScopeDetail(t.name)"
								>
									all tools
								</button>
								<template v-else>
									<button
										v-for="bucket in scopeBuckets(t)"
										:key="bucket.label"
										type="button"
										:class="bucket.cls + ' hover:opacity-80'"
										@click="toggleScopeDetail(t.name)"
									>
										{{ bucket.count }} {{ bucket.label }}
									</button>
									<button
										type="button"
										class="text-[11px] text-blue-600 hover:underline"
										@click="toggleScopeDetail(t.name)"
									>
										{{ expandedTokens[t.name] ? 'Hide' : 'Show' }} details
									</button>
								</template>
								<span v-if="t.allowed_release_groups?.length || t.allowed_sites?.length"
									class="ml-2 inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-800">
									→
									<span v-if="t.allowed_release_groups?.length" class="ml-1">
										{{ t.allowed_release_groups.length }} RG{{ t.allowed_release_groups.length > 1 ? 's' : '' }}
									</span>
									<span v-if="t.allowed_release_groups?.length && t.allowed_sites?.length" class="mx-1">/</span>
									<span v-if="t.allowed_sites?.length">
										{{ t.allowed_sites.length }} site{{ t.allowed_sites.length > 1 ? 's' : '' }}
									</span>
								</span>
							</div>
							<!-- Meta line -->
							<div class="mt-1.5 text-[11px] text-gray-500">
								Issued {{ formatDate(t.creation) }} ·
								Expires {{ formatDate(t.expires_at) }} ·
								Last used {{ formatDate(t.last_used_at) || 'never' }}
							</div>
						</div>
						<!-- Right: handover / reissue / revoke actions -->
						<div class="flex shrink-0 gap-1">
							<!-- Has plaintext: one-click Copy reveals the real token inline. -->
							<Button v-if="t.has_plaintext" size="sm" @click="onShowHandover(t)"
								title="Show plaintext token + handover snippet">
								Copy token
							</Button>
							<!-- Active old token without plaintext: one-click Reissue & Copy replaces
							     it with a fresh one and shows the new plaintext inline. -->
							<Button v-else-if="t.status === 'active'" size="sm" @click="onReissue(t)"
								title="Revoke this old token + issue a new one with the same scope, then show the fresh plaintext">
								Reissue & Copy
							</Button>
							<!-- Old expired/revoked token without plaintext: nothing useful to show. -->
							<Button v-if="t.has_plaintext && t.status === 'active'" size="sm" @click="onReissue(t)" title="Revoke + issue new token with same scope">
								Reissue
							</Button>
							<Button v-if="t.status === 'active'" size="sm" @click="onRevoke(t)">Revoke</Button>
						</div>
					</div>

					<!-- Inline handover panel (toggled per-row) -->
					<div v-if="handoverFor === t.name" class="mt-3">
						<HandoverPanel
							:token="handoverToken || '<YOUR_TOKEN_HERE>'"
							:label="t.label"
							:scope="t.scope || []"
							:mode="handoverToken ? 'issued' : 'existing'"
						/>
					</div>

					<!-- Expanded scope detail (grouped by category) -->
					<div v-if="expandedTokens[t.name] && (t.scope || []).length > 0"
						class="mt-3 space-y-2 rounded border border-gray-200 bg-gray-50 p-3">
						<div v-for="cat in TOOL_CATEGORIES" :key="cat.id">
							<div v-if="toolsInCategory(t, cat.id).length > 0">
								<div class="mb-1 text-[11px] font-semibold uppercase text-gray-600">
									{{ cat.label }}
									<span class="font-normal text-gray-500">({{ toolsInCategory(t, cat.id).length }})</span>
								</div>
								<div class="flex flex-wrap gap-1">
									<span v-for="tool in toolsInCategory(t, cat.id)" :key="tool"
										class="inline-flex items-center rounded bg-white border border-gray-200 px-2 py-0.5 text-[11px] text-gray-700"
										:title="tool">
										{{ TOOL_CATALOG[tool]?.label || tool }}
										<span :class="riskBadgeClass(TOOL_CATALOG[tool]?.risk) + ' ml-1'">
											{{ TOOL_CATALOG[tool]?.risk?.[0]?.toUpperCase() || '?' }}
										</span>
									</span>
								</div>
							</div>
						</div>
					</div>
				</li>
			</ul>
		</section>

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

		<IssueTokenDialog v-model="showIssueDialog" @issued="loadTokens" />
	</div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { Button, FeatherIcon, call, toast } from 'frappe-ui';
import { confirmDialog } from '../../../utils/components';
import IssueTokenDialog from '../../../components/mcp/IssueTokenDialog.vue';
import HandoverPanel from '../../../components/mcp/HandoverPanel.vue';
import MCPTopTabs from '../../../components/mcp/MCPTopTabs.vue';
import {
	toolLabel,
	TOOL_CATALOG,
	TOOL_CATEGORIES,
	riskBadgeClass,
} from '../../../components/mcp/_tool_catalog.js';

const tokens = ref([]);
const tokenSearch = ref('');
const expandedTokens = reactive({});
const handoverFor = ref(null); // token name whose inline handover panel is open
const handoverToken = ref(null); // plaintext token (only set after a Reissue)
const showIssueDialog = ref(false);

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

// ---- Tokens: bucket counts, filter, sort, summary ----

function tokenRiskCount(token, risk) {
	const scope = token.scope || [];
	if (scope.length === 0) {
		// Empty scope = all tools allowed; count from catalog
		return Object.values(TOOL_CATALOG).filter((t) => t.risk === risk).length;
	}
	return scope.filter((id) => TOOL_CATALOG[id]?.risk === risk).length;
}

function scopeBuckets(token) {
	const buckets = [];
	const high = tokenRiskCount(token, 'high');
	const medium = tokenRiskCount(token, 'medium');
	const low = tokenRiskCount(token, 'low');
	if (high) buckets.push({ label: 'high-risk', count: high, cls: riskBadgeClass('high') });
	if (medium) buckets.push({ label: 'state-changing', count: medium, cls: riskBadgeClass('medium') });
	if (low) buckets.push({ label: 'read-only', count: low, cls: riskBadgeClass('low') });
	return buckets;
}

function toolsInCategory(token, catId) {
	const scope = token.scope || [];
	if (scope.length === 0) {
		// All tools — show entire category
		return Object.keys(TOOL_CATALOG).filter((id) => TOOL_CATALOG[id].category === catId);
	}
	return scope.filter((id) => TOOL_CATALOG[id]?.category === catId);
}

function toggleScopeDetail(name) {
	expandedTokens[name] = !expandedTokens[name];
}

const filteredTokens = computed(() => {
	const q = tokenSearch.value.trim().toLowerCase();
	let list = tokens.value.slice();
	if (q) {
		list = list.filter((t) => {
			if ((t.label || '').toLowerCase().includes(q)) return true;
			return (t.scope || []).some((id) => {
				if (id.toLowerCase().includes(q)) return true;
				const label = TOOL_CATALOG[id]?.label || '';
				return label.toLowerCase().includes(q);
			});
		});
	}
	// Sort: active first, then high-risk-count desc, then creation desc
	return list.sort((a, b) => {
		const aActive = a.status === 'active' ? 0 : 1;
		const bActive = b.status === 'active' ? 0 : 1;
		if (aActive !== bActive) return aActive - bActive;
		const aHigh = tokenRiskCount(a, 'high');
		const bHigh = tokenRiskCount(b, 'high');
		if (aHigh !== bHigh) return bHigh - aHigh;
		return (b.creation || '').localeCompare(a.creation || '');
	});
});

const summary = computed(() => {
	const active = tokens.value.filter((t) => t.status === 'active');
	const highRisk = active.filter((t) => tokenRiskCount(t, 'high') > 0).length;
	const now = Date.now();
	const expiringSoon = active.filter((t) => {
		if (!t.expires_at) return false;
		const ms = new Date(t.expires_at).getTime() - now;
		return ms > 0 && ms < 24 * 60 * 60 * 1000;
	}).length;
	return { active: active.length, highRisk, expiringSoon };
});

async function loadTokens() {
	try {
		tokens.value = await call('press.mcp_server.dashboard.list_my_tokens');
	} catch (e) {
		toast.error('Failed to load tokens: ' + (e?.message || e));
	}
}

async function onPurgeExpired() {
	confirmDialog({
		title: 'Purge expired tokens?',
		message: 'This will permanently delete <strong>all</strong> of your expired tokens right now (instead of waiting for tomorrow\'s daily cron). Active tokens are not affected.',
		onSuccess: async ({ hide }) => {
			try {
				const result = await call('press.mcp_server.dashboard.purge_my_expired_tokens');
				toast.success(`Purged ${result.deleted} expired token${result.deleted === 1 ? '' : 's'}`);
				hide();
				await loadTokens();
			} catch (e) {
				toast.error('Purge failed: ' + (e?.messages?.[0] || e?.message || e));
			}
		},
	});
}

async function performRevoke(token) {
	try {
		await call('press.mcp_server.auth.revoke_token', { token_id: token.name });
		toast.success(`Revoked: ${token.label}`);
		await loadTokens();
	} catch (e) {
		toast.error('Revoke failed: ' + (e?.message || e));
	}
}

async function onShowHandover(token) {
	if (handoverFor.value === token.name) {
		// Toggle off
		handoverFor.value = null;
		handoverToken.value = null;
		return;
	}
	if (!token.has_plaintext) {
		// Old token (pre-plaintext-storage) — show placeholder snippet
		handoverFor.value = token.name;
		handoverToken.value = null;
		return;
	}
	// Recoverable: fetch plaintext directly (owner check is the auth gate;
	// no password prompt — same model as viewing a GitHub PAT in repo settings).
	try {
		const r = await call('press.mcp_server.auth.recover_token', {
			token_id: token.name,
		});
		handoverFor.value = token.name;
		handoverToken.value = r.token;
	} catch (e) {
		toast.error(e?.messages?.[0] || e?.message || 'Recover failed');
	}
}

function onReissue(token) {
	confirmDialog({
		title: 'Reissue token?',
		message: `This will <strong>revoke</strong> <code>${token.label}</code> and create a new token with the same scope. Any agent using the old token will lose access immediately.`,
		fields: [
			{ label: 'New TTL (days, 1–90)', fieldname: 'ttl_days', type: 'int', default: 7 },
		],
		onSuccess: async ({ hide, values }) => {
			try {
				const days = Math.max(1, Math.min(90, parseInt(values.ttl_days) || 7));
				const result = await call('press.mcp_server.auth.reissue_token', {
					token_id: token.name,
					ttl_minutes: days * 24 * 60,
				});
				toast.success(`Reissued: ${token.label}`);
				hide();
				await loadTokens();
				// Show the new token's handover inline on the new row
				handoverFor.value = result.name;
				handoverToken.value = result.token;
			} catch (e) {
				toast.error('Reissue failed: ' + (e?.messages?.[0] || e?.message || e));
			}
		},
	});
}

function onRevoke(token) {
	const high = tokenRiskCount(token, 'high');
	if (high > 0) {
		confirmDialog({
			title: 'Revoke high-risk token?',
			message: `This token has <strong>${high}</strong> high-risk tool(s) enabled (e.g. site_run_python — RCE). Any agent using it will lose access immediately.<br><br>Token: <code>${token.label}</code>`,
			onSuccess: ({ hide }) => {
				performRevoke(token);
				hide();
			},
		});
		return;
	}
	performRevoke(token);
}

function formatDate(d) {
	if (!d) return '';
	try { return new Date(d).toLocaleString(); } catch { return d; }
}

function statusClass(s) {
	if (s === 'active') return 'inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800';
	if (s === 'expired') return 'inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700';
	return 'inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-800';
}

onMounted(() => {
	loadTokens();
});
</script>
