<template>
	<div class="space-y-4">
		<!-- Summary cards -->
		<div class="grid grid-cols-5 gap-3" v-if="summary">
			<div class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
				<p class="text-xs font-medium uppercase text-gray-500">Health Score</p>
				<p class="mt-1 text-2xl font-bold" :style="{ color: healthColor(summary.health_pct) }">{{ summary.health_pct }}%</p>
				<div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
					<div class="h-full rounded-full" :style="{ width: summary.health_pct + '%', background: healthColor(summary.health_pct) }"></div>
				</div>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
				<p class="text-xs font-medium uppercase text-gray-500">Files</p>
				<p class="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{{ summary.total_files?.toLocaleString() }}</p>
				<p class="mt-1 text-xs text-gray-400">{{ summary.total_lines?.toLocaleString() }} lines</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
				<p class="text-xs font-medium uppercase text-gray-500">Clean</p>
				<p class="mt-1 text-2xl font-bold text-green-500">{{ summary.clean }}</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
				<p class="text-xs font-medium uppercase text-gray-500">Warnings</p>
				<p class="mt-1 text-2xl font-bold text-yellow-500">{{ summary.warning }}</p>
			</div>
			<div class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
				<p class="text-xs font-medium uppercase text-gray-500">Violations</p>
				<p class="mt-1 text-2xl font-bold text-red-500">{{ summary.violation }}</p>
			</div>
		</div>

		<!-- Tabs -->
		<div class="flex border-b border-gray-200 dark:border-gray-700">
			<button v-for="t in tabs" :key="t.id"
				class="px-4 py-2 text-sm font-semibold border-b-2 transition-colors"
				:class="activeTab === t.id ? 'text-blue-500 border-blue-500' : 'text-gray-500 border-transparent hover:text-gray-700'"
				@click="activeTab = t.id">{{ t.label }}</button>
		</div>

		<!-- Loading -->
		<div v-if="scanning" class="flex h-64 items-center justify-center">
			<div class="text-center text-gray-500">
				<div class="mx-auto mb-3 h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent"></div>
				Scanning...
			</div>
		</div>

		<!-- Health Map -->
		<div v-show="activeTab === 'health' && !scanning" class="relative overflow-hidden rounded-lg border border-gray-200 bg-gray-950 dark:border-gray-700" style="height:500px">
			<svg ref="circlePack" class="h-full w-full"></svg>
			<div ref="tooltip" class="pointer-events-none absolute z-50 hidden rounded-lg border border-gray-600 bg-gray-800 px-3 py-2 text-xs shadow-lg" style="max-width:260px"></div>
			<div ref="sidebar" class="absolute right-0 top-0 z-40 hidden h-full w-64 overflow-y-auto border-l border-gray-700 bg-gray-900 p-3"></div>
			<div class="absolute bottom-3 left-3 flex gap-3 text-[10px] text-gray-500 z-10">
				<span><span class="inline-block h-2 w-2 rounded-full bg-green-500"></span> Clean</span>
				<span><span class="inline-block h-2 w-2 rounded-full bg-yellow-500"></span> Warning</span>
				<span><span class="inline-block h-2 w-2 rounded-full bg-red-500"></span> Violation</span>
			</div>
			<div class="absolute right-3 top-3 flex flex-col gap-1 z-20">
				<button @click="zoomIn" class="h-7 w-7 rounded border border-gray-600 bg-gray-800 text-white text-sm">+</button>
				<button @click="zoomOut" class="h-7 w-7 rounded border border-gray-600 bg-gray-800 text-white text-sm">&minus;</button>
				<button @click="zoomReset" class="h-7 w-7 rounded border border-gray-600 bg-gray-800 text-gray-400 text-[10px]">&#8634;</button>
			</div>
		</div>

		<!-- Radar Scores -->
		<div v-show="activeTab === 'radar' && !scanning" class="grid grid-cols-3 gap-4">
			<div v-for="app in appScores" :key="app.app" class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
				<div class="mb-2 flex items-center justify-between">
					<h3 class="text-sm font-semibold text-gray-900 dark:text-white">{{ app.app }}</h3>
					<Badge size="sm" :label="app.scores.overall + '%'" :theme="app.scores.overall >= 80 ? 'green' : app.scores.overall >= 50 ? 'orange' : 'red'" />
				</div>
				<svg :ref="'radar-' + app.app" width="220" height="220" class="mx-auto block"></svg>
			</div>
		</div>

		<!-- Compliance -->
		<div v-show="activeTab === 'compliance' && !scanning">
			<table class="w-full text-sm" v-if="compliance.length">
				<thead><tr class="border-b border-gray-200 bg-gray-50 text-xs uppercase text-gray-500 dark:border-gray-700 dark:bg-gray-800">
					<th class="px-3 py-2 text-left">App</th>
					<th v-for="c in complianceHeaders" :key="c" class="px-2 py-2 text-center">{{ c }}</th>
					<th class="px-3 py-2 text-right">Score</th>
				</tr></thead>
				<tbody>
					<tr v-for="app in compliance" :key="app.app" class="border-b border-gray-100 dark:border-gray-800" :class="app.compliance_pct < 40 ? 'bg-red-50 dark:bg-red-900/10' : ''">
						<td class="px-3 py-2 font-semibold text-gray-900 dark:text-white">{{ app.app }}</td>
						<td v-for="ch in app.checks" :key="ch.name" class="px-2 py-2 text-center">
							<span v-if="ch.status" class="text-green-500">&#10003;</span>
							<span v-else class="text-red-500">&#10007;</span>
						</td>
						<td class="px-3 py-2 text-right">
							<Badge size="sm" :label="app.compliance_pct + '%'" :theme="app.compliance_pct >= 80 ? 'green' : app.compliance_pct >= 50 ? 'orange' : 'red'" />
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

<script>
import { call } from 'frappe-ui';

const API = 'press.press.doctype.bench.bench_code_health';
const COLORS = { clean: '#3fb950', warning: '#d29922', violation: '#f85149', 'non-code': '#484f58' };

export default {
	name: 'BenchCodeHealth',
	props: { benchName: { type: String, required: true } },
	data() {
		return {
			scanning: false, activeTab: 'health',
			summary: null, healthData: null, appScores: [], compliance: [],
			tabs: [
				{ id: 'health', label: 'Health Map' },
				{ id: 'radar', label: 'Radar Scores' },
				{ id: 'compliance', label: 'Compliance' },
			],
			_focus: null, _packed: null, _view: null,
		};
	},
	computed: {
		complianceHeaders() {
			if (!this.compliance.length) return [];
			return this.compliance[0].checks.map(c => c.name);
		},
	},
	mounted() { this.scan(); },
	methods: {
		healthColor(pct) { return pct >= 80 ? '#3fb950' : pct >= 50 ? '#d29922' : '#f85149'; },
		async scan() {
			this.scanning = true;
			try {
				const [summary, health, scores, comp] = await Promise.all([
					call(`${API}.get_health_summary`, { bench_name: this.benchName }),
					call(`${API}.scan_bench_health`, { bench_name: this.benchName }),
					call(`${API}.get_app_scores`, { bench_name: this.benchName }),
					call(`${API}.get_docs_compliance`, { bench_name: this.benchName }),
				]);
				this.summary = summary;
				this.healthData = health;
				this.appScores = scores;
				this.compliance = comp;
				this.$nextTick(() => {
					this.renderCirclePack();
					this.renderRadars();
				});
			} catch (e) {
				console.error('Scan failed:', e);
			} finally {
				this.scanning = false;
			}
		},
		renderCirclePack() {
			if (!this.healthData || !this.$refs.circlePack) return;
			const d3 = window.d3; if (!d3) return;
			const svg = d3.select(this.$refs.circlePack);
			const el = this.$refs.circlePack;
			const w = el.clientWidth, h = el.clientHeight;
			svg.selectAll('*').remove();
			svg.attr('viewBox', [-w/2, -h/2, w, h]).style('cursor', 'pointer');

			const hier = d3.hierarchy(this.healthData)
				.sum(d => d.children ? 0 : Math.max(d.lines || 1, 4))
				.sort((a, b) => (b.value || 0) - (a.value || 0));
			const packed = d3.pack().size([w-4, h-4]).padding(3)(hier);

			this._packed = packed;
			this._focus = packed;
			this._view = [packed.x, packed.y, packed.r * 2];

			const dirs = svg.append('g').selectAll('circle')
				.data(packed.descendants().filter(d => d.children)).join('circle')
				.attr('fill', 'none')
				.attr('stroke', d => { const p = d.data.health_pct || 0; return p >= 80 ? '#238636' : p >= 50 ? '#9e6a03' : '#da3633'; })
				.attr('stroke-width', d => d.depth < 1 ? 2 : 1).attr('stroke-opacity', 0.5)
				.style('cursor', 'pointer')
				.on('click', (e, d) => { e.stopPropagation(); this._zoom(d, svg, dirs, files, labels, w); });

			const tt = this.$refs.tooltip;
			const sb = this.$refs.sidebar;
			const ctr = el.parentElement;
			const files = svg.append('g').selectAll('circle')
				.data(packed.leaves()).join('circle')
				.attr('fill', d => COLORS[d.data.health] || '#484f58')
				.attr('fill-opacity', d => d.data.health === 'non-code' ? 0.35 : 0.8)
				.attr('stroke', d => d.data.health === 'violation' ? '#f85149' : 'none').attr('stroke-width', 2)
				.style('cursor', 'pointer')
				.on('mouseover', (e, d) => { const hc = COLORS[d.data.health] || '#8b949e'; tt.innerHTML = `<div class="font-semibold text-white">${d.data.name}</div><div class="text-gray-400">${d.data.lines||0} lines</div><div class="mt-1 font-semibold" style="color:${hc}">${(d.data.health||'').toUpperCase()}</div>`; tt.classList.remove('hidden'); })
				.on('mousemove', (e) => { const r = ctr.getBoundingClientRect(); tt.style.left = (e.clientX-r.left+12)+'px'; tt.style.top = (e.clientY-r.top-10)+'px'; })
				.on('mouseout', () => { tt.classList.add('hidden'); })
				.on('click', (e, d) => { e.stopPropagation(); if (d.parent && d.parent !== this._focus) this._zoom(d.parent, svg, dirs, files, labels, w); this._showSidebar(d, sb); });

			const labels = svg.append('g').selectAll('text')
				.data(packed.descendants().filter(d => d.children && d.depth > 0)).join('text')
				.attr('text-anchor', 'middle').attr('fill', '#8b949e').attr('pointer-events', 'none');

			svg.on('click', () => { if (this._focus?.parent) this._zoom(this._focus.parent, svg, dirs, files, labels, w); else this._zoom(packed, svg, dirs, files, labels, w); sb.classList.add('hidden'); });
			svg.on('wheel', (e) => { e.preventDefault(); e.deltaY < 0 ? this.zoomIn() : this.zoomOut(); });

			this._zoomTo(this._view, dirs, files, labels, w);
			this._els = { svg, dirs, files, labels, w };
		},
		_zoomTo(v, dirs, files, labels, w) {
			const k = w / v[2]; this._view = v;
			dirs.attr('cx', d => (d.x-v[0])*k).attr('cy', d => (d.y-v[1])*k).attr('r', d => d.r*k);
			files.attr('cx', d => (d.x-v[0])*k).attr('cy', d => (d.y-v[1])*k).attr('r', d => d.r*k);
			labels.attr('x', d => (d.x-v[0])*k).attr('y', d => ((d.y-d.r)-v[1])*k+12)
				.attr('font-size', d => Math.max(7, Math.min(12, d.r*k/4)))
				.attr('display', d => d.r*k > 25 ? 'block' : 'none').text(d => d.data.name);
		},
		_zoom(d, svg, dirs, files, labels, w) {
			this._focus = d;
			const d3 = window.d3;
			svg.transition().duration(400).tween('z', () => {
				const i = d3.interpolateZoom(this._view, [d.x, d.y, d.r * 4]);
				return t => this._zoomTo(i(t), dirs, files, labels, w);
			});
		},
		_showSidebar(d, sb) {
			const hc = COLORS[d.data.health] || '#8b949e';
			const path = []; let n = d; while (n.parent) { path.unshift(n.data.name); n = n.parent; }
			sb.innerHTML = `<div class="flex justify-between items-center mb-2"><span class="font-semibold text-white text-sm">${d.data.name}</span><button onclick="this.parentElement.parentElement.classList.add('hidden')" class="text-gray-400 text-lg">&times;</button></div>`
				+ `<div class="text-[10px] text-gray-500 break-all mb-3">${path.join('/')}</div>`
				+ `<div class="flex justify-between py-1.5 border-b border-gray-800 text-xs"><span class="text-gray-500">Lines</span><span>${d.data.lines||0}</span></div>`
				+ `<div class="flex justify-between py-1.5 border-b border-gray-800 text-xs"><span class="text-gray-500">Health</span><span style="color:${hc}" class="font-semibold">${(d.data.health||'').toUpperCase()}</span></div>`
				+ (d.data.lines > 700 ? '<div class="mt-3 rounded bg-red-900/30 border border-red-500 p-2 text-xs text-red-400 font-semibold">MUST SPLIT — exceeds 700 lines</div>' : '')
				+ (d.data.lines > 500 && d.data.lines <= 700 ? '<div class="mt-3 rounded bg-yellow-900/30 border border-yellow-500 p-2 text-xs text-yellow-400 font-semibold">Plan split — approaching limit</div>' : '');
			sb.classList.remove('hidden');
		},
		zoomIn() { if (this._focus?.children && this._els) { const b = this._focus.children.reduce((a, b) => (b.value||0) > (a.value||0) ? b : a); this._zoom(b, this._els.svg, this._els.dirs, this._els.files, this._els.labels, this._els.w); } },
		zoomOut() { if (this._focus?.parent && this._els) this._zoom(this._focus.parent, this._els.svg, this._els.dirs, this._els.files, this._els.labels, this._els.w); },
		zoomReset() { if (this._packed && this._els) this._zoom(this._packed, this._els.svg, this._els.dirs, this._els.files, this._els.labels, this._els.w); },
		renderRadars() {
			const d3 = window.d3; if (!d3) return;
			const dims = ['CLAUDE', 'README', 'Docs', 'Tests', 'Clean', 'Patterns', 'Lessons', 'Security'];
			const keys = ['claude_md', 'readme', 'documentation', 'tests', 'clean_code', 'code_patterns', 'lessons', 'security'];
			for (const app of this.appScores) {
				const ref = this.$refs['radar-' + app.app];
				const el = Array.isArray(ref) ? ref[0] : ref;
				if (!el) continue;
				const svg = d3.select(el); svg.selectAll('*').remove();
				const w = 220, h = 220, cx = w/2, cy = h/2, r = 80;
				const g = svg.append('g').attr('transform', `translate(${cx},${cy})`);
				const n = dims.length, a = 2 * Math.PI / n;
				[0.25,0.5,0.75,1].forEach(l => g.append('circle').attr('r', r*l).attr('fill','none').attr('stroke','#e5e7eb').attr('stroke-width',0.5));
				dims.forEach((d, i) => { const an = a*i - Math.PI/2; g.append('line').attr('x1',0).attr('y1',0).attr('x2',r*Math.cos(an)).attr('y2',r*Math.sin(an)).attr('stroke','#e5e7eb').attr('stroke-width',0.5); g.append('text').attr('x',(r+14)*Math.cos(an)).attr('y',(r+14)*Math.sin(an)).attr('text-anchor','middle').attr('dominant-baseline','middle').attr('fill','#9ca3af').attr('font-size',8).text(d); });
				const scores = keys.map(k => app.scores[k] || 0);
				const pts = scores.map((s, i) => { const an = a*i - Math.PI/2; return [r*(s/100)*Math.cos(an), r*(s/100)*Math.sin(an)]; }); pts.push(pts[0]);
				g.append('path').datum(pts).attr('d', d3.line().x(d=>d[0]).y(d=>d[1])).attr('fill','rgba(59,130,246,0.15)').attr('stroke','#3b82f6').attr('stroke-width',1.5);
				scores.forEach((s, i) => { const an = a*i - Math.PI/2; g.append('circle').attr('cx',r*(s/100)*Math.cos(an)).attr('cy',r*(s/100)*Math.sin(an)).attr('r',3).attr('fill', s>=80?'#22c55e':s>=50?'#eab308':'#ef4444'); });
			}
		},
	},
};
</script>
