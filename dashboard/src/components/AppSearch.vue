<!-- Search the dashboard (owner 2026-11-21: "add a search icon here"; chose sites, benches and servers), in the top bar
like the desk's own search box (owner 2026-11-22: "the search should open in the top bar, not in the middle of the
page"). Part of a name finds the sites, benches and servers this account may see (Press's own list API, so the team
rules apply: a system user sees every team, as on the Sites list), grouped under the box; Enter or a click opens one;
the arrow keys move between results; Escape or a click elsewhere closes the list; "/" focuses the box (AppTopbar). -->
<template>
	<div ref="root" class="as-search">
		<div class="as-search-box" :class="{ open }">
			<SearchIcon class="h-4 w-4 shrink-0" />
			<input
				ref="input"
				v-model="query"
				type="text"
				placeholder="Search sites, benches, servers"
				aria-label="Search sites, benches, servers"
				@focus="open = true"
				@keydown.down.prevent="move(1)"
				@keydown.up.prevent="move(-1)"
				@keydown.enter.prevent="go(rows[cursor])"
				@keydown.esc.prevent="close"
			/>
		</div>
		<div v-if="open" class="as-search-panel">
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
						@click="go(row)"
						@mousemove="cursor = rows.indexOf(row)"
					>
						<span class="name">{{ row.title }}</span>
						<span v-if="row.sub" class="sub">{{ row.sub }}</span>
					</button>
				</template>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { createResource } from 'frappe-ui';
import SearchIcon from '~icons/lucide/search';

const open = ref(false);
const root = ref(null);
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
function go(row) {
	if (!row) return;
	close();
	router.push(row.route);
}
function close() {
	open.value = false;
	query.value = '';
	rows.value = [];
	input.value?.blur();
}
// "/" in the top bar
function focus() {
	input.value?.focus();
	input.value?.select();
}
function outside(event) {
	if (open.value && root.value && !root.value.contains(event.target)) close();
}
onMounted(() => document.addEventListener('mousedown', outside));
onBeforeUnmount(() => document.removeEventListener('mousedown', outside));
defineExpose({ focus });
</script>

<style scoped>
.as-search {
	position: relative;
}
/* on the dark top bar: translucent white with a visible border, like the desk's search on press-ctrl */
.as-search-box {
	display: flex;
	align-items: center;
	gap: 8px;
	width: 320px;
	padding: 0 12px;
	border: 1px solid rgba(255, 255, 255, 0.38);
	border-radius: 8px;
	background: rgba(255, 255, 255, 0.14);
	color: rgba(255, 255, 255, 0.85);
}
.as-search-box.open {
	background: rgba(255, 255, 255, 0.22);
	border-color: rgba(255, 255, 255, 0.65);
}
.as-search-box input {
	flex: 1;
	min-width: 0;
	height: 36px !important; /* style.css forces every input to 36 px */
	border: 0 !important;
	background: transparent !important;
	color: #fff;
	font-size: 13.5px;
	box-shadow: none !important;
	outline: none;
}
.as-search-box input::placeholder {
	color: rgba(255, 255, 255, 0.85);
}
.as-search-panel {
	position: absolute;
	top: calc(100% + 8px);
	right: 0;
	width: 420px;
	padding: 6px;
	background: #fff;
	border-radius: 10px;
	box-shadow: 0 12px 32px rgba(16, 24, 40, 0.22);
	z-index: 40;
}
.as-search-note {
	padding: 12px 10px;
	font-size: 13.5px;
	color: #6b737b;
}
.as-search-results {
	max-height: 60vh;
	overflow-y: auto;
}
.as-search-group {
	padding: 10px 10px 4px;
	font-size: 12px;
	font-weight: 600;
	color: #6b737b;
}
.as-search-row {
	display: flex;
	width: 100%;
	align-items: baseline;
	gap: 10px;
	padding: 8px 10px;
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
