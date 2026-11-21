<!-- One client's Watch Tower page (owner 2026-11-21, prototype ACM-SP-03, contract
~/docs/prototypes/watch-tower-press/v2-contract.yaml): what is open, what is failing and what is installed, before
calling the client or changing their app. Data from sanad_ai_control_center.watch_tower_hub.client_profile.get_client
(Watch Tower Hub or System Manager, kept a minute). Open findings open in the desk. -->
<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[
						{ label: 'Watch Tower', route: '/watch-tower/overview' },
						{ label: 'Overview', route: '/watch-tower/overview' },
						{ label: data?.site.client_name || site, route: `/watch-tower/clients/${encodeURIComponent(site)}` },
					]"
				/>
				<span v-if="data" class="ml-auto text-sm text-gray-500" title="The hub reads every client every 5 minutes">
					As of {{ data.as_of.slice(11, 16) }}
				</span>
			</Header>
		</div>

		<div class="space-y-4 p-5">
			<div v-if="resource.loading && !data" class="space-y-4">
				<div class="h-24 animate-pulse rounded-lg bg-gray-100" />
				<div class="grid grid-cols-2 gap-3 md:grid-cols-5">
					<div v-for="i in 5" :key="i" class="h-24 animate-pulse rounded-lg bg-gray-100" />
				</div>
				<div class="grid gap-4 lg:grid-cols-5">
					<div class="h-72 animate-pulse rounded-lg bg-gray-100 lg:col-span-3" />
					<div class="h-72 animate-pulse rounded-lg bg-gray-100 lg:col-span-2" />
				</div>
			</div>

			<div v-else-if="notConnected" class="rounded-lg border p-8 text-center text-base text-gray-700">
				<p class="font-medium text-gray-900">This client is not connected</p>
				<p class="mt-1">It was removed from the hub, or its address changed.</p>
				<router-link class="wt-btn mt-3" to="/watch-tower/overview">Back to the overview</router-link>
			</div>

			<div v-else-if="resource.error" class="rounded-lg border p-8 text-center text-base text-gray-700">
				<p class="font-medium text-gray-900">Could not load this client</p>
				<p class="mt-1">{{ errorText }}</p>
				<button class="wt-btn mt-3" @click="resource.reload()">Try again</button>
			</div>

			<template v-else-if="data">
				<section class="wt-card">
					<div class="flex flex-wrap items-center gap-4 px-5 py-4">
						<div class="min-w-0">
							<h2 class="flex flex-wrap items-center gap-2 text-xl font-semibold text-gray-900">
								{{ s.client_name }}
								<span class="badge" :class="ENV_CLASS[s.environment]">{{ s.environment }}</span>
								<span class="badge" :class="STATUS_CLASS[s.status]">{{ s.status }}</span>
							</h2>
							<div class="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-base text-gray-600">
								<span class="mono">{{ s.name }}</span>
								<span>Last read {{ ago(data.as_of, s.last_read_at) }}</span>
								<span v-if="s.version">Watch Tower {{ s.version }}</span>
								<span v-if="frappeVersion">Frappe {{ frappeVersion }}</span>
							</div>
							<div v-if="s.last_error" class="err" style="max-width: none" :title="s.last_error">{{ s.last_error }}</div>
						</div>
						<div class="ml-auto flex gap-2">
							<a class="wt-btn" :href="`/app/monitored-site/${encodeURIComponent(s.name)}`">Open in desk</a>
							<a v-if="/^https?:\/\//i.test(s.site_url || '')" class="wt-btn" :href="s.site_url" target="_blank" rel="noopener">Open the site</a>
						</div>
					</div>
				</section>

				<div class="grid grid-cols-2 gap-3 md:grid-cols-5">
					<WtTile
						label="Open critical"
						:value="t.open_critical"
						:compare="critical.text"
						:tone="critical.tone"
						:flag="t.open_critical ? { kind: 'red', text: 'Needs review' } : { kind: 'ok', text: 'None' }"
					/>
					<WtTile
						label="Open high"
						:value="t.open_high"
						:compare="high.text"
						:tone="high.tone"
						:flag="t.open_high ? { kind: 'amber', text: 'Needs review' } : { kind: 'ok', text: 'None' }"
					/>
					<WtTile label="New in 7 days" :value="t.new_7d" :compare="week.text" :tone="week.tone" />
					<WtTile
						label="Errors 24 h"
						:value="t.errors_24h"
						:compare="errors.text"
						:tone="errors.tone"
						:flag="t.errors_24h > 100 ? { kind: 'red', text: 'High' } : null"
					/>
					<WtTile label="Email" :compare="email.text" :tone="email.tone">
						{{ t.email_failed }} <span class="unit">failed</span> · {{ t.email_stuck }} <span class="unit">stuck</span>
					</WtTile>
				</div>

				<div class="grid gap-4 lg:grid-cols-5">
					<section class="wt-card lg:col-span-3">
						<div class="wt-card-h">
							<h3>New findings per day</h3>
							<span class="sub">last 30 days, by severity</span>
						</div>
						<WtStackedBars :days="data.days" :layers="severityLayers" label="New findings per day by severity" />
						<div class="wt-legend">
							<span v-for="l in severityLayers" :key="l.name"><i :style="{ background: l.color }" />{{ l.name }}</span>
						</div>
					</section>
					<section class="wt-card lg:col-span-2">
						<div class="wt-card-h">
							<h3>Open findings by type</h3>
							<span class="sub">what kind of problem</span>
						</div>
						<WtHBars :rows="data.by_type" color="#3d4752" empty="No open findings" />
					</section>
				</div>

				<div class="grid gap-4 lg:grid-cols-5">
					<section class="wt-card lg:col-span-3">
						<div class="wt-card-h">
							<h3>Open findings</h3>
							<span class="sub">all severities, newest first · showing {{ data.open.length }} of {{ data.open_total }}</span>
							<a class="more" :href="`/app/client-finding?monitored_site=${encodeURIComponent(s.name)}&status=Open`">
								All in the desk
							</a>
						</div>
						<div v-if="!data.open.length" class="p-8 text-center text-base text-gray-600">No open findings</div>
						<a v-for="f in data.open" :key="f.name" class="wt-li" :href="`/app/client-finding/${encodeURIComponent(f.name)}`">
							<span class="badge" :class="SEVERITY_CLASS[f.severity]">{{ f.severity }}</span>
							<span class="what">
								<b>{{ f.finding_type }}</b> <span class="mono">{{ f.user }}</span>
								<span class="hidden text-gray-600 md:inline"> {{ f.subject }}</span>
							</span>
							<span class="end">{{ ago(data.as_of, f.raised_on) }}</span>
						</a>
					</section>
					<section class="wt-card lg:col-span-2">
						<div class="wt-card-h">
							<h3>Top errors</h3>
							<span class="sub">last 24 h on their site</span>
						</div>
						<WtHBars :rows="data.top_errors" color="#eda100" long empty="No errors in the last 24 h" />
					</section>
				</div>

				<div class="grid gap-4 lg:grid-cols-5">
					<section class="wt-card lg:col-span-3">
						<div class="wt-card-h">
							<h3>Site health per day</h3>
							<span class="sub" title="One reading per client per day, kept from 21-11-2026">last 30 days</span>
						</div>
						<div class="wt-pair">
							<div>
								<div class="h">Errors</div>
								<WtStackedBars :days="data.days" :layers="errorLayers" :height="160" label="Errors per day" />
							</div>
							<div>
								<div class="h">Failed emails</div>
								<WtStackedBars :days="data.days" :layers="emailLayers" :height="160" label="Failed emails per day" />
							</div>
						</div>
					</section>
					<section class="wt-card lg:col-span-2">
						<div class="wt-card-h">
							<h3>Installed apps</h3>
							<span class="sub" title="Our apps are marked older when behind git; framework apps only when a whole major behind">
								against git
							</span>
						</div>
						<table class="wt-table">
							<thead>
								<tr>
									<th>App</th>
									<th class="num">Installed</th>
									<th class="num">Git</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="a in data.apps" :key="a.app">
									<td class="mono text-gray-900">{{ a.app }}</td>
									<td class="num mono">
										{{ a.version || '-' }}
										<span v-if="a.flag" class="tag" :class="{ major: a.flag === 'major behind' }">{{ a.flag }}</span>
									</td>
									<td class="num mono text-gray-500">{{ a.git || '-' }}</td>
								</tr>
							</tbody>
						</table>
					</section>
				</div>
			</template>
		</div>
	</div>
</template>

<script setup>
import { computed, watch } from 'vue';
import { createResource } from 'frappe-ui';
import WtHBars from './WtHBars.vue';
import WtStackedBars from './WtStackedBars.vue';
import WtTile from './WtTile.vue';
import { ENV_CLASS, SEVERITY_CLASS, SEVERITY_COLORS, STATUS_CLASS, ago, versus } from './shared';

const props = defineProps({ site: { type: String, required: true } });

// GET: the hub method answers GET only (a read); frappe-ui posts by default, which Frappe refuses as Not permitted
const resource = createResource({
	url: 'sanad_ai_control_center.watch_tower_hub.client_profile.get_client',
	method: 'GET',
	makeParams: () => ({ site: props.site }),
	auto: true,
});
// another client: drop the last one's numbers so the skeleton shows instead of them
watch(
	() => props.site,
	() => {
		resource.reset();
		resource.reload();
	},
);

const data = computed(() => resource.data);
const s = computed(() => data.value.site);
const t = computed(() => data.value.tiles);
const notConnected = computed(() => resource.error?.exc_type === 'DoesNotExistError');
const errorText = computed(
	() => resource.error?.messages?.[0] || resource.error?.message || 'Not permitted: needs the Watch Tower Hub or System Manager role.',
);
const frappeVersion = computed(() => data.value.apps.find((a) => a.app === 'frappe')?.version);

const critical = computed(() => versus(t.value.open_critical, t.value.open_critical_24h_ago, '24 h ago'));
const high = computed(() => versus(t.value.open_high, t.value.open_high_24h_ago, '24 h ago'));
const week = computed(() => versus(t.value.new_7d, t.value.new_prev_7d, 'previous 7 days'));
const errors = computed(() => versus(t.value.errors_24h, t.value.errors_yesterday, 'yesterday'));
const email = computed(() => {
	const v = versus(t.value.email_failed, t.value.email_failed_yesterday, 'yesterday');
	return { ...v, text: v.text ? `${v.text} failed` : '' };
});

const severityLayers = computed(() =>
	['Critical', 'High', 'Medium', 'Low'].map((name) => ({ name, color: SEVERITY_COLORS[name], values: data.value.by_severity[name] })),
);
const errorLayers = computed(() => [{ name: 'Errors', color: '#eda100', values: data.value.health_days.error_logs_24h }]);
const emailLayers = computed(() => [{ name: 'Failed emails', color: '#3d4752', values: data.value.health_days.email_failed_24h }]);
</script>

<style scoped src="./watch-tower.css"></style>
<style scoped>
.unit {
	font-size: 15px;
	color: #6b737b;
	font-weight: 500;
}
</style>
