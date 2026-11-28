<template>
	<div class="space-y-3 rounded border p-3"
		:class="mode === 'issued' ? 'border-amber-300 bg-amber-50' : 'border-blue-200 bg-blue-50'">
		<div>
			<div class="text-sm font-medium" :class="mode === 'issued' ? 'text-amber-900' : 'text-blue-900'">
				<template v-if="mode === 'issued'">Token issued — copy NOW. You won't see it again.</template>
				<template v-else>Handover snippet</template>
			</div>
			<div class="text-xs" :class="mode === 'issued' ? 'text-amber-800' : 'text-blue-800'">
				<template v-if="mode === 'issued'">
					Hand the snippet below to your AI agent. It contains the URL + token + how to call it.
				</template>
				<template v-else>
					The plain token can't be retrieved (it's hashed). Replace
					<code class="rounded bg-white/70 px-1">&lt;YOUR_TOKEN_HERE&gt;</code>
					with the original token before sending to your agent.
				</template>
			</div>
		</div>

		<!-- Tabs -->
		<div class="flex flex-wrap gap-1 border-b" :class="mode === 'issued' ? 'border-amber-200' : 'border-blue-200'">
			<button
				v-for="tab in ['Markdown', 'Env', 'Config', 'curl']"
				:key="tab"
				type="button"
				class="px-3 py-1.5 text-xs font-medium transition"
				:class="tabClass(tab)"
				@click="activeTab = tab"
			>
				{{ tab }}
			</button>
		</div>

		<!-- Tab body -->
		<div class="relative">
			<button
				v-if="mode === 'issued'"
				type="button"
				class="absolute right-14 top-1 rounded border border-amber-300 bg-white px-2 py-0.5 text-xs font-medium text-amber-900 hover:opacity-80"
				@click="onShow"
			>
				{{ revealed ? 'Hide' : 'Show' }}
			</button>
			<button
				type="button"
				class="absolute right-1 top-1 rounded border bg-white px-2 py-0.5 text-xs font-medium hover:opacity-80"
				:class="mode === 'issued' ? 'border-amber-300 text-amber-900' : 'border-blue-300 text-blue-900'"
				@click="copyActive"
			>
				{{ copyLabel }}
			</button>
			<pre class="max-h-[260px] overflow-auto rounded bg-white/70 p-3 pr-28 text-[11px] leading-snug whitespace-pre-wrap break-all"
				:class="mode === 'issued' ? 'text-amber-900' : 'text-blue-900'">{{ activeSnippet }}</pre>
		</div>

		<p v-if="mode === 'issued'" class="text-xs text-amber-800">
			Show and Copy ask you to confirm it is you. Copy puts the full token in what you paste.
		</p>
		<details v-if="mode === 'issued'" class="text-xs text-amber-800">
			<summary class="cursor-pointer font-medium">Just the raw token</summary>
			<div class="mt-1 flex items-center gap-2">
				<code class="block flex-1 break-all rounded bg-white/70 p-2">{{ tok }}</code>
				<button type="button" class="rounded border border-amber-300 bg-white px-2 py-0.5 font-medium text-amber-900 hover:opacity-80" @click="copyRaw">
					{{ rawCopyLabel }}
				</button>
			</div>
		</details>
		<ConfirmItsYouDialog v-model="confirmOpen" :reason="confirmReason" @confirmed="onConfirmed" />
	</div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { TOOL_CATALOG, TOOL_CATEGORIES } from './_tool_catalog.js';
import ConfirmItsYouDialog from './ConfirmItsYouDialog.vue';
import { useConfirm } from './useConfirm.js';

const props = defineProps({
	token: { type: String, required: true },
	label: { type: String, default: 'agent' },
	mode: { type: String, default: 'issued' }, // 'issued' | 'existing'
	scope: { type: Array, default: () => [] }, // tool ids this token can call; empty = all
});

const activeTab = ref('Markdown');
const copyLabel = ref('Copy');
const rawCopyLabel = ref('Copy token');
let copyResetTimer = null;

// PRS-SP-22: the token stays masked on screen. Show reveals it, Copy reads it for one synchronous moment (never
// drawn); both ask Confirm it's you unless one still holds (issuing counts as one).
const { confirmOpen, confirmReason, withConfirm, onConfirmed } = useConfirm();
const revealed = ref(false);
const copying = ref(false);
const tok = computed(() => {
	if (props.mode !== 'issued' || revealed.value || copying.value) return props.token;
	return props.token.slice(0, 8) + '•'.repeat(Math.max(props.token.length - 8, 8));
});

const mcpUrl = computed(() => `${window.location.origin}/api/method/press.mcp_server.server.handle`);

const envSnippet = computed(() => `export PRESS_MCP_URL='${mcpUrl.value}'
export PRESS_MCP_TOKEN='${tok.value}'`);

const curlSnippet = computed(() => `# Quick connectivity test (returns help text)
curl -X POST '${mcpUrl.value}' \\
  --data-urlencode 'tool=help' \\
  --data-urlencode 'token=${tok.value}'

# List available tools for this token
curl -X POST '${mcpUrl.value}' \\
  --data-urlencode 'tool=list_tools' \\
  --data-urlencode 'token=${tok.value}'`);

const configSnippet = computed(() => JSON.stringify({
	mcpServers: {
		'press-cloud': {
			url: mcpUrl.value,
			transport: 'http',
			headers: {},
			env: { PRESS_MCP_TOKEN: tok.value },
			description: `Press MCP — ${props.label}`,
		},
	},
}, null, 2));

// Build a markdown catalog of the tools this token can call, grouped by category.
// Empty scope = all tools (the catalog reflects what the server allows).
const scopedCatalog = computed(() => {
	const allowedIds = props.scope.length === 0
		? Object.keys(TOOL_CATALOG)
		: props.scope.filter((id) => !!TOOL_CATALOG[id]);
	if (allowedIds.length === 0) return '_(no tools in scope)_';
	const lines = [];
	for (const cat of TOOL_CATEGORIES) {
		const inCat = allowedIds
			.filter((id) => TOOL_CATALOG[id].category === cat.id)
			.sort();
		if (inCat.length === 0) continue;
		lines.push(`\n**${cat.label}** (${inCat.length} tool${inCat.length === 1 ? '' : 's'}):`);
		for (const id of inCat) {
			const t = TOOL_CATALOG[id];
			const risk = t.risk ? ` _[${t.risk}-risk]_` : '';
			const desc = t.desc ? ` — ${t.desc}` : '';
			lines.push(`- \`${id}\`${risk}${desc}`);
		}
	}
	// Built-in tools always available regardless of scope
	lines.push(`\n**Always available** (built-in):`);
	lines.push(`- \`help\` — return this server's usage instructions`);
	lines.push(`- \`list_tools\` — list every tool callable by THIS token, with descriptions`);
	return lines.join('\n').trim();
});

const markdownSnippet = computed(() => `## Press MCP handover

**Server**: \`${mcpUrl.value}\`
**Token**: \`${tok.value}\`
**Label**: ${props.label}

### How to call
Send POST as form-encoded body — \`tool\` + \`token\` (+ optional \`args\` JSON):

\`\`\`bash
${curlSnippet.value}
\`\`\`

### Env vars (paste in shell or .env)
\`\`\`bash
${envSnippet.value}
\`\`\`

### Claude Desktop / Cursor config (\`~/.claude.json\` or \`~/.cursor/mcp.json\`)
\`\`\`json
${configSnippet.value}
\`\`\`

### Available tools for this token

${scopedCatalog.value}

### Calling a tool with arguments
\`args\` is a JSON-encoded object. Examples:

\`\`\`bash
# Read a release group's details
curl -X POST '${mcpUrl.value}' \\
  --data-urlencode 'tool=release_group_get' \\
  --data-urlencode 'args={"name":"bench-0011"}' \\
  --data-urlencode 'token=${tok.value}'

# Install an app on a site
curl -X POST '${mcpUrl.value}' \\
  --data-urlencode 'tool=site_install_app' \\
  --data-urlencode 'args={"site":"my-site.example.com","app":"erpnext"}' \\
  --data-urlencode 'token=${tok.value}'
\`\`\`

### Response shape
Always \`{message: <result>}\` on success, \`{exc_type, exception}\` on error.
Tool errors come through as HTTP 200 with \`message.error\` set; permission/auth
errors come through as HTTP 4xx with \`exception\` describing the cause.

### Notes for the agent
- Token in body, NOT \`Authorization\` header.
- Audit-logged: every call is recorded with status, duration, and arguments.
- Risky tools (RCE-tier like \`site_run_python\`) require explicit per-token approval.
- Re-fetch \`list_tools\` if you need the live catalog from the server (this snippet
  reflects the catalog at issue time; new tools may have been added since).
`);

const activeSnippet = computed(() => {
	if (activeTab.value === 'Markdown') return markdownSnippet.value;
	if (activeTab.value === 'Env') return envSnippet.value;
	if (activeTab.value === 'Config') return configSnippet.value;
	return curlSnippet.value;
});

function tabClass(tab) {
	const isActive = activeTab.value === tab;
	if (props.mode === 'issued') {
		return isActive
			? 'border-b-2 border-amber-700 text-amber-900'
			: 'text-amber-700 hover:text-amber-900';
	}
	return isActive
		? 'border-b-2 border-blue-700 text-blue-900'
		: 'text-blue-700 hover:text-blue-900';
}

function guarded(action) {
	if (props.mode !== 'issued') return action();
	return withConfirm(`to copy or show the token of ${props.label}`, action);
}

async function writeClipboard(read, label, idle) {
	copying.value = true;
	const text = read();
	copying.value = false;
	try {
		await navigator.clipboard.writeText(text);
		label.value = 'Copied!';
	} catch {
		label.value = 'Press Copy again';
	}
	if (copyResetTimer) clearTimeout(copyResetTimer);
	copyResetTimer = setTimeout(() => (label.value = idle), 1500);
}

function copyActive() {
	return guarded(() => writeClipboard(() => activeSnippet.value, copyLabel, 'Copy'));
}

function copyRaw() {
	return guarded(() => writeClipboard(() => props.token, rawCopyLabel, 'Copy token'));
}

function onShow() {
	if (revealed.value) {
		revealed.value = false;
		return;
	}
	return guarded(() => {
		revealed.value = true;
	});
}
</script>
