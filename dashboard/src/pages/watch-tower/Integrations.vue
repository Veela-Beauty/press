<!-- Watch Tower Integrations (owner 2026-11-24, prototype ACM-SP-08): per client site, the AccuHub link's state and its
task pipeline (Backlog, With OptiFlow, With Accurate, Closed in 30 days), the site's row then one row per project. A
count opens that stage's tasks (IntegrationTasks.vue). Data from sanad_ai_control_center.watch_tower_hub.integrations
(Watch Tower Hub or System Manager), as each link's own Watch Tower check sent it. -->
<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[
						{ label: 'Watch Tower', route: '/watch-tower/overview' },
						{ label: 'Integrations', route: '/watch-tower/integrations' },
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
					<h3>AccuHub link</h3>
					<span class="sub">the team's AccuHub tasks, per site and project</span>
					<span v-if="data" class="more">{{ data.accuhub.length }} {{ data.accuhub.length === 1 ? 'site' : 'sites' }}</span>
				</div>

				<div v-if="resource.loading && !data" class="space-y-2 p-4">
					<div v-for="i in 5" :key="i" class="h-8 animate-pulse rounded bg-gray-100" />
				</div>
				<div v-else-if="resource.error" class="p-8 text-center text-base text-gray-700">
					<p class="font-medium text-gray-900">Could not load the integrations</p>
					<p class="mt-1">{{ errorText }}</p>
					<button class="wt-btn mt-3" @click="resource.reload()">Try again</button>
				</div>
				<div v-else-if="data && !data.accuhub.length" class="p-8 text-center text-base text-gray-600">
					<p class="font-medium text-gray-900">No client runs the AccuHub link</p>
					<p class="mt-1">A client shows here once its link is on and Watch Tower reads it.</p>
				</div>
				<div v-else-if="data" class="overflow-x-auto">
					<table class="wt-table">
						<thead>
							<tr>
								<th>Client</th>
								<th>State</th>
								<th>Last run</th>
								<th v-for="s in STAGES" :key="s.key" class="num" :class="{ step: s.key !== 'closed' }" :title="s.hint">{{ s.label }}</th>
								<th class="num">Sync notes</th>
							</tr>
						</thead>
						<tbody v-for="r in data.accuhub" :key="r.site">
							<tr>
								<td>
									<router-link class="name" :to="{ name: 'Watch Tower Client', params: { site: r.site } }">{{ r.client_name || r.site }}</router-link>
									<div class="host">
										<span class="badge small" :class="ENV_CLASS[r.environment]">{{ r.environment }}</span>
										<span class="mono">{{ r.site }}</span>
									</div>
								</td>
								<td>
									<span v-if="r.ok" class="badge b-green">Working</span>
									<template v-else>
										<span class="badge b-red">{{ r.since ? `Failing since ${hhmm(r.since)}` : 'Failing' }}</span>
										<div class="err" :title="r.message">{{ r.message }}</div>
									</template>
								</td>
								<td>
									<span class="mono">{{ r.last_run ? hhmm(r.last_run) : '-' }}</span>
									<div class="sub2" :title="r.last_result">{{ result(r.last_result) }}</div>
								</td>
								<td v-for="s in STAGES" :key="s.key" class="num">
									<router-link v-if="r.totals[s.key]" class="count" :to="tasksRoute(r.site, s.key)">{{ r.totals[s.key] }}</router-link>
									<span v-else class="zero">{{ r.has_counts ? 0 : '-' }}</span>
								</td>
								<td class="num"><span :class="{ zero: !r.notes }">{{ r.has_counts ? r.notes : '-' }}</span></td>
							</tr>
							<tr v-for="p in r.projects" :key="p.project" class="proj">
								<td colspan="3">{{ p.title }}</td>
								<td v-for="s in STAGES" :key="s.key" class="num">
									<router-link v-if="p[s.key]" class="count" :to="tasksRoute(r.site, s.key, p.project)">{{ p[s.key] }}</router-link>
									<span v-else class="zero">0</span>
								</td>
								<td />
							</tr>
							<tr v-if="!r.has_counts" class="proj">
								<td colspan="8">Counts come with AccuHub link 0.5.0 and Watch Tower 0.7.7 on this site.</td>
							</tr>
						</tbody>
					</table>
				</div>
			</section>
		</div>
	</div>
</template>

<script setup>
import { computed } from 'vue';
import { createResource } from 'frappe-ui';
import { ENV_CLASS } from './shared';
import { STAGES } from './integrations';

// GET: the hub method answers GET only (a read); frappe-ui posts by default, which Frappe refuses as Not permitted
const resource = createResource({
	url: 'sanad_ai_control_center.watch_tower_hub.integrations.get_integrations',
	method: 'GET',
	auto: true,
});
const data = computed(() => resource.data);
const errorText = computed(
	() => resource.error?.messages?.[0] || resource.error?.message || 'Not permitted: needs the Watch Tower Hub or System Manager role.',
);
const hhmm = (when) => (when || '').slice(11, 16);
// the link writes "<time> · <what happened>"; the time already shows above it
const result = (text) => (text || '').split(' · ').slice(1).join(' · ') || text || '';
const tasksRoute = (site, stage, project) => ({
	name: 'Watch Tower Integration Tasks',
	params: { site },
	query: project === undefined ? { stage } : { stage, project },
});
</script>

<style scoped src="./watch-tower.css"></style>
<style scoped>
.wt-table th.step::after {
	content: '\203A';
	margin-left: 8px;
	color: #c2c6cb;
}
.count {
	color: #1a5f7a;
	font-weight: 600;
	text-decoration: underline;
	text-underline-offset: 3px;
}
.zero {
	color: #a0a6ad;
}
tr.proj td {
	padding-top: 7px;
	padding-bottom: 7px;
	font-size: 12.5px;
	color: #525a64;
}
tr.proj td:first-child {
	padding-left: 32px;
}
</style>
