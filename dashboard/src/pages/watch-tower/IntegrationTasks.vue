<!-- One stage of a client's AccuHub task pipeline (owner 2026-11-24, prototype ACM-SP-08): the four stages as tabs in
pipeline order, a Project pick list (ticks, its own search, several allowed) and the stage's tasks, read live from the
client site through the hub (sanad_ai_control_center.watch_tower_hub.integrations.get_stage_tasks); nothing is kept on
autodeploy. Stage and projects live in the URL (?stage=&project=), so a link from the Integrations page opens it set.
The tasks show as a tree with Created by, Created on and Assigned on (accuhub_link 0.6.0, prototype ACH-SP-06): a grey
row is a group not in this stage, there so its tasks sit under it, and is not counted. -->
<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs
					:items="[
						{ label: 'Watch Tower', route: '/watch-tower/overview' },
						{ label: 'Integrations', route: '/watch-tower/integrations' },
						{ label: data?.client_name || site, route: $route.fullPath },
					]"
				/>
			</Header>
		</div>

		<div class="p-5">
			<section class="wt-card flex flex-col">
				<div class="wt-card-h">
					<h3>AccuHub tasks</h3>
					<span class="sub mono">{{ site }}</span>
					<span v-if="data" class="more" title="Read from the client site when this page opened">read {{ data.read_at.slice(11, 16) }}</span>
				</div>
				<div class="wt-toolbar">
					<div class="tabs" role="group" aria-label="Stage">
						<template v-for="(s, i) in STAGES" :key="s.key">
							<span v-if="i" class="sep" aria-hidden="true">&rsaquo;</span>
							<button type="button" class="tab" :class="{ on: s.key === stage }" :aria-pressed="s.key === stage" :title="s.hint" @click="setStage(s.key)">
								{{ s.label }}<b v-if="data">{{ data.counts[s.key] }}</b>
							</button>
						</template>
					</div>
					<div class="picker">
						<button type="button" class="pick" :class="{ set: picked.length }" :aria-expanded="open" @click="open = !open">
							Project: {{ pickedLabel }}
						</button>
						<div v-if="open" class="backdrop" @click="open = false" />
						<div v-if="open" class="panel">
							<input v-model="query" type="search" placeholder="Search projects" aria-label="Search projects" />
							<label v-for="p in shownProjects" :key="p.project">
								<input type="checkbox" :checked="picked.includes(p.project)" @change="toggle(p.project)" />
								<span class="pname">{{ p.title }}</span>
								<span class="pcount">{{ total(p) }}</span>
							</label>
							<p v-if="!shownProjects.length" class="none">No project matches</p>
							<button v-if="picked.length" type="button" class="clear" @click="setProjects([])">Clear</button>
						</div>
					</div>
				</div>

				<div v-if="resource.loading && !data" class="space-y-2 p-4">
					<div v-for="i in 6" :key="i" class="h-8 animate-pulse rounded bg-gray-100" />
				</div>
				<div v-else-if="resource.error" class="p-8 text-center text-base text-gray-700">
					<p class="font-medium text-gray-900">Could not read the tasks from the client site</p>
					<p class="mt-1">{{ errorText }}</p>
					<button class="wt-btn mt-3" @click="resource.reload()">Try again</button>
				</div>
				<div v-else-if="data && !data.rows.length" class="p-8 text-center text-base text-gray-600">
					<p class="font-medium text-gray-900">No task in this stage</p>
					<p v-if="picked.length" class="mt-1">for the picked projects</p>
				</div>
				<div v-else-if="data" class="overflow-x-auto" :class="{ 'opacity-50': resource.loading }">
					<table class="wt-table tree">
						<thead>
							<tr>
								<th>Task</th>
								<th>Project</th>
								<th>Developer</th>
								<th>AccuHub state</th>
								<th>Created by</th>
								<th>Created on</th>
								<th>Assigned on</th>
								<th>Last change</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="t in data.rows"
								:key="t.task"
								:class="{ head: isHeading(t) }"
								:title="isHeading(t) ? 'Not in this stage: shown so its tasks sit under it' : undefined"
							>
								<td class="task">
									<div class="cell" :style="{ paddingInlineStart: indent(t) }">
										<lucide-folder v-if="t.is_group" class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
										<a class="name" :href="t.url" target="_blank" rel="noopener" :title="`${t.subject}: opens the task on the client site`">{{ t.subject }}</a>
									</div>
								</td>
								<td>{{ t.title }}</td>
								<td>
									<template v-if="!isHeading(t)"><span v-if="t.developer">{{ t.developer }}</span><span v-else class="zero">Not assigned</span></template>
								</td>
								<td>{{ t.accuhub_state || (isHeading(t) ? '' : '-') }}</td>
								<td :title="t.created_by"><span class="who">{{ t.created_by }}</span></td>
								<td class="mono" :title="t.created_on">{{ taskDay(t.created_on) }}</td>
								<td class="mono" :title="t.assigned_on">{{ taskDay(t.assigned_on) }}</td>
								<td class="mono">{{ isHeading(t) ? '' : when(t.modified) }}</td>
							</tr>
						</tbody>
					</table>
					<p v-if="stageCount(data.rows) >= 200" class="sub2 px-4 py-2">The newest 200 tasks of this stage.</p>
				</div>
			</section>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { createResource } from 'frappe-ui';
import { STAGES, MONTHS, isHeading, stageCount, indent, taskDay } from './integrations';

const props = defineProps({ site: { type: String, required: true } });
const route = useRoute();
const router = useRouter();
const open = ref(false);
const query = ref('');

const stage = computed(() => (STAGES.some((s) => s.key === route.query.stage) ? route.query.stage : 'backlog'));
// ?project=a&project=b; "" is the tasks with no project
const picked = computed(() => {
	const q = route.query.project;
	return q === undefined ? [] : [].concat(q).map((p) => p ?? '');
});

// GET: the hub method answers GET only (a read); frappe-ui posts by default, which Frappe refuses as Not permitted
const resource = createResource({
	url: 'sanad_ai_control_center.watch_tower_hub.integrations.get_stage_tasks',
	method: 'GET',
	makeParams: () => ({ site: props.site, stage: stage.value, projects: JSON.stringify(picked.value) }),
	auto: true,
});
watch(
	() => route.fullPath,
	() => route.name === 'Watch Tower Integration Tasks' && resource.reload(), // not on the way out
);
const data = computed(() => resource.data);
const errorText = computed(
	() => resource.error?.messages?.[0] || resource.error?.message || 'Not permitted: needs the Watch Tower Hub or System Manager role.',
);

const titleOf = (project) => data.value?.projects.find((p) => p.project === project)?.title || project || 'No project';
const pickedLabel = computed(() => {
	if (!picked.value.length) return 'All';
	return picked.value.length === 1 ? titleOf(picked.value[0]) : `${picked.value.length} projects`;
});
const shownProjects = computed(() => {
	const q = query.value.trim().toLowerCase();
	return (data.value?.projects || []).filter((p) => !q || p.title.toLowerCase().includes(q));
});
const total = (p) => STAGES.reduce((n, s) => n + p[s.key], 0);

function setStage(key) {
	router.replace({ query: { ...route.query, stage: key } });
}
function setProjects(list) {
	router.replace({ query: { stage: stage.value, ...(list.length ? { project: list } : {}) } });
}
function toggle(project) {
	setProjects(picked.value.includes(project) ? picked.value.filter((p) => p !== project) : [...picked.value, project]);
}
const when = (stamp) => (stamp ? `${Number(stamp.slice(8, 10))} ${MONTHS[Number(stamp.slice(5, 7)) - 1]}, ${stamp.slice(11, 16)}` : '-');
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
.tabs {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: 6px;
}
.sep {
	color: #c2c6cb;
}
.tab,
.pick {
	height: 36px;
	border: 1px solid #dfe1e4;
	background: #fff;
	padding: 0 12px;
	font-size: 13px;
	color: #525a64;
}
.tab b {
	margin-left: 6px;
	font-variant-numeric: tabular-nums;
}
.tab.on,
.pick.set {
	background: #eef5f8;
	border-color: #9cc3d2;
	color: #1a5f7a;
	font-weight: 550;
}
.picker {
	position: relative;
	margin-left: auto;
}
.backdrop {
	position: fixed;
	inset: 0;
	z-index: 20;
}
.panel {
	position: absolute;
	right: 0;
	top: 42px;
	z-index: 21;
	width: 280px;
	max-height: 360px;
	overflow-y: auto;
	padding: 8px;
	background: #fff;
	border: 1px solid #e9eaec;
	border-radius: 8px;
	box-shadow: 0 6px 20px rgba(17, 24, 39, 0.08);
}
.panel input[type='search'] {
	width: 100%;
	margin-bottom: 6px;
	border: 1px solid #dfe1e4;
	padding: 0 10px;
	font-size: 13px;
}
.panel label {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 6px 4px;
	font-size: 13px;
	color: #1c2024;
	cursor: pointer;
}
.pname {
	flex: 1;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.pcount {
	color: #6b737b;
	font-variant-numeric: tabular-nums;
}
.none {
	padding: 6px 4px;
	font-size: 13px;
	color: #6b737b;
}
.clear {
	border: 0;
	background: none;
	padding: 6px 4px;
	font-size: 13px;
	color: #1a5f7a;
}
.zero {
	color: #a0a6ad;
}
/* the tree (prototype ACH-SP-06): eight columns fit at 1440 with 12px cell padding; a long title ends in an ellipsis */
.tree th,
.tree td {
	padding-left: 12px;
	padding-right: 12px;
}
.cell {
	display: flex;
	align-items: center;
	gap: 6px;
	max-width: 420px;
	color: #6b737b;
}
.cell a {
	min-width: 0;
	font-weight: 550;
	color: #1c2024;
	overflow: hidden;
	text-overflow: ellipsis;
}
.who {
	display: block;
	max-width: 200px;
	overflow: hidden;
	text-overflow: ellipsis;
}
.tree tr.head td {
	background: #f8f9fa;
	color: #6b737b;
}
.tree tr.head a.name {
	color: #525a64;
}
</style>
