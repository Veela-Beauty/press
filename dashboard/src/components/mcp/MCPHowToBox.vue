<template>
	<div class="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
		<button
			type="button"
			class="flex w-full items-center justify-between px-4 py-3 text-left transition hover:bg-gray-50"
			@click="open = !open"
		>
			<div class="flex items-center gap-2">
				<FeatherIcon name="info" class="h-4 w-4 text-blue-600" />
				<span class="text-sm font-semibold text-gray-900">How to use MCP</span>
				<span class="hidden text-xs text-gray-500 sm:inline">— issue a token, hand it to your AI agent, audit calls</span>
			</div>
			<FeatherIcon
				:name="open ? 'chevron-up' : 'chevron-down'"
				class="h-4 w-4 text-gray-400"
			/>
		</button>
		<div v-if="open" class="space-y-3 border-t border-gray-200 bg-gray-50 px-4 py-4 text-sm text-gray-700">
			<p class="text-xs leading-relaxed text-gray-600">
				<strong>MCP (Model Context Protocol)</strong> lets AI agents (Claude Desktop, Cursor, Cline, etc.)
				call Press tools on your behalf — list sites, deploy benches, install apps, and more.
				Each agent gets a scoped token; calls are audit-logged in the panel below.
			</p>
			<div>
				<div class="font-medium text-gray-900">1. Issue a token</div>
				<ul class="mt-0.5 list-disc space-y-1 pl-5 text-xs leading-relaxed">
					<li>Click <strong>Issue Token</strong> top-right. Pick a label (e.g. "Cursor / dev laptop"), TTL, and the tools the agent should be allowed to call.</li>
					<li>Use <strong>Read-only</strong> preset for safe browsing, <strong>Standard agent</strong> for typical workflows, or check individual tools.</li>
					<li>For <code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">site_run_python</code> / <code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">site_run_sql</code> (high-risk RCE), enable <strong>risky tools</strong>. Non-System users get a <code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">pending</code> token requiring Admin Panel approval.</li>
				</ul>
			</div>
			<div>
				<div class="font-medium text-gray-900">2. Hand off to your agent</div>
				<p class="mt-0.5 text-xs leading-relaxed">The post-issue dialog gives you 4 ready-to-paste handover formats:</p>
				<ul class="mt-0.5 list-disc space-y-1 pl-5 text-xs leading-relaxed">
					<li><strong>Markdown</strong> — full hand-off blob; paste into a chat with the agent</li>
					<li><strong>Env</strong> — <code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">PRESS_MCP_URL</code> + <code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">PRESS_MCP_TOKEN</code> for shell / .env</li>
					<li><strong>Config</strong> — <code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">mcpServers</code> JSON for <code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">~/.claude.json</code> or <code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">~/.cursor/mcp.json</code></li>
					<li><strong>curl</strong> — connectivity test the agent can run first</li>
				</ul>
			</div>
			<div>
				<div class="font-medium text-gray-900">3. Manage existing tokens</div>
				<ul class="mt-0.5 list-disc space-y-1 pl-5 text-xs leading-relaxed">
					<li><strong>Copy token</strong> — one-click reveals the original plaintext inline. Use if you forgot to copy at issue time. Token stays valid; agent isn't disrupted.</li>
					<li><strong>Reissue &amp; Copy</strong> — for older tokens (issued before 2026-05-10) whose plaintext was never stored. One click revokes the old + issues a new with the same scope and shows the fresh plaintext inline. Existing agents using the old token lose access.</li>
					<li><strong>Reissue</strong> — same as Reissue &amp; Copy but available on newer tokens too if you want to rotate them.</li>
					<li><strong>Revoke</strong> — kills the token. High-risk tokens prompt for confirmation.</li>
					<li><strong>Purge expired</strong> (header) — one-click delete of all your expired tokens, instead of waiting for the daily cron.</li>
				</ul>
			</div>
			<div>
				<div class="font-medium text-gray-900">4. Audit + cleanup</div>
				<ul class="mt-0.5 list-disc space-y-1 pl-5 text-xs leading-relaxed">
					<li>Header shows live summary: <code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">N active · M with high-risk tools · K expiring within 24h</code>.</li>
					<li>
						Click any risk badge (<span :class="riskBadgeClass('low')">read-only</span>
						/ <span :class="riskBadgeClass('medium')">state-changing</span>
						/ <span :class="riskBadgeClass('high')">high-risk</span>) to expand the per-category tool list.
					</li>
					<li>Tokens expired more than 24h ago are auto-deleted by a daily cron — no manual cleanup needed.</li>
					<li><strong>Recent Calls</strong> below shows every API call (paginated). Status, duration, error — full audit trail.</li>
				</ul>
			</div>
			<div class="rounded border border-blue-200 bg-blue-50 p-3">
				<div class="mb-2 flex items-center gap-2">
					<FeatherIcon name="book-open" class="h-4 w-4 text-blue-700" />
					<div class="text-sm font-semibold text-blue-900">Canonical Recipes</div>
					<span class="text-[11px] text-blue-700">— copy-paste flows that work first try</span>
				</div>
				<p class="mb-2 text-[11px] leading-relaxed text-blue-800">
					Same recipes the MCP <code class="rounded bg-blue-100 px-1 py-0.5 text-[10px]">help</code> command returns to AI agents.
					Read these before building a multi-tool flow — they prevent the "agent polls forever / restarts a busy worker" failure modes.
				</p>
				<div v-if="recipesLoading" class="text-[11px] text-blue-700">Loading recipes…</div>
				<div v-else-if="recipesError" class="text-[11px] text-red-700">Failed to load recipes: {{ recipesError }}</div>
				<div v-else class="space-y-3">
					<div
						v-for="r in recipes"
						:key="r.id"
						class="rounded border border-blue-100 bg-white p-2"
					>
						<div class="flex items-start justify-between gap-2">
							<div class="font-medium text-gray-900 text-xs">{{ r.title }}</div>
							<button
								type="button"
								class="shrink-0 rounded border border-gray-200 bg-gray-50 px-2 py-0.5 text-[10px] text-gray-600 hover:bg-gray-100"
								@click="copyRecipe(r)"
							>
								{{ copiedId === r.id ? 'Copied!' : 'Copy' }}
							</button>
						</div>
						<p class="mt-1 text-[11px] leading-relaxed text-gray-600">{{ r.purpose }}</p>
						<pre class="mt-1.5 overflow-x-auto rounded bg-gray-900 px-2 py-1.5 text-[10.5px] leading-snug text-gray-100"><code>{{ r.steps.join('\n') }}</code></pre>
						<p v-if="r.caveats" class="mt-1 text-[10.5px] italic leading-relaxed text-amber-700">⚠ {{ r.caveats }}</p>
					</div>
				</div>
			</div>
			<p class="text-xs leading-relaxed text-gray-500">
				<strong>Security note:</strong> tokens are encrypted at rest (Frappe's standard <code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">__Auth</code>).
				Keep them out of public repos and shared chat history. Revoke if leaked.
			</p>
		</div>
	</div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { FeatherIcon, createResource } from 'frappe-ui';
import { riskBadgeClass } from './_tool_catalog.js';

const open = ref(false);
const recipes = ref([]);
const recipesLoading = ref(false);
const recipesError = ref('');
const copiedId = ref('');

const recipesResource = createResource({
	url: 'press.mcp_server.help.get_server_recipes',
	auto: false,
	onSuccess(data) {
		recipes.value = Array.isArray(data) ? data : [];
		recipesLoading.value = false;
	},
	onError(err) {
		recipesError.value = err?.messages?.[0] || err?.message || String(err);
		recipesLoading.value = false;
	},
});

onMounted(() => {
	recipesLoading.value = true;
	recipesResource.fetch();
});

function copyRecipe(r) {
	const text = `# ${r.title}\n# ${r.purpose}\n\n${r.steps.join('\n')}` + (r.caveats ? `\n\n# Caveats: ${r.caveats}` : '');
	navigator.clipboard.writeText(text).then(() => {
		copiedId.value = r.id;
		setTimeout(() => { if (copiedId.value === r.id) copiedId.value = ''; }, 1500);
	});
}
</script>
