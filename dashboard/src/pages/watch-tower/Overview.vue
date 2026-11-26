<!-- Watch Tower overview, the module's control room (owner 2026-11-21, prototype ACM-SP-03, contract
~/docs/prototypes/watch-tower-press/v2-contract.yaml): which client needs action now. Data from
sanad_ai_control_center.watch_tower_hub.overview.get_overview (Watch Tower Hub or System Manager, kept a minute).
Rows, chart segments and client columns open that client's page. -->
<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[
						{ label: 'Watch Tower', route: '/watch-tower/overview' },
						{ label: 'Overview', route: '/watch-tower/overview' },
					]"
				/>
				<span v-if="data" class="ml-auto text-sm text-gray-500" title="The hub reads every client every 5 minutes">
					As of {{ data.as_of.slice(11, 16) }}
				</span>
			</Header>
		</div>

		<div class="space-y-4 p-5">
			<div v-if="resource.loading && !data" class="space-y-4">
				<div class="grid grid-cols-2 gap-3 md:grid-cols-5">
					<div v-for="i in 5" :key="i" class="h-24 animate-pulse rounded-lg bg-gray-100" />
				</div>
				<div class="grid gap-4 lg:grid-cols-5">
					<div class="h-72 animate-pulse rounded-lg bg-gray-100 lg:col-span-3" />
					<div class="h-72 animate-pulse rounded-lg bg-gray-100 lg:col-span-2" />
				</div>
				<div class="h-56 animate-pulse rounded-lg bg-gray-100" />
			</div>

			<div v-else-if="resource.error" class="rounded-lg border p-8 text-center text-base text-gray-700">
				<p class="font-medium text-gray-900">Could not load Watch Tower</p>
				<p class="mt-1">{{ errorText }}</p>
				<button class="wt-btn mt-3" @click="resource.reload()">Try again</button>
			</div>

			<div v-else-if="data && !data.sites.length" class="rounded-lg border p-8 text-center text-base text-gray-700">
				<p class="font-medium text-gray-900">No client sites connected yet</p>
				<p class="mt-1">Add one in the desk: Monitored Site, then Connect and test.</p>
			</div>

			<template v-else-if="data">
				<div class="grid grid-cols-2 gap-3" :class="security.data?.checked_at ? 'md:grid-cols-6' : 'md:grid-cols-5'">
					<WtTile
						label="Clients needing action"
						:value="t.needing_action"
						:compare="`of ${t.clients} clients`"
						:flag="needFlag"
						link
						@open="scrollTo(clientsCard)"
					/>
					<WtTile
						label="Open critical"
						:value="t.open_critical"
						:compare="critical.text"
						:tone="critical.tone"
						:flag="t.open_critical ? { kind: 'red', text: 'Needs review' } : { kind: 'ok', text: 'None' }"
						link
						@open="scrollTo(findingsCard)"
					/>
					<WtTile
						label="Open high"
						:value="t.open_high"
						:compare="high.text"
						:tone="high.tone"
						:flag="t.open_high ? { kind: 'amber', text: 'Needs review' } : { kind: 'ok', text: 'None' }"
						link
						@open="scrollTo(findingsCard)"
					/>
					<WtTile label="New in the last 24 h" :value="t.new_24h" :compare="fresh.text" :tone="fresh.tone" />
					<WtTile
						label="Apps behind git"
						:value="t.apps_behind"
						:compare="appsCompare"
						:tone="apps.tone"
						:flag="t.apps_behind ? { kind: 'amber', text: 'Plan updates' } : { kind: 'ok', text: 'Current' }"
						link
						@open="router.push({ name: 'Watch Tower Apps' })"
					/>
					<WtTile
						v-if="security.data?.checked_at"
						label="Security risks"
						:value="securityCount"
						compare="on our servers, checked hourly"
						:flag="securityFlag"
						link
						@open="router.push({ name: 'Infrastructure' })"
					/>
				</div>

				<div class="grid gap-4 lg:grid-cols-5">
					<section class="wt-card lg:col-span-3">
						<div class="wt-card-h">
							<h3>New findings per day</h3>
							<span class="sub">last 30 days, by client</span>
						</div>
						<WtStackedBars
							:days="data.days"
							:layers="layers"
							:pickable-layers="Math.min(3, data.sites.length)"
							label="New findings per day by client"
							@pick="(k) => openClient(data.sites[k].name)"
						/>
						<div class="wt-legend">
							<span v-for="l in layers" :key="l.name"><i :style="{ background: l.color }" />{{ l.name }}</span>
						</div>
					</section>

					<section ref="findingsCard" class="wt-card flex scroll-mt-16 flex-col lg:col-span-2">
						<div class="wt-card-h">
							<h3>Open Critical and High</h3>
							<span class="sub">Critical first, newest first · {{ findings.total.value }} open</span>
							<a class="more" href="/app/client-finding?status=Open">All in the desk</a>
						</div>
						<div v-if="!findings.total.value" class="p-8 text-center text-base text-gray-600">
							No open Critical or High findings
						</div>
						<div :class="{ 'opacity-50': findings.more.loading }">
							<button
								v-for="f in findings.rows.value"
								:key="f.name"
								class="wt-li"
								type="button"
								@click="openClient(f.monitored_site)"
							>
								<span class="badge" :class="SEVERITY_CLASS[f.severity]">{{ f.severity }}</span>
								<span class="what"><b>{{ f.client_name }}</b> <span class="text-gray-600">{{ f.finding_type }}</span></span>
								<span class="end">{{ ago(data.as_of, f.raised_on) }}</span>
							</button>
						</div>
						<WtPager
							class="mt-auto"
							:page="findings.page.value"
							:total="findings.total.value"
							:busy="findings.more.loading"
							@go="findings.go"
						/>
					</section>
				</div>

				<section ref="clientsCard" class="wt-card scroll-mt-16">
					<div class="wt-card-h">
						<h3>Clients</h3>
						<span class="sub">Production first, then the ones that need action</span>
						<a class="more" href="/app/monitored-site">All in the desk</a>
					</div>
					<div class="overflow-x-auto">
						<table class="wt-table wt-clients">
							<thead>
								<tr>
									<th>Client</th>
									<th>Status</th>
									<th>Open findings</th>
									<th class="num">Errors 24 h</th>
									<th>Email</th>
									<th>Users</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="(s, i) in data.sites" :key="s.name" class="go" @click="openClient(s.name)">
									<td>
										<span class="dot" :style="{ background: clientColor(i) }" /><router-link class="name" :to="clientRoute(s.name)" @click.stop>{{ s.client_name }}</router-link>
										<div class="host">
											<span class="badge small" :class="ENV_CLASS[s.environment]">{{ s.environment }}</span>
											<span class="mono">{{ s.name }}</span>
										</div>
									</td>
									<td>
										<span class="badge" :class="STATUS_CLASS[s.status]">{{ s.status }}</span>
										<div v-if="s.failing_checks?.length" class="err" :title="checksTip(s)">{{ failingText(s) }}</div>
										<div v-else class="sub2">read {{ ago(data.as_of, s.last_read_at) }}</div>
										<div v-if="s.last_error" class="err" :title="s.last_error">{{ s.last_error }}</div>
									</td>
									<td>
										<div class="mini">
											<div class="bar">
												<span v-if="s.open_critical" :style="seg(s.open_critical, SEVERITY_COLORS.Critical)" />
												<span v-if="s.open_high" :style="seg(s.open_high, SEVERITY_COLORS.High)" />
												<span v-if="rest(s)" :style="seg(rest(s), REST_COLOR)" />
											</div>
											<span class="txt">
												<template v-if="open(s)">
													<b v-if="s.open_critical" class="text-red-700">{{ s.open_critical }} critical ·</b>
													{{ s.open_high }} high · {{ rest(s) }} other
												</template>
												<template v-else>none</template>
											</span>
										</div>
									</td>
									<td class="num" :class="s.errors_24h > 100 ? 'hot' : s.errors_24h ? 'warn' : ''" :title="topErrors(s)">
										{{ s.errors_24h }}
									</td>
									<td>
										<template v-if="s.email_failed || s.email_stuck">
											<span v-if="s.email_failed">{{ s.email_failed }} failed</span>
											<span v-if="s.email_failed && s.email_stuck"> · </span>
											<span v-if="s.email_stuck" class="text-amber-700">{{ s.email_stuck }} stuck</span>
										</template>
										<span v-else class="text-gray-400">-</span>
									</td>
									<td class="wt-users" :class="{ stale: stale(s) }" :title="usersTip(s)">
										<template v-if="s.users">
											<div>
												<span class="n" :class="CAP_CLASS[s.users.level]">{{ seats(s.users) }}</span>
												<span v-if="s.users.level" class="w" :class="CAP_CLASS[s.users.level]">{{ s.users.level }}</span>
												<span v-else-if="!s.users.cap" class="nocap">no cap set</span>
											</div>
											<div class="sub2">{{ stale(s) ? 'last known' : `${s.users.active_30d} active` }}</div>
										</template>
										<span v-else class="text-gray-400">-</span>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</section>
			</template>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import { createResource } from 'frappe-ui';
import WtPager from './WtPager.vue';
import WtTile from './WtTile.vue';
import WtStackedBars from './WtStackedBars.vue';
import { usePages } from './paging';
import {
	CAP_CLASS,
	ENV_CLASS,
	OTHER_COLOR,
	REST_COLOR,
	SEVERITY_CLASS,
	SEVERITY_COLORS,
	STATUS_CLASS,
	ago,
	clientColor,
	failingChecks,
	failingText,
	seats,
	versus,
} from './shared';

const router = useRouter();
const clientsCard = ref(null);
const findingsCard = ref(null);

// GET: the hub method answers GET only (a read); frappe-ui posts by default, which Frappe refuses as Not permitted
const resource = createResource({
	url: 'sanad_ai_control_center.watch_tower_hub.overview.get_overview',
	method: 'GET',
	auto: true,
});
const data = computed(() => resource.data);
// Exposure Watch (prototype PRS-SP-11): System Manager only; anyone else gets no data and no tile
const security = createResource({ url: 'press.api.infra_board.get_security_findings', auto: true });
const securityCount = computed(() => security.data?.findings?.length || 0);
// Red only for High or Medium; Low rows alone (e.g. socketio on all addresses) ask for a review, not a fix now
const securityFlag = computed(() => {
	const rows = security.data?.findings || [];
	if (rows.some((r) => r.severity !== 'Low')) return { kind: 'red', text: 'Fix now' };
	return rows.length ? { kind: 'amber', text: 'Review' } : { kind: 'ok', text: 'None' };
});
const t = computed(() => data.value.tiles);
const findings = usePages('sanad_ai_control_center.watch_tower_hub.overview.get_findings', () => ({
	rows: data.value.findings,
	total: data.value.findings_total,
}));
const errorText = computed(
	() => resource.error?.messages?.[0] || resource.error?.message || 'Not permitted: needs the Watch Tower Hub or System Manager role.',
);

const critical = computed(() => versus(t.value.open_critical, t.value.open_critical_24h_ago, '24 h ago'));
const high = computed(() => versus(t.value.open_high, t.value.open_high_24h_ago, '24 h ago'));
const fresh = computed(() => versus(t.value.new_24h, t.value.new_prev_24h, 'previous 24 h'));
const apps = computed(() => versus(t.value.apps_behind, t.value.apps_behind_7d_ago, '7 days ago'));
const appsCompare = computed(() => {
	const where = `on ${t.value.apps_behind_clients} clients`;
	return apps.value.text ? `${apps.value.text} · ${where}` : where;
});

// the first three clients get their own colour; the rest fold into "Other clients"
const layers = computed(() => {
	const zero = data.value.days.map(() => 0);
	const values = (s) => data.value.per_client_days[s.name] || zero;
	const named = data.value.sites.slice(0, 3).map((s, i) => ({ name: s.client_name, color: clientColor(i), values: values(s) }));
	const others = data.value.sites.slice(3);
	if (others.length) {
		named.push({
			name: others.length === 1 ? others[0].client_name : 'Other clients',
			color: OTHER_COLOR,
			values: zero.map((_, i) => others.reduce((a, s) => a + values(s)[i], 0)),
		});
	}
	return named;
});

const open = (s) => s.open_critical + s.open_high + s.open_medium + s.open_low;
const rest = (s) => s.open_medium + s.open_low;
const maxOpen = computed(() => Math.max(1, ...data.value.sites.map(open)));
const seg = (n, color) => ({ width: `${(100 * n) / maxOpen.value}%`, background: color });
// a site that stopped reporting shows the users of its last good read, greyed
const stale = (s) => !['Connected', 'Paused'].includes(s.status);
const usersTip = (s) =>
	s.users ? `${s.users.enabled} enabled system users · ${s.users.active_30d} active in the last 30 days` : 'Needs Watch Tower 0.7.3 on the site';
// a failing check on a Production client counts as needing action (hub 0.2.24); the chip says which kind
const needFlag = computed(() => {
	const n = t.value.needing_action;
	const checks = t.value.checks_failing || 0;
	if (!n) return { kind: 'ok', text: 'All read' };
	const unread = data.value.sites.some((s) => ['Silent', 'Revoked', 'Paused'].includes(s.status));
	if (checks && !unread) return { kind: 'red', text: `${checks} check${checks === 1 ? '' : 's'} failing` };
	return { kind: 'red', text: 'Needs review' };
});
const checksTip = (s) => failingChecks(s).map((c) => `${c.name}: ${c.message}`).join('\n');
const topErrors = (s) => (s.top_errors || []).map((e) => `${e.count} x ${e.title}`).join('\n');

const clientRoute = (site) => ({ name: 'Watch Tower Client', params: { site } });
function openClient(site) {
	router.push(clientRoute(site));
}
function scrollTo(card) {
	card?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
</script>

<style scoped src="./watch-tower.css"></style>
