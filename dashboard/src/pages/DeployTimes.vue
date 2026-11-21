<!-- Deploy Times (owner 2026-11-21, prototype PRS-SP-03): how long each developer's deploys run and which bench makes
them wait. Data from press.watch_tower.deploy_times.get_deploy_times (system users, cached 10 minutes). -->
<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs :items="[{ label: 'Deploy Times', route: '/deploy-times' }]" />
			</Header>
		</div>

		<div class="space-y-4 p-5">
			<div class="flex items-center gap-3">
				<div class="inline-flex overflow-hidden rounded border text-sm">
					<button
						v-for="d in [7, 30]"
						:key="d"
						class="px-3 py-1"
						:class="period === d ? 'bg-gray-100 font-medium text-gray-900' : 'text-gray-600'"
						@click="period = d"
					>
						Last {{ d }} days
					</button>
				</div>
				<span v-if="data" class="ml-auto text-sm text-gray-500">Press data, as of {{ data.today }}</span>
			</div>

			<div v-if="resource.loading && !data" class="space-y-4">
				<div class="grid grid-cols-2 gap-3 md:grid-cols-4">
					<div v-for="i in 4" :key="i" class="h-20 animate-pulse rounded-lg border bg-gray-50" />
				</div>
				<div class="h-72 animate-pulse rounded-lg border bg-gray-50" />
				<div class="h-48 animate-pulse rounded-lg border bg-gray-50" />
			</div>

			<div v-else-if="resource.error" class="rounded-lg border p-8 text-center text-base text-gray-700">
				<p class="font-medium text-gray-900">Could not load deploy times</p>
				<p class="mt-1">{{ errorText }}</p>
			</div>

			<template v-else-if="data">
				<div v-if="!now.deploys" class="rounded-lg border p-8 text-center text-base text-gray-700">
					<p class="font-medium text-gray-900">No deploys in this period</p>
					<p class="mt-1">Deploys appear here after their build finishes.</p>
				</div>

				<template v-else>
					<div class="grid grid-cols-2 gap-3 md:grid-cols-4">
						<div v-for="k in kpis" :key="k.label" class="rounded-lg border px-4 py-3">
							<div class="text-sm text-gray-600">{{ k.label }}</div>
							<div class="mt-0.5 text-xl font-semibold tabular-nums">{{ k.value }}</div>
							<div class="mt-0.5 text-sm" :class="k.tone">{{ k.change }}</div>
						</div>
					</div>

					<div class="grid gap-4 lg:grid-cols-5">
						<div class="rounded-lg border lg:col-span-3">
							<div class="flex items-baseline gap-2 border-b px-4 py-3">
								<h3 class="text-base font-semibold">Minutes in deploys per day</h3>
								<span class="text-sm text-gray-500">by developer; deploys running together count once</span>
							</div>
							<VChart class="h-72 w-full px-2" autoresize :option="chartOption" :init-options="{ renderer: 'svg' }" />
						</div>
						<div class="rounded-lg border lg:col-span-2">
							<div class="flex items-baseline gap-2 border-b px-4 py-3">
								<h3 class="text-base font-semibold">Where a deploy's time goes</h3>
								<span class="text-sm text-gray-500">typical deploy, last 30 days</span>
							</div>
							<div class="p-4">
								<div class="flex h-8 gap-0.5 overflow-hidden rounded">
									<div
										v-for="s in data.stages"
										:key="s.name"
										class="flex items-center justify-center text-xs font-semibold"
										:style="{ flex: Math.max(s.min, 0.05), background: STAGE_COLOR[s.kind], color: s.kind === 'wait' ? '#1c2024' : '#fff' }"
										:title="`${s.name}: ${s.min} min`"
									>
										{{ s.min >= 0.8 ? `${s.min}m` : '' }}
									</div>
								</div>
								<div class="mt-2 flex flex-wrap gap-4 text-sm text-gray-600">
									<span><span class="swatch" :style="{ background: STAGE_COLOR.work }" />Working</span>
									<span><span class="swatch" :style="{ background: STAGE_COLOR.wait }" />Waiting, nothing running</span>
									<span class="text-gray-500">{{ waiting }} of {{ stageTotal }} min is waiting</span>
								</div>
								<div class="mt-3 space-y-1.5 text-sm">
									<div v-for="s in data.stages" :key="s.name" class="flex justify-between gap-3">
										<span><span class="swatch" :style="{ background: STAGE_COLOR[s.kind] }" />{{ s.name }}</span>
										<span class="font-semibold tabular-nums">{{ s.min }} min</span>
									</div>
								</div>
							</div>
						</div>
					</div>

					<div class="rounded-lg border">
						<div class="flex items-baseline gap-2 border-b px-4 py-3">
							<h3 class="text-base font-semibold">Developers</h3>
							<span class="text-sm text-gray-500">last {{ period }} days, most minutes first</span>
						</div>
						<div class="overflow-x-auto">
							<table class="w-full text-sm">
								<thead>
									<tr class="border-b text-left text-gray-500">
										<th class="px-4 py-2 font-normal">Developer</th>
										<th class="px-4 py-2 text-right font-normal">Deploys</th>
										<th class="px-4 py-2 text-right font-normal">Failed</th>
										<th class="px-4 py-2 text-right font-normal">Minutes in deploys</th>
										<th class="px-4 py-2 text-right font-normal">Per working day</th>
										<th class="px-4 py-2 text-right font-normal">Typical (min)</th>
										<th class="px-4 py-2 text-right font-normal">Slowest (min)</th>
									</tr>
								</thead>
								<tbody>
									<tr v-for="r in developerRows" :key="r.id" class="border-b last:border-0">
										<td class="whitespace-nowrap px-4 py-2"><span class="swatch" :style="{ background: r.color }" />{{ r.name }}</td>
										<td class="px-4 py-2 text-right tabular-nums">{{ r.deploys }}</td>
										<td class="px-4 py-2 text-right tabular-nums">{{ r.failed }}</td>
										<td class="px-4 py-2 text-right font-semibold tabular-nums">{{ r.minutes }}</td>
										<td class="px-4 py-2 text-right tabular-nums">{{ r.perDay }}</td>
										<td class="px-4 py-2 text-right tabular-nums">{{ r.typical.toFixed(1) }}</td>
										<td class="px-4 py-2 text-right tabular-nums">{{ r.slowest.toFixed(1) }}</td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>

					<div class="rounded-lg border">
						<div class="flex items-baseline gap-2 border-b px-4 py-3">
							<h3 class="text-base font-semibold">Benches</h3>
							<span class="text-sm text-gray-500">last 30 days, most minutes first; heavy = typical deploy over 10 minutes</span>
						</div>
						<div class="overflow-x-auto">
							<table class="w-full text-sm">
								<thead>
									<tr class="border-b text-left text-gray-500">
										<th class="px-4 py-2 font-normal">Bench</th>
										<th class="px-4 py-2 text-right font-normal">Apps</th>
										<th class="px-4 py-2 text-right font-normal">Sites</th>
										<th class="px-4 py-2 text-right font-normal">Deploys</th>
										<th class="px-4 py-2 text-right font-normal">Typical (min)</th>
										<th class="px-4 py-2 text-right font-normal">Slowest</th>
										<th class="px-4 py-2 text-right font-normal">Build</th>
										<th class="px-4 py-2 text-right font-normal">Site update</th>
										<th class="px-4 py-2 font-normal">Main deployer</th>
									</tr>
								</thead>
								<tbody>
									<tr
										v-for="b in data.benches.slice(0, 12)"
										:key="b.group"
										class="cursor-pointer border-b last:border-0 hover:bg-gray-50"
										@click="$router.push({ name: 'Release Group Detail Deploys', params: { name: b.group } })"
									>
										<td class="whitespace-nowrap px-4 py-2">
											{{ b.bench }}
											<span v-if="b.typical >= 10 && b.deploys >= 5" class="heavy">heavy</span>
										</td>
										<td class="px-4 py-2 text-right tabular-nums">{{ b.apps }}</td>
										<td class="px-4 py-2 text-right tabular-nums">{{ b.sites }}</td>
										<td class="px-4 py-2 text-right tabular-nums">{{ b.deploys }}</td>
										<td class="px-4 py-2 text-right font-semibold tabular-nums">{{ b.typical.toFixed(1) }}</td>
										<td class="px-4 py-2 text-right tabular-nums">{{ b.slowest.toFixed(1) }}</td>
										<td class="px-4 py-2 text-right tabular-nums">{{ b.build.toFixed(1) }}</td>
										<td class="px-4 py-2 text-right tabular-nums">{{ b.site_update.toFixed(1) }}</td>
										<td class="whitespace-nowrap px-4 py-2 text-gray-500">{{ b.main }}</td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>
				</template>
			</template>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { createResource } from 'frappe-ui';
import { use } from 'echarts/core';
import { SVGRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components';
import VChart from 'vue-echarts';

use([SVGRenderer, BarChart, GridComponent, LegendComponent, TooltipComponent]);

// validated categorical slots 1-3 (dataviz palette) + gray for a fourth; stages: neutral work, amber wait
const COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#8b9198'];
const STAGE_COLOR = { work: '#3d4752', wait: '#eda100' };

const period = ref(30);
const resource = createResource({ url: 'press.watch_tower.deploy_times.get_deploy_times', auto: true });
const data = computed(() => resource.data);
const errorText = computed(() => resource.error?.messages?.[0] || resource.error?.message || 'Not permitted: system users only.');

function dayList(n, offset = 0) {
	const today = new Date(`${data.value.today}T00:00:00Z`);
	return Array.from({ length: n }, (_, i) => new Date(today - (n + offset - i) * 86400000).toISOString().slice(0, 10));
}
function summary(dev, days) {
	const out = { deploys: 0, failed: 0, minutes: 0, active: 0, typicals: [], slowest: 0 };
	for (const day of days) {
		const v = dev.days[day];
		if (!v) continue;
		out.deploys += v.deploys;
		out.failed += v.failed;
		out.minutes += v.minutes;
		out.active += 1;
		// the typical deploy: each day's typical counts once per deploy that day
		for (let i = 0; i < v.deploys; i++) out.typicals.push(v.typical);
		out.slowest = Math.max(out.slowest, v.slowest);
	}
	out.typicals.sort((a, b) => a - b);
	out.typical = out.typicals.length ? out.typicals[Math.floor(out.typicals.length / 2)] : 0;
	return out;
}
const developers = computed(() => {
	if (!data.value) return [];
	const month = dayList(30);
	return Object.entries(data.value.developers)
		.map(([id, d]) => ({ id, name: d.name, days: d.days, month: summary(d, month).minutes }))
		.sort((a, b) => b.month - a.month)
		.map((d, i) => ({ ...d, color: COLORS[Math.min(i, COLORS.length - 1)] }));
});
function totals(days) {
	const parts = developers.value.map((d) => summary(d, days));
	const typicals = parts.flatMap((p) => p.typicals).sort((a, b) => a - b);
	const deploys = parts.reduce((a, p) => a + p.deploys, 0);
	const failed = parts.reduce((a, p) => a + p.failed, 0);
	return {
		deploys,
		failedPct: deploys ? (100 * failed) / deploys : 0,
		minutes: parts.reduce((a, p) => a + p.minutes, 0),
		typical: typicals.length ? typicals[Math.floor(typicals.length / 2)] : 0,
	};
}
const now = computed(() => (data.value ? totals(dayList(period.value)) : { deploys: 0 }));
const before = computed(() => totals(dayList(period.value, period.value)));
function change(a, b, lowerIsBetter) {
	if (!b) return { change: 'no earlier period', tone: 'text-gray-500' };
	const pct = Math.round((100 * (a - b)) / b);
	if (pct === 0) return { change: `same as the previous ${period.value} days`, tone: 'text-gray-500' };
	const tone = lowerIsBetter === null ? 'text-gray-500' : (lowerIsBetter ? pct < 0 : pct > 0) ? 'text-green-700' : 'text-red-600';
	return { change: `${pct > 0 ? 'up' : 'down'} ${Math.abs(pct)}% from the previous ${period.value} days`, tone };
}
const kpis = computed(() => {
	const n = now.value, b = before.value;
	const hours = (m) => (m >= 120 ? `${(m / 60).toFixed(1)} h` : `${m} min`);
	return [
		{ label: 'Deploys', value: n.deploys, ...change(n.deploys, b.deploys, null) },
		{ label: 'Failed', value: `${n.failedPct.toFixed(0)}%`, ...change(n.failedPct, b.failedPct, true) },
		{ label: 'Minutes in deploys', value: hours(n.minutes), ...change(n.minutes, b.minutes, true) },
		{ label: 'Typical deploy', value: `${n.typical.toFixed(1)} min`, ...change(n.typical, b.typical, true) },
	];
});
const developerRows = computed(() =>
	developers.value
		.map((d) => ({ ...d, s: summary(d, dayList(period.value)) }))
		.filter((d) => d.s.deploys)
		.sort((a, b) => b.s.minutes - a.s.minutes)
		.map((d) => ({
			id: d.id, name: d.name, color: d.color, deploys: d.s.deploys, failed: d.s.failed, minutes: d.s.minutes,
			perDay: Math.round(d.s.minutes / Math.max(1, d.s.active)), typical: d.s.typical, slowest: d.s.slowest,
		})),
);
const chartOption = computed(() => {
	const days = dayList(period.value);
	// whole-hour ticks: four steps sized from the busiest day (ECharts' own ticks fall between hours)
	const busiest = Math.max(60, ...days.map((day) => developers.value.reduce((a, d) => a + (d.days[day]?.minutes || 0), 0)));
	const stepHours = Math.max(1, Math.ceil(busiest / 60 / 4));
	return {
		grid: { left: 44, right: 16, top: 16, bottom: 56 },
		legend: { bottom: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10, textStyle: { color: '#6b7178' } },
		tooltip: {
			trigger: 'axis',
			axisPointer: { type: 'shadow' },
			valueFormatter: (v) => `${v} min`,
		},
		xAxis: {
			type: 'category',
			data: days.map((d) => `${d.slice(8)}/${d.slice(5, 7)}`),
			axisTick: { show: false },
			axisLine: { lineStyle: { color: '#dfe1e4' } },
			axisLabel: { color: '#8b9198', interval: period.value > 7 ? 4 : 0 },
		},
		yAxis: {
			type: 'value',
			min: 0,
			max: stepHours * 4 * 60,
			interval: stepHours * 60,
			splitLine: { lineStyle: { color: '#eceef0' } },
			axisLabel: { color: '#8b9198', formatter: (v) => (v ? `${Math.round(v / 60)} h` : '0') },
		},
		series: developers.value.map((d) => ({
			name: d.name,
			type: 'bar',
			stack: 'minutes',
			barMaxWidth: 28,
			itemStyle: { color: d.color, borderColor: '#fff', borderWidth: 1 },
			data: days.map((day) => d.days[day]?.minutes || 0),
		})),
	};
});
const stageTotal = computed(() => (data.value ? data.value.stages.reduce((a, s) => a + s.min, 0).toFixed(1) : 0));
const waiting = computed(() =>
	data.value ? data.value.stages.filter((s) => s.kind === 'wait').reduce((a, s) => a + s.min, 0).toFixed(1) : 0,
);
</script>

<style scoped>
.swatch {
	display: inline-block;
	width: 10px;
	height: 10px;
	border-radius: 2px;
	margin-right: 7px;
	vertical-align: -1px;
}
.heavy {
	margin-left: 6px;
	border-radius: 5px;
	padding: 0 7px;
	font-size: 11.5px;
	font-weight: 550;
	background: #fdf3d6;
	color: #8a5a00;
}
</style>
