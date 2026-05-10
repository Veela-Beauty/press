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
					<li><strong>Copy token</strong> — re-fetch the original plaintext (password re-auth required). Use if you forgot to copy at issue time. Token stays valid; agent isn't disrupted.</li>
					<li><strong>Snippet</strong> — older tokens (issued before 2026-05-10) only have a placeholder. Use <strong>Reissue</strong> if you need a fresh plaintext.</li>
					<li><strong>Reissue</strong> — revokes old + issues new with same scope, resources, and label. Existing agents lose access immediately.</li>
					<li><strong>Revoke</strong> — kills the token. High-risk tokens prompt for confirmation.</li>
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
			<p class="text-xs leading-relaxed text-gray-500">
				<strong>Security note:</strong> tokens are encrypted at rest (Frappe's standard <code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">__Auth</code>).
				Keep them out of public repos and shared chat history. Revoke if leaked.
			</p>
		</div>
	</div>
</template>

<script setup>
import { ref } from 'vue';
import { FeatherIcon } from 'frappe-ui';
import { riskBadgeClass } from './_tool_catalog.js';

const open = ref(false);
</script>
