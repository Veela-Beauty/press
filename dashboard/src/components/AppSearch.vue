<!-- Search the dashboard (owner 2026-11-21: "add a search icon here"; chose sites, benches and servers). The top bar's
search icon or "/" opens it; part of a name finds the sites, benches and servers this account may see (Press's own
list API, so the team rules apply: a system user sees every team, as on the Sites list), grouped; Enter or a click
opens one; the arrow keys move between results. -->
<template>
	<Dialog v-model="show" :options="{ size: 'xl' }">
		<template #body>
			<div class="as-search">
				<div class="as-search-box">
					<SearchIcon class="h-5 w-5 shrink-0 text-gray-500" />
					<input
						ref="input"
						v-model="query"
						type="text"
						placeholder="Search sites, benches, servers"
						aria-label="Search sites, benches, servers"
						@keydown.down.prevent="move(1)"
						@keydown.up.prevent="move(-1)"
						@keydown.enter.prevent="open(rows[cursor])"
					/>
				</div>
				<div v-if="query.trim().length < 2" class="as-search-note">Two letters or more</div>
				<div v-else-if="loading && !rows.length" class="as-search-note">Searching</div>
				<div v-else-if="!rows.length" class="as-search-note">Nothing matches "{{ query.trim() }}"</div>
				<div v-else class="as-search-results" role="listbox" :aria-label="`Results for ${query.trim()}`">
					<template v-for="group in groups" :key="group.label">
						<div class="as-search-group">{{ group.label }}</div>
						<button
							v-for="row in group.rows"
							:key="row.route"
							type="button"
							role="option"
							:aria-selected="rows.indexOf(row) === cursor"
							class="as-search-row"
							:class="{ on: rows.indexOf(row) === cursor }"
							@click="open(row)"
							@mousemove="cursor = rows.indexOf(row)"
						>
							<span class="name">{{ row.title }}</span>
							<span v-if="row.sub" class="sub">{{ row.sub }}</span>
						</button>
					</template>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { createResource } from 'frappe-ui';
import SearchIcon from '~icons/lucide/search';

const show = defineModel({ type: Boolean, default: false });
const router = useRouter();
const input = ref(null);
const query = ref('');
const rows = ref([]);
const loading = ref(false);
const cursor = ref(0);

const SOURCES = [
	{ label: 'Sites', doctype: 'Site', fields: ['name', 'status'], field: 'name', title: (r) => r.name, sub: (r) => r.status, route: (r) => `/sites/${r.name}` },
	{ label: 'Benches', doctype: 'Release Group', fields: ['name', 'title'], field: 'title', title: (r) => r.title || r.name, sub: () => '', route: (r) => `/groups/${r.name}` },
	{ label: 'Servers', doctype: 'Server', fields: ['name', 'title'], field: 'title', title: (r) => r.title || r.name, sub: (r) => (r.title && r.title !== r.name ? r.name : ''), route: (r) => `/servers/${r.name}` },
];
// through createResource, so Press's request adds the team header like every other list
const lists = SOURCES.map(() => createResource({ url: 'press.api.client.get_list' }));

const groups = computed(() =>
	SOURCES.map((s) => ({ label: s.label, rows: rows.value.filter((r) => r.group === s.label) })).filter((g) => g.rows.length),
);

let typing;
let latest = 0;
watch(query, (value) => {
	clearTimeout(typing);
	typing = setTimeout(() => search(value.trim()), 250);
});
async function search(text) {
	const mine = ++latest;
	if (text.length < 2) {
		rows.value = [];
		return;
	}
	loading.value = true;
	const found = await Promise.all(
		SOURCES.map((s, i) =>
			lists[i]
				.fetch({
					doctype: s.doctype,
					fields: s.fields,
					filters: { [s.field]: ['like', `%${text}%`], skip_team_filter_for_system_user_and_support_agent: true },
					order_by: 'modified desc',
					limit: 6,
				})
				.then((list) => (list || []).map((r) => ({ group: s.label, title: s.title(r), sub: s.sub(r), route: s.route(r) })))
				.catch(() => []),
		),
	);
	if (mine !== latest) return; // a later search already answered
	rows.value = found.flat();
	cursor.value = 0;
	loading.value = false;
}
function move(step) {
	if (rows.value.length) cursor.value = (cursor.value + step + rows.value.length) % rows.value.length;
}
function open(row) {
	if (!row) return;
	show.value = false;
	router.push(row.route);
}
watch(show, async (open) => {
	if (!open) return;
	await nextTick();
	input.value?.focus();
	input.value?.select();
});
</script>

<style scoped>
.as-search {
	padding: 10px;
}
.as-search-box {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 0 12px;
	border: 1px solid #dfe1e4;
	border-radius: 8px;
}
.as-search-box input {
	flex: 1;
	height: 44px !important;
	border: 0 !important;
	background: transparent !important;
	font-size: 15px;
	box-shadow: none !important;
	outline: none;
}
.as-search-note {
	padding: 16px 12px 8px;
	font-size: 13.5px;
	color: #6b737b;
}
.as-search-results {
	max-height: 60vh;
	overflow-y: auto;
	padding-top: 6px;
}
.as-search-group {
	padding: 10px 12px 4px;
	font-size: 12px;
	font-weight: 600;
	color: #6b737b;
}
.as-search-row {
	display: flex;
	width: 100%;
	align-items: baseline;
	gap: 10px;
	padding: 8px 12px;
	border-radius: 6px;
	text-align: left;
	font-size: 14px;
	color: #1c2024;
}
.as-search-row.on {
	background: #e8f1f7;
	color: #1a5f7a;
}
.as-search-row .name {
	font-weight: 550;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.as-search-row .sub {
	margin-left: auto;
	font-size: 12.5px;
	color: #6b737b;
	white-space: nowrap;
}
</style>
