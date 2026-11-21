<!-- Watch Tower Apps (owner 2026-11-21, prototype ACM-SP-04): every app on the connected clients against git, one row
per app with the most clients behind first, 20 a page, to plan updates at 100 apps on 100 clients. Data from
sanad_ai_control_center.watch_tower_hub.apps.get_apps (Watch Tower Hub or System Manager). A row opens the app. -->
<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[
						{ label: 'Watch Tower', route: '/watch-tower/overview' },
						{ label: 'Apps', route: '/watch-tower/apps' },
					]"
				/>
				<span v-if="data" class="ml-auto text-sm text-gray-500" title="The hub reads every client every 5 minutes">
					As of {{ data.as_of.slice(11, 16) }}
				</span>
			</Header>
		</div>

		<div class="p-5">
			<section class="wt-card flex flex-col">
				<div class="wt-card-h">
					<h3>Installed apps</h3>
					<span class="sub" title="Our apps are older when behind git; framework apps only when a whole major behind">
						against git, most clients behind first
					</span>
				</div>
				<div class="wt-toolbar">
					<input v-model="search" class="wt-search" type="search" placeholder="Search app" aria-label="Search app" />
					<div class="wt-seg" role="group" aria-label="Which apps">
						<button type="button" :class="{ on: behind }" @click="setBehind(true)">Behind</button>
						<button type="button" :class="{ on: !behind }" @click="setBehind(false)">All</button>
					</div>
					<span v-if="data" class="count">{{ data.total }} of {{ data.apps }} apps</span>
				</div>

				<div v-if="resource.loading && !data" class="space-y-2 p-4">
					<div v-for="i in 8" :key="i" class="h-8 animate-pulse rounded bg-gray-100" />
				</div>
				<div v-else-if="resource.error" class="p-8 text-center text-base text-gray-700">
					<p class="font-medium text-gray-900">Could not load the apps</p>
					<p class="mt-1">{{ errorText }}</p>
					<button class="wt-btn mt-3" @click="resource.reload()">Try again</button>
				</div>
				<div v-else-if="data && !data.rows.length" class="p-8 text-center text-base text-gray-600">
					<p class="font-medium text-gray-900">{{ emptyTitle }}</p>
					<p class="mt-1">{{ emptyText }}</p>
				</div>
				<div v-else-if="data" class="overflow-x-auto" :class="{ 'opacity-50': resource.loading }">
					<table class="wt-table">
						<thead>
							<tr>
								<th>App</th>
								<th class="num hidden md:table-cell">Git</th>
								<th class="num">Clients</th>
								<th>Standing</th>
								<th class="num hidden lg:table-cell">Oldest installed</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="r in data.rows" :key="r.app" class="go" @click="openApp(r.app)">
								<td>
									<router-link class="mono name" :to="appRoute(r.app)" @click.stop>{{ r.app }}</router-link>
									<span v-if="r.framework" class="badge b-gray small ml-2">framework</span>
								</td>
								<td class="num mono hidden md:table-cell">{{ r.git.join(' / ') || '-' }}</td>
								<td class="num">{{ r.clients }}</td>
								<td>
									<div class="stand">
										<div class="bar">
											<span v-if="r.major" :style="seg(r, r.major, SEVERITY_COLORS.Critical)" />
											<span v-if="r.older" :style="seg(r, r.older, SEVERITY_COLORS.High)" />
											<span v-if="r.current" :style="seg(r, r.current, REST_COLOR)" />
										</div>
										<span class="txt">
											<b v-if="r.major" class="text-red-700">{{ r.major }} major behind · </b>
											<template v-if="r.older">{{ r.older }} older · </template>{{ r.current }} current
										</span>
									</div>
								</td>
								<td class="num mono hidden lg:table-cell">{{ r.oldest || '-' }}</td>
							</tr>
						</tbody>
					</table>
				</div>
				<WtPager :page="page" :total="data?.total || 0" :size="PAGE" :busy="resource.loading" @go="go" />
			</section>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { createResource } from 'frappe-ui';
import WtPager from './WtPager.vue';
import { REST_COLOR, SEVERITY_COLORS } from './shared';

const PAGE = 20; // the hub's apps.PAGE
const router = useRouter();
const search = ref('');
const behind = ref(true);
const page = ref(0);

// GET: the hub method answers GET only (a read); frappe-ui posts by default, which Frappe refuses as Not permitted
const resource = createResource({
	url: 'sanad_ai_control_center.watch_tower_hub.apps.get_apps',
	method: 'GET',
	makeParams: () => ({ search: search.value.trim(), behind_only: behind.value ? 1 : 0, start: page.value * PAGE }),
	auto: true,
});
const data = computed(() => resource.data);
const errorText = computed(
	() => resource.error?.messages?.[0] || resource.error?.message || 'Not permitted: needs the Watch Tower Hub or System Manager role.',
);
const emptyTitle = computed(() => (search.value.trim() ? 'No app matches' : behind.value ? 'Every app is current' : 'No apps yet'));
const emptyText = computed(() =>
	search.value.trim()
		? 'Check the name, or show All.'
		: behind.value
			? 'No client runs an app behind git.'
			: 'Apps show once the hub reads a client.',
);

let typing;
watch(search, () => {
	clearTimeout(typing);
	typing = setTimeout(() => go(0), 250); // one request when the typing stops
});
function setBehind(value) {
	behind.value = value;
	go(0);
}
function go(n) {
	page.value = n;
	resource.reload();
}
const appRoute = (app) => ({ name: 'Watch Tower App', params: { app } });
const openApp = (app) => router.push(appRoute(app));
// each bar is its own app's clients: the share behind reads at a glance; the Clients column carries the size
const seg = (r, n, color) => ({ width: `${(100 * n) / r.clients}%`, background: color });
</script>

<style scoped src="./watch-tower.css"></style>
<style scoped>
.wt-toolbar {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: 10px;
	padding: 10px 16px;
	border-bottom: 1px solid #e9eaec;
}
.wt-search {
	width: 240px;
	border: 1px solid #dfe1e4;
	padding: 0 10px;
	font-size: 13px;
	color: #1c2024;
}
.wt-seg {
	display: inline-flex;
}
.wt-seg button {
	height: 36px; /* level with the search: style.css forces inputs to 36 px */
	border: 1px solid #dfe1e4;
	background: #fff;
	padding: 0 12px;
	font-size: 13px;
	color: #525a64;
}
.wt-seg button:first-child {
	border-radius: 6px 0 0 6px !important; /* style.css forces 6 px on every button */
}
.wt-seg button:last-child {
	border-left: 0;
	border-radius: 0 6px 6px 0 !important;
}
.wt-seg button.on {
	background: #f0f1f2;
	color: #1c2024;
	font-weight: 550;
}
.count {
	margin-left: auto;
	font-size: 12.5px;
	color: #6b737b;
}
.stand {
	display: flex;
	align-items: center;
	gap: 10px;
}
.stand .bar {
	display: flex;
	gap: 2px;
	flex: 0 0 auto;
	width: 140px;
	height: 8px;
	background: #f0f1f2;
	border-radius: 4px;
	overflow: hidden;
}
.stand .bar span {
	height: 100%;
}
.stand .txt {
	font-size: 12.5px;
	color: #525a64;
	font-variant-numeric: tabular-nums;
}
</style>
