<template>
	<div>
		<!-- Top bar: search + risk filter + count -->
		<div class="flex flex-wrap items-center gap-2 border-b border-gray-200 bg-gray-50 px-4 py-3">
			<input
				v-model="search"
				type="text"
				placeholder="Search tool name or description..."
				class="min-w-[200px] flex-1 rounded border border-gray-200 px-2 py-1 text-xs focus:border-blue-400 focus:outline-none"
			/>
			<div class="flex items-center gap-1 text-[11px]">
				<span class="text-gray-500">Risk:</span>
				<button
					v-for="r in ['all', 'low', 'medium', 'high']"
					:key="r"
					type="button"
					class="rounded border px-1.5 py-0.5 transition"
					:class="riskFilter === r ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'"
					@click="riskFilter = r"
				>
					{{ r }}
				</button>
			</div>
			<div class="text-[11px] text-gray-500">
				{{ filteredCount }} / {{ catalog?.total || 0 }} shown
			</div>
		</div>

		<div v-if="loading" class="px-4 py-6 text-center text-xs text-gray-500">
			Loading catalog…
		</div>
		<div v-else-if="error" class="px-4 py-6 text-center text-xs text-red-600">
			Failed to load catalog: {{ error }}
		</div>
		<div v-else class="space-y-4 px-4 py-4">
			<div v-for="cat in filteredCategories" :key="cat.id">
				<div class="mb-2 flex items-baseline gap-2">
					<h3 class="text-sm font-semibold text-gray-900">{{ cat.label }}</h3>
					<span class="text-[11px] text-gray-500">{{ cat.tools.length }} tools</span>
				</div>
				<div class="grid grid-cols-1 gap-2 lg:grid-cols-2">
					<div
						v-for="t in cat.tools"
						:key="t.name"
						class="rounded border border-gray-200 bg-white p-2.5"
					>
						<div class="flex items-start justify-between gap-2">
							<div class="min-w-0 flex-1">
								<div class="flex items-center gap-1.5 flex-wrap">
									<code
										class="rounded px-1.5 py-0.5 text-[12px] font-mono font-semibold"
										style="background-color: #1f2937; color: #6ee7b7;"
									>{{ t.name }}</code>
									<span :class="riskBadgeClass(t.risk)">{{ t.risk }}</span>
								</div>
								<p class="mt-1 text-[11.5px] leading-snug text-gray-700">{{ t.description }}</p>
							</div>
							<button
								type="button"
								class="shrink-0 rounded border border-gray-200 bg-gray-50 px-2 py-0.5 text-[10px] text-gray-600 hover:bg-gray-100"
								@click="copyCurl(t)"
							>
								{{ copiedTool === t.name ? 'Copied!' : 'Copy curl' }}
							</button>
						</div>

						<div v-if="argEntries(t).length" class="mt-2 overflow-hidden rounded border border-gray-100">
							<table class="w-full text-[10.5px]">
								<thead class="bg-gray-50 text-gray-600">
									<tr>
										<th class="px-2 py-1 text-left font-medium">arg</th>
										<th class="px-2 py-1 text-left font-medium">type</th>
										<th class="px-2 py-1 text-left font-medium">req</th>
										<th class="px-2 py-1 text-left font-medium">description</th>
									</tr>
								</thead>
								<tbody>
									<tr v-for="a in argEntries(t)" :key="a.name" class="border-t border-gray-100">
										<td class="px-2 py-1 font-mono text-gray-900">{{ a.name }}</td>
										<td class="px-2 py-1 text-gray-600">{{ a.type }}</td>
										<td class="px-2 py-1">
											<span v-if="a.required" class="text-red-600">●</span>
											<span v-else class="text-gray-300">○</span>
										</td>
										<td class="px-2 py-1 text-gray-600">{{ a.description }}</td>
									</tr>
								</tbody>
							</table>
						</div>
						<div v-else class="mt-2 text-[10.5px] italic text-gray-400">no arguments</div>

						<details class="mt-2">
							<summary class="cursor-pointer text-[10.5px] text-blue-600 hover:underline">Show example call</summary>
							<pre class="mt-1.5 overflow-x-auto rounded bg-gray-900 px-2 py-1.5 text-[10px] leading-snug text-gray-100"><code>{{ curlExample(t) }}</code></pre>
						</details>
					</div>
				</div>
			</div>
			<div v-if="filteredCount === 0" class="rounded border border-dashed border-gray-300 bg-white py-8 text-center text-xs text-gray-500">
				No tools match "{{ search }}" at risk={{ riskFilter }}.
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { createResource } from 'frappe-ui';
import { riskBadgeClass } from './_tool_catalog.js';

const catalog = ref(null);
const loading = ref(true);
const error = ref('');
const search = ref('');
const riskFilter = ref('all');
const copiedTool = ref('');

const catalogResource = createResource({
	url: 'press.mcp_server.help.get_tool_catalog_for_guide',
	auto: false,
	onSuccess(data) {
		catalog.value = data;
		loading.value = false;
	},
	onError(err) {
		error.value = err?.messages?.[0] || err?.message || String(err);
		loading.value = false;
	},
});

onMounted(() => {
	catalogResource.fetch();
});

function argEntries(tool) {
	const props = tool?.args_schema?.properties || {};
	const required = new Set(tool?.args_schema?.required || tool?.required_args || []);
	return Object.entries(props).map(([name, schema]) => ({
		name,
		type: schema?.type || (schema?.enum ? 'enum' : '?'),
		required: required.has(name),
		description: schema?.description || '',
	}));
}

function curlExample(tool) {
	const args = {};
	for (const [name] of Object.entries(tool?.args_schema?.properties || {})) {
		if ((tool?.args_schema?.required || tool?.required_args || []).includes(name)) {
			args[name] = `<${name}>`;
		}
	}
	return [
		`curl -X POST 'https://<press-host>/api/method/press.mcp_server.server.handle' \\`,
		`  -H 'Content-Type: application/x-www-form-urlencoded' \\`,
		`  --data-urlencode 'token=<your-token>' \\`,
		`  --data-urlencode 'tool=${tool.name}' \\`,
		`  --data-urlencode 'args=${JSON.stringify(args)}'`,
	].join('\n');
}

function copyCurl(tool) {
	navigator.clipboard.writeText(curlExample(tool)).then(() => {
		copiedTool.value = tool.name;
		setTimeout(() => { if (copiedTool.value === tool.name) copiedTool.value = ''; }, 1500);
	});
}

const filteredCategories = computed(() => {
	if (!catalog.value?.categories) return [];
	const q = search.value.trim().toLowerCase();
	const rf = riskFilter.value;
	const out = [];
	for (const cat of catalog.value.categories) {
		const tools = cat.tools.filter((t) => {
			if (rf !== 'all' && t.risk !== rf) return false;
			if (!q) return true;
			return t.name.toLowerCase().includes(q) || (t.description || '').toLowerCase().includes(q);
		});
		if (tools.length) out.push({ ...cat, tools });
	}
	return out;
});

const filteredCount = computed(() => filteredCategories.value.reduce((n, c) => n + c.tools.length, 0));
</script>
