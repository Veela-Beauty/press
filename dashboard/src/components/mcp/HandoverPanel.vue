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
				type="button"
				class="absolute right-1 top-1 rounded border bg-white px-2 py-0.5 text-xs font-medium hover:opacity-80"
				:class="mode === 'issued' ? 'border-amber-300 text-amber-900' : 'border-blue-300 text-blue-900'"
				@click="copyActive"
			>
				{{ copyLabel }}
			</button>
			<pre class="max-h-[260px] overflow-auto rounded bg-white/70 p-3 pr-16 text-[11px] leading-snug whitespace-pre-wrap break-all"
				:class="mode === 'issued' ? 'text-amber-900' : 'text-blue-900'">{{ activeSnippet }}</pre>
		</div>

		<details v-if="mode === 'issued'" class="text-xs text-amber-800">
			<summary class="cursor-pointer font-medium">Just the raw token</summary>
			<code class="mt-1 block break-all rounded bg-white/70 p-2">{{ token }}</code>
		</details>
	</div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { TOOL_CATALOG, TOOL_CATEGORIES } from './_tool_catalog.js';

const props = defineProps({
	token: { type: String, required: true },
	label: { type: String, default: 'agent' },
	mode: { type: String, default: 'issued' }, // 'issued' | 'existing'
	scope: { type: Array, default: () => [] }, // tool ids this token can call; empty = all
});

const activeTab = ref('Markdown');
const copyLabel = ref('Copy');
let copyResetTimer = null;

const mcpUrl = computed(() => `${window.location.origin}/api/method/press.mcp_server.server.handle`);

const envSnippet = computed(() => `export PRESS_MCP_URL='${mcpUrl.value}'
export PRESS_MCP_TOKEN='${props.token}'`);

const curlSnippet = computed(() => `# Quick connectivity test (returns help text)
curl -X POST '${mcpUrl.value}' \\
  --data-urlencode 'tool=help' \\
  --data-urlencode 'token=${props.token}'

# List available tools for this token
curl -X POST '${mcpUrl.value}' \\
  --data-urlencode 'tool=list_tools' \\
  --data-urlencode 'token=${props.token}'`);

const configSnippet = computed(() => JSON.stringify({
	mcpServers: {
		'press-cloud': {
			url: mcpUrl.value,
			transport: 'http',
			headers: {},
			env: { PRESS_MCP_TOKEN: props.token },
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
**Token**: \`${props.token}\`
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
  --data-urlencode 'token=${props.token}'

# Install an app on a site
curl -X POST '${mcpUrl.value}' \\
  --data-urlencode 'tool=site_install_app' \\
  --data-urlencode 'args={"site":"my-site.example.com","app":"erpnext"}' \\
  --data-urlencode 'token=${props.token}'
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

async function copyActive() {
	try {
		await navigator.clipboard.writeText(activeSnippet.value);
		copyLabel.value = 'Copied!';
	} catch {
		copyLabel.value = 'Copy failed';
	}
	if (copyResetTimer) clearTimeout(copyResetTimer);
	copyResetTimer = setTimeout(() => (copyLabel.value = 'Copy'), 1500);
}
</script>
