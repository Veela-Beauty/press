<template>
	<div>
		<!-- Header: warnings about active tokens + search + issue -->
		<div class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 bg-gray-50 px-4 py-3">
			<div class="text-xs">
				<span v-if="summary.highRisk > 0" class="text-red-700">
					<span class="font-semibold">{{ summary.highRisk }}</span> active with high-risk tools
				</span>
				<span v-if="summary.expiringSoon > 0" class="ml-2 text-amber-700">
					<span class="font-semibold">{{ summary.expiringSoon }}</span> expiring within 24h
				</span>
			</div>
			<div class="flex items-center gap-2">
				<input
					type="text"
					v-model="tokenSearch"
					placeholder="Search by name, key or tool..."
					class="w-56 rounded border border-gray-300 px-3 py-1.5 text-xs focus:border-blue-500 focus:outline-none"
				/>
				<Button size="sm" @click="statusTab = 'active'; $emit('issue')" variant="solid">
					<template #prefix><FeatherIcon name="plus" class="h-4 w-4" /></template>
					Issue
				</Button>
			</div>
		</div>

		<!-- Status switch: the page opens on Active so dead tokens are never mistaken for live ones -->
		<div class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 px-4 py-3">
			<div class="inline-flex overflow-x-auto rounded border border-gray-200">
				<button
					v-for="(tab, i) in STATUS_TABS"
					:key="tab.id"
					type="button"
					:class="[
						'inline-flex items-center gap-1 whitespace-nowrap border-gray-200 px-3 py-1.5 text-xs',
						i > 0 && 'border-l',
						statusTab === tab.id ? 'bg-gray-900 text-white' : 'bg-white text-gray-700 hover:bg-gray-50',
					]"
					@click="statusTab = tab.id"
				>
					{{ tab.label }}
					<span :class="statusTab === tab.id ? 'text-gray-300' : 'text-gray-500'">{{ statusCounts[tab.id] }}</span>
				</button>
			</div>
			<Button v-if="statusTab === 'expired' && statusCounts.expired > 0" size="sm" @click="onPurgeExpired"
				title="Delete expired tokens now instead of waiting for the daily job">
				Purge expired
			</Button>
			<span v-else-if="statusTab === 'revoked'" class="text-xs text-gray-500">
				Revoked tokens stop working at once and cannot be used again.
			</span>
		</div>

		<!-- Token list -->
		<div v-if="filteredTokens.length === 0" class="p-8 text-center text-sm text-gray-500">
			<template v-if="tokenSearch.trim()">No {{ statusTab }} tokens match "{{ tokenSearch }}".</template>
			<template v-else-if="statusTab === 'active'">No active tokens. Click <strong>Issue</strong> to create one.</template>
			<template v-else>No {{ statusTab }} tokens.</template>
		</div>
		<ul v-else class="divide-y divide-gray-100">
			<li v-for="t in filteredTokens" :key="t.name" :class="['p-4', t.status !== 'active' && 'bg-gray-50']">
				<div class="flex flex-wrap items-start justify-between gap-3">
					<div class="min-w-0 flex-1">
						<div class="flex items-center gap-2">
							<span :class="['truncate text-sm', t.status === 'active' ? 'font-semibold text-gray-900' : 'font-medium text-gray-500']">
								{{ t.label }}
							</span>
							<span :class="statusClass(t.status)">{{ t.status }}</span>
							<span v-if="t.token_prefix" class="font-mono text-[11px] text-gray-500" title="First 8 characters of the token">
								{{ t.token_prefix }}…
							</span>
						</div>
						<div :class="['mt-2 flex flex-wrap items-center gap-2', t.status !== 'active' && 'opacity-60 grayscale']">
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
							<span v-else class="ml-2 inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-800">
								all sites
							</span>
						</div>
						<div class="mt-2 text-[11px] text-gray-500">
							<span v-if="t.status === 'active'" class="font-semibold text-gray-700">Expires {{ formatDate(t.expires_at) }}</span>
							<span v-else-if="t.status === 'revoked'" class="font-semibold text-red-700">Revoked {{ formatDate(t.revoked_at) }}</span>
							<span v-else class="font-semibold text-gray-700">Expired {{ formatDate(t.expires_at) }}</span>
							· {{ t.last_used_at ? 'Last used ' + formatDate(t.last_used_at) : 'Never used' }}
							· Issued {{ formatDate(t.creation) }}
						</div>
					</div>
					<div v-if="t.status === 'active'" class="flex shrink-0 gap-1">
						<Button v-if="t.has_plaintext" size="sm" @click="onShowHandover(t)"
							title="Show plaintext token + handover snippet">
							Copy token
						</Button>
						<Button v-else size="sm" @click="onReissue(t)"
							title="Revoke this old token + issue a new one with the same scope, then show the fresh plaintext">
							Reissue &amp; Copy
						</Button>
						<Button v-if="t.has_plaintext" size="sm" @click="onReissue(t)" title="Revoke + issue new token with same scope">
							Reissue
						</Button>
						<Button size="sm" theme="red" @click="onRevoke(t)">Revoke</Button>
					</div>
				</div>

				<div v-if="handoverFor === t.name" class="mt-3">
					<HandoverPanel
						:token="handoverToken || '<YOUR_TOKEN_HERE>'"
						:label="t.label"
						:scope="t.scope || []"
						:mode="handoverToken ? 'issued' : 'existing'"
					/>
				</div>

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
	</div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { Button, FeatherIcon, toast } from 'frappe-ui';
import call from './teamCall.js';
import { confirmDialog } from '../../utils/components';
import HandoverPanel from './HandoverPanel.vue';
import { TOOL_CATALOG, TOOL_CATEGORIES, riskBadgeClass } from './_tool_catalog.js';

defineEmits(['issue']);

const STATUS_TABS = [
	{ id: 'active', label: 'Active' },
	{ id: 'revoked', label: 'Revoked' },
	{ id: 'expired', label: 'Expired' },
];

const tokens = ref([]);
const tokenSearch = ref('');
const statusTab = ref('active');
const expandedTokens = reactive({});
const handoverFor = ref(null);
const handoverToken = ref(null);

function tokenRiskCount(token, risk) {
	const scope = token.scope || [];
	if (scope.length === 0) return Object.values(TOOL_CATALOG).filter((t) => t.risk === risk).length;
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
	if (scope.length === 0) return Object.keys(TOOL_CATALOG).filter((id) => TOOL_CATALOG[id].category === catId);
	return scope.filter((id) => TOOL_CATALOG[id]?.category === catId);
}

function toggleScopeDetail(name) {
	expandedTokens[name] = !expandedTokens[name];
}

const statusCounts = computed(() =>
	Object.fromEntries(STATUS_TABS.map((tab) => [tab.id, tokens.value.filter((t) => t.status === tab.id).length])),
);

const filteredTokens = computed(() => {
	const q = tokenSearch.value.trim().toLowerCase();
	let list = tokens.value.filter((t) => t.status === statusTab.value);
	if (q) {
		list = list.filter((t) => {
			if ((t.label || '').toLowerCase().includes(q)) return true;
			if ((t.token_prefix || '').toLowerCase().includes(q)) return true;
			return (t.scope || []).some((id) => {
				if (id.toLowerCase().includes(q)) return true;
				const label = TOOL_CATALOG[id]?.label || '';
				return label.toLowerCase().includes(q);
			});
		});
	}
	return list.sort((a, b) => {
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
		handoverFor.value = null;
		handoverToken.value = null;
		return;
	}
	if (!token.has_plaintext) {
		handoverFor.value = token.name;
		handoverToken.value = null;
		return;
	}
	try {
		const r = await call('press.mcp_server.auth.recover_token', { token_id: token.name });
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
			onSuccess: ({ hide }) => { performRevoke(token); hide(); },
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

// Expose loadTokens to parent so it can re-fetch after Issue Token dialog completes
defineExpose({ loadTokens });

onMounted(() => {
	loadTokens();
});
</script>
