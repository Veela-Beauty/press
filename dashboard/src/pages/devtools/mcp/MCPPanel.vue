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

		<MCPHowToBox />

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

		<section class="rounded border border-gray-200 bg-white">
			<div class="flex items-center justify-between border-b border-gray-200 p-4">
				<div class="flex items-baseline gap-3">
					<div class="text-base font-semibold">Recent Calls</div>
					<div class="text-xs text-gray-500">
						<span v-if="totalCalls">
							{{ pageStart }}–{{ pageEnd }} of {{ totalCalls }}
						</span>
						<span v-else>—</span>
					</div>
				</div>
				<div class="flex items-center gap-2">
					<select
						v-model.number="pageSize"
						class="rounded border border-gray-300 bg-white px-2 py-1 text-xs"
						@change="onPageSizeChange"
					>
						<option v-for="s in [10, 25, 50, 100]" :key="s" :value="s">{{ s }}/page</option>
					</select>
					<Button size="sm" @click="loadCalls(false)">Refresh</Button>
				</div>
			</div>
			<div class="overflow-x-auto">
				<table class="w-full text-left text-sm">
					<thead class="bg-gray-50 text-xs uppercase text-gray-600">
						<tr>
							<th class="p-3">Time</th>
							<th class="p-3">Tool</th>
							<th class="p-3">Status</th>
							<th class="p-3">Duration</th>
							<th class="p-3">Error</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="c in calls" :key="c.name" class="border-t border-gray-100">
							<td class="p-3 text-xs text-gray-600">{{ formatDate(c.creation) }}</td>
							<td class="p-3" :title="c.tool">
								<div class="font-medium">{{ toolLabel(c.tool) }}</div>
								<div v-if="toolLabel(c.tool) !== c.tool" class="font-mono text-[10px] text-gray-400 leading-tight">
									{{ c.tool }}
								</div>
							</td>
							<td class="p-3">
								<span :class="callStatusClass(c.status)">{{ c.status }}</span>
							</td>
							<td class="p-3 text-xs text-gray-600">{{ c.duration_ms }}ms</td>
							<td class="p-3 text-xs text-red-700">{{ c.error_message || '' }}</td>
						</tr>
						<tr v-if="!calls.length">
							<td colspan="5" class="p-6 text-center text-sm text-gray-500">No MCP calls yet.</td>
						</tr>
					</tbody>
				</table>
			</div>
			<div v-if="totalCalls > pageSize" class="flex items-center justify-between gap-2 border-t border-gray-200 p-3">
				<div class="text-xs text-gray-500">Page {{ currentPage }} of {{ totalPages }}</div>
				<div class="flex gap-1">
					<Button size="sm" :disabled="currentPage === 1" @click="goToPage(1)">First</Button>
					<Button size="sm" :disabled="currentPage === 1" @click="goToPage(currentPage - 1)">Prev</Button>
					<Button size="sm" :disabled="currentPage === totalPages" @click="goToPage(currentPage + 1)">Next</Button>
					<Button size="sm" :disabled="currentPage === totalPages" @click="goToPage(totalPages)">Last</Button>
				</div>
			</div>
		</section>

		<IssueTokenDialog v-model="showIssueDialog" @issued="loadTokens" />
	</div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue';
import { Button, FeatherIcon, call, toast } from 'frappe-ui';
import { confirmDialog } from '../../../utils/components';
import IssueTokenDialog from '../../../components/mcp/IssueTokenDialog.vue';
import HandoverPanel from '../../../components/mcp/HandoverPanel.vue';
import MCPHowToBox from '../../../components/mcp/MCPHowToBox.vue';
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
const calls = ref([]);
const totalCalls = ref(0);
const currentPage = ref(1);
const pageSize = ref(25);
const latestCallTs = ref(null);
const showIssueDialog = ref(false);
let pollHandle = null;

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

const totalPages = computed(() => Math.max(1, Math.ceil(totalCalls.value / pageSize.value)));
const pageStart = computed(() => totalCalls.value === 0 ? 0 : (currentPage.value - 1) * pageSize.value + 1);
const pageEnd = computed(() => Math.min(currentPage.value * pageSize.value, totalCalls.value));

async function loadTokens() {
	try {
		tokens.value = await call('press.mcp_server.dashboard.list_my_tokens');
	} catch (e) {
		toast.error('Failed to load tokens: ' + (e?.message || e));
	}
}

async function loadCalls(incremental = false) {
	try {
		const args = {
			limit: pageSize.value,
			offset: (currentPage.value - 1) * pageSize.value,
		};
		// Incremental polling only on page 1 (newest rows show there)
		if (incremental && currentPage.value === 1 && latestCallTs.value) {
			args.since_iso = latestCallTs.value;
		}
		const result = await call('press.mcp_server.dashboard.list_my_calls', args);
		const rows = result?.rows || [];
		const isPolling = !!args.since_iso;
		if (!isPolling) {
			calls.value = rows;
		} else if (rows.length) {
			// Prepend new rows; trim to pageSize so the page stays bounded
			calls.value = [...rows, ...calls.value].slice(0, pageSize.value);
			totalCalls.value += rows.length;
		}
		if (typeof result?.total === 'number' && !isPolling) {
			totalCalls.value = result.total;
		}
		if (result?.latest) {
			latestCallTs.value = result.latest;
		}
	} catch (e) {
		toast.error('Failed to load calls: ' + (e?.message || e));
	}
}

function pollCalls() {
	loadCalls(true);
}

function goToPage(p) {
	const target = Math.max(1, Math.min(totalPages.value, p));
	if (target === currentPage.value) return;
	currentPage.value = target;
	loadCalls(false);
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

function onPageSizeChange() {
	currentPage.value = 1;
	loadCalls(false);
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

function callStatusClass(s) {
	if (s === 'Success') return 'inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800';
	if (s === 'PermissionError') return 'inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-800';
	if (s === 'ValidationError') return 'inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800';
	return 'inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700';
}

onMounted(() => {
	loadTokens();
	loadCalls(false);
	pollHandle = setInterval(pollCalls, 10000);
});

onUnmounted(() => {
	if (pollHandle) clearInterval(pollHandle);
});
</script>
