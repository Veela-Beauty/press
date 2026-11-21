<!-- One app on the connected clients (owner 2026-11-21, prototype ACM-SP-04): its git version and every client running
it, behind first, then Production, 20 a page, to plan its update. Data from
sanad_ai_control_center.watch_tower_hub.apps.get_app (Watch Tower Hub or System Manager). A row opens the client. -->
<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[
						{ label: 'Watch Tower', route: '/watch-tower/overview' },
						{ label: 'Apps', route: '/watch-tower/apps' },
						{ label: app, route: `/watch-tower/apps/${encodeURIComponent(app)}` },
					]"
				/>
				<span v-if="data" class="ml-auto text-sm text-gray-500" title="The hub reads every client every 5 minutes">
					As of {{ data.as_of.slice(11, 16) }}
				</span>
			</Header>
		</div>

		<div class="space-y-4 p-5">
			<div v-if="resource.loading && !data" class="space-y-4">
				<div class="h-20 animate-pulse rounded-lg bg-gray-100" />
				<div class="h-96 animate-pulse rounded-lg bg-gray-100" />
			</div>

			<div v-else-if="notFound" class="rounded-lg border p-8 text-center text-base text-gray-700">
				<p class="font-medium text-gray-900">No connected client runs this app</p>
				<p class="mt-1">It was removed, or the clients running it are no longer connected.</p>
				<router-link class="wt-btn mt-3" to="/watch-tower/apps">Back to the apps</router-link>
			</div>

			<div v-else-if="resource.error" class="rounded-lg border p-8 text-center text-base text-gray-700">
				<p class="font-medium text-gray-900">Could not load this app</p>
				<p class="mt-1">{{ errorText }}</p>
				<button class="wt-btn mt-3" @click="resource.reload()">Try again</button>
			</div>

			<template v-else-if="data">
				<section class="wt-card">
					<div class="px-5 py-4">
						<h2 class="flex flex-wrap items-center gap-2 text-xl font-semibold text-gray-900">
							<span class="app-name">{{ a.app }}</span>
							<span v-if="a.framework" class="badge b-gray">framework</span>
						</h2>
						<div class="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-base text-gray-600">
							<span>Git <span class="mono">{{ a.git.join(' / ') || '-' }}</span></span>
							<span>on {{ a.clients }} clients</span>
							<span>
								<b v-if="a.major" class="text-red-700">{{ a.major }} major behind · </b>
								<template v-if="a.older">{{ a.older }} older · </template>{{ a.current }} current
							</span>
						</div>
					</div>
				</section>

				<section class="wt-card flex flex-col">
					<div class="wt-card-h">
						<h3>Clients running it</h3>
						<span class="sub">behind first, then Production</span>
					</div>
					<div class="overflow-x-auto" :class="{ 'opacity-50': resource.loading }">
						<table class="wt-table">
							<thead>
								<tr>
									<th>Client</th>
									<th>Environment</th>
									<th class="num">Installed</th>
									<th>Standing</th>
									<th class="hidden md:table-cell">Last read</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="c in data.rows" :key="c.site" class="go" @click="openClient(c.site)">
									<td>
										<router-link class="name" :to="clientRoute(c.site)" @click.stop>{{ c.client_name || c.site }}</router-link>
										<div class="mono mt-0.5">{{ c.site }}</div>
									</td>
									<td><span class="badge" :class="ENV_CLASS[c.environment]">{{ c.environment }}</span></td>
									<td class="num mono">{{ c.version || '-' }}</td>
									<td>
										<span v-if="c.flag" class="tag" :class="{ major: c.flag === 'major behind' }" style="margin-left: 0">
											{{ c.flag }}
										</span>
										<span v-else class="text-gray-600">current</span>
									</td>
									<td class="hidden text-gray-600 md:table-cell">{{ ago(data.as_of, c.last_read_at) }}</td>
								</tr>
							</tbody>
						</table>
					</div>
					<WtPager :page="page" :total="data.total" :size="PAGE" :busy="resource.loading" @go="go" />
				</section>
			</template>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { createResource } from 'frappe-ui';
import WtPager from './WtPager.vue';
import { ENV_CLASS, ago } from './shared';

const props = defineProps({ app: { type: String, required: true } });
const PAGE = 20; // the hub's apps.PAGE
const router = useRouter();
const page = ref(0);

// GET: the hub method answers GET only (a read); frappe-ui posts by default, which Frappe refuses as Not permitted
const resource = createResource({
	url: 'sanad_ai_control_center.watch_tower_hub.apps.get_app',
	method: 'GET',
	makeParams: () => ({ app: props.app, start: page.value * PAGE }),
	auto: true,
});
// another app: drop the last one's rows so the skeleton shows instead of them, and start at page 1
watch(
	() => props.app,
	() => {
		page.value = 0;
		resource.reset();
		resource.reload();
	},
);

const data = computed(() => resource.data);
const a = computed(() => data.value.app);
const notFound = computed(() => resource.error?.exc_type === 'DoesNotExistError');
const errorText = computed(
	() => resource.error?.messages?.[0] || resource.error?.message || 'Not permitted: needs the Watch Tower Hub or System Manager role.',
);
function go(n) {
	page.value = n;
	resource.reload();
}
const clientRoute = (site) => ({ name: 'Watch Tower Client', params: { site } });
const openClient = (site) => router.push(clientRoute(site));
</script>

<style scoped src="./watch-tower.css"></style>
<style scoped>
.app-name {
	font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
	font-size: 19px;
}
a.name {
	font-weight: 550;
	color: #1c2024;
}
a.name:hover {
	text-decoration: underline;
}
</style>
