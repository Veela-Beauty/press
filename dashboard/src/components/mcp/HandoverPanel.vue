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

const props = defineProps({
	token: { type: String, required: true },
	label: { type: String, default: 'agent' },
	mode: { type: String, default: 'issued' }, // 'issued' | 'existing'
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

### Notes for the agent
- Token in body, NOT \`Authorization\` header.
- First call \`tool=help\` for usage, then \`tool=list_tools\` for the catalog.
- Audit-logged. Risky tools require explicit approval per token.
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
