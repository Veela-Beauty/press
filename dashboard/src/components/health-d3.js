/**
 * D3 rendering functions for BenchCodeHealth — circle pack + radar charts.
 * Extracted to keep BenchCodeHealth.vue under 500 lines.
 */
import * as d3 from 'd3';

const COLORS = { clean: '#3fb950', warning: '#d29922', violation: '#f85149', 'non-code': '#484f58' };

/**
 * Render circle-packing visualization into an SVG element.
 * Returns { svg, dirs, files, labels, w, packed, leaves } for zoom control.
 */
export function renderCirclePack(el, healthData, { tooltip, sidebar, breadcrumb, onZoom, onFilter, appRepos }) {
	const svg = d3.select(el);
	const w = el.clientWidth, h = el.clientHeight;
	svg.selectAll('*').remove();
	svg.attr('viewBox', [-w / 2, -h / 2, w, h]).style('cursor', 'pointer');

	const hier = d3.hierarchy(healthData)
		.sum(d => d.children ? 0 : Math.max(d.lines || 1, 4))
		.sort((a, b) => (b.value || 0) - (a.value || 0));
	const packed = d3.pack().size([w - 4, h - 4]).padding(3)(hier);

	const state = { focus: packed, view: [packed.x, packed.y, packed.r * 2], packed, bcNodes: [] };

	const dirs = svg.append('g').selectAll('circle')
		.data(packed.descendants().filter(d => d.children)).join('circle')
		.attr('fill', 'none')
		.attr('stroke', d => { const p = d.data.health_pct || 0; return p >= 80 ? '#238636' : p >= 50 ? '#9e6a03' : '#da3633'; })
		.attr('stroke-width', d => d.depth < 1 ? 2 : 1).attr('stroke-opacity', 0.5)
		.style('cursor', 'pointer')
		.on('click', (e, d) => { e.stopPropagation(); zoom(d); });

	const ctr = el.parentElement;
	const files = svg.append('g').selectAll('circle')
		.data(packed.leaves()).join('circle')
		.attr('fill', d => COLORS[d.data.health] || '#484f58')
		.attr('fill-opacity', d => d.data.health === 'non-code' ? 0.35 : 0.8)
		.attr('stroke', d => d.data.health === 'violation' ? '#f85149' : 'none').attr('stroke-width', 2)
		.style('cursor', 'pointer')
		.on('mouseover', (e, d) => {
			const c = COLORS[d.data.health] || '#8b949e';
			tooltip.innerHTML = `<div class="font-semibold text-white">${d.data.name}</div><div class="text-gray-400">${d.data.lines || 0} lines</div><div class="mt-1 font-semibold" style="color:${c}">${(d.data.health || '').toUpperCase()}</div>`;
			tooltip.classList.remove('hidden');
		})
		.on('mousemove', (e) => { const r = ctr.getBoundingClientRect(); tooltip.style.left = (e.clientX - r.left + 12) + 'px'; tooltip.style.top = (e.clientY - r.top - 10) + 'px'; })
		.on('mouseout', () => { tooltip.classList.add('hidden'); })
		.on('click', (e, d) => { e.stopPropagation(); if (d.parent && d.parent !== state.focus) zoom(d.parent); showSidebar(d); });

	const labels = svg.append('g').selectAll('text')
		.data(packed.descendants().filter(d => d.children && d.depth > 0)).join('text')
		.attr('text-anchor', 'middle').attr('fill', '#8b949e').attr('pointer-events', 'none');

	const els = { svg, dirs, files, labels, w };

	function zoomTo(v) {
		const k = w / v[2]; state.view = v;
		dirs.attr('cx', d => (d.x - v[0]) * k).attr('cy', d => (d.y - v[1]) * k).attr('r', d => d.r * k);
		files.attr('cx', d => (d.x - v[0]) * k).attr('cy', d => (d.y - v[1]) * k).attr('r', d => d.r * k);
		labels.attr('x', d => (d.x - v[0]) * k).attr('y', d => ((d.y - d.r) - v[1]) * k + 12)
			.attr('font-size', d => Math.max(7, Math.min(12, d.r * k / 4)))
			.attr('display', d => d.r * k > 25 ? 'block' : 'none').text(d => d.data.name);
	}

	function zoom(d) {
		state.focus = d;
		svg.transition().duration(400).tween('z', () => {
			const i = d3.interpolateZoom(state.view, [d.x, d.y, d.r * 4]);
			return t => zoomTo(i(t));
		});
		if (breadcrumb) {
			const nodes = []; let n = d; while (n) { nodes.unshift(n); n = n.parent; }
			state.bcNodes = nodes;
			breadcrumb.innerHTML = nodes.map((nd, idx) =>
				`<span style="cursor:pointer" data-bc-idx="${idx}">${nd.data.name}</span>`
			).join(' <span style="color:#8b949e">/</span> ');
			breadcrumb.querySelectorAll('[data-bc-idx]').forEach(el => {
				el.onclick = (e) => { e.stopPropagation(); zoom(state.bcNodes[parseInt(el.dataset.bcIdx)]); };
			});
		}
		if (onZoom) onZoom(d);
	}

	function showSidebar(d) {
		const c = COLORS[d.data.health] || '#8b949e';
		const path = []; let n = d; while (n.parent) { path.unshift(n.data.name); n = n.parent; }
		const fullPath = path.join('/');
		// Build GitHub link: first path segment = app name → look up repo
		const appName = path[0] || '';
		const repoPath = path.slice(1).join('/');
		const repo = appRepos?.[appName] || '';
		const ghLink = repo && repoPath ? `https://github.com/${repo}/blob/HEAD/${repoPath}` : '';

		sidebar.innerHTML = `<div class="flex justify-between items-center mb-2"><span class="font-semibold text-white text-sm">${d.data.name}</span><button onclick="this.parentElement.parentElement.classList.add('hidden')" class="text-gray-400 text-lg">&times;</button></div>`
			+ `<div class="text-[10px] text-gray-500 break-all mb-3">${fullPath}</div>`
			+ `<div class="flex justify-between py-1.5 border-b border-gray-800 text-xs"><span class="text-gray-500">Lines</span><span>${d.data.lines || 0}</span></div>`
			+ `<div class="flex justify-between py-1.5 border-b border-gray-800 text-xs"><span class="text-gray-500">Extension</span><span>${d.data.ext || '\u2014'}</span></div>`
			+ `<div class="flex justify-between py-1.5 border-b border-gray-800 text-xs"><span class="text-gray-500">Health</span><span style="color:${c}" class="font-semibold">${(d.data.health || '').toUpperCase()}</span></div>`
			+ (ghLink ? `<a href="${ghLink}" target="_blank" class="mt-3 flex items-center gap-1.5 rounded bg-gray-800 border border-gray-700 p-2 text-xs text-blue-400 hover:text-blue-300 hover:border-blue-500"><svg class="h-3.5 w-3.5 flex-shrink-0" fill="currentColor" viewBox="0 0 16 16"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>View on GitHub</a>` : '')
			+ (d.data.lines > 700 ? '<div class="mt-3 rounded bg-red-900/30 border border-red-500 p-2 text-xs text-red-400 font-semibold">MUST SPLIT \u2014 exceeds 700 lines</div>' : '')
			+ (d.data.lines > 500 && d.data.lines <= 700 ? '<div class="mt-3 rounded bg-yellow-900/30 border border-yellow-500 p-2 text-xs text-yellow-400 font-semibold">Plan split \u2014 approaching limit</div>' : '');
		sidebar.classList.remove('hidden');
	}

	svg.on('click', () => { if (state.focus?.parent) zoom(state.focus.parent); else zoom(packed); sidebar.classList.add('hidden'); });
	svg.on('wheel', (e) => { e.preventDefault(); e.deltaY < 0 ? zoomInFn() : zoomOutFn(); });

	function zoomInFn() { if (state.focus?.children) { const b = state.focus.children.reduce((a, c) => (c.value || 0) > (a.value || 0) ? c : a); zoom(b); } }
	function zoomOutFn() { if (state.focus?.parent) zoom(state.focus.parent); }
	function zoomResetFn() { zoom(packed); }

	zoomTo(state.view);

	return { els, state, leaves: packed.leaves(), zoomIn: zoomInFn, zoomOut: zoomOutFn, zoomReset: zoomResetFn, applyFilters(healthFilters, extFilters) {
		const activeH = new Set(healthFilters.filter(f => f.active).map(f => f.key));
		const activeE = new Set(extFilters.filter(f => f.active).map(f => f.ext));
		let visible = 0;
		files.each(function(d) {
			const h = d.data.health || 'non-code';
			const ext = d.data.ext || '';
			const show = activeH.has(h) && (activeE.has(ext) || (!ext && activeH.has('non-code')));
			d3.select(this).attr('opacity', show ? (h === 'non-code' ? 0.35 : 0.8) : 0.03);
			if (show) visible++;
		});
		return visible;
	}, destroy() { svg.on('click', null); svg.on('wheel', null); svg.selectAll('*').remove(); } };
}

/**
 * Draw a radar chart into an SVG selection.
 */
export function drawRadar(svgSel, scores, w, h, dims) {
	svgSel.selectAll('*').remove();
	const cx = w / 2, cy = h / 2, r = Math.min(w, h) / 2 - 20;
	const g = svgSel.append('g').attr('transform', `translate(${cx},${cy})`);
	const n = dims.length, a = 2 * Math.PI / n;
	[0.25, 0.5, 0.75, 1].forEach(l => g.append('circle').attr('r', r * l).attr('fill', 'none').attr('stroke', '#e5e7eb').attr('stroke-width', 0.5));
	dims.forEach((d, i) => {
		const an = a * i - Math.PI / 2;
		g.append('line').attr('x1', 0).attr('y1', 0).attr('x2', r * Math.cos(an)).attr('y2', r * Math.sin(an)).attr('stroke', '#e5e7eb').attr('stroke-width', 0.5);
		g.append('text').attr('x', (r + 14) * Math.cos(an)).attr('y', (r + 14) * Math.sin(an)).attr('text-anchor', 'middle').attr('dominant-baseline', 'middle').attr('fill', '#9ca3af').attr('font-size', 8).text(d);
	});
	const pts = scores.map((s, i) => { const an = a * i - Math.PI / 2; return [r * (s / 100) * Math.cos(an), r * (s / 100) * Math.sin(an)]; });
	pts.push(pts[0]);
	g.append('path').datum(pts).attr('d', d3.line().x(d => d[0]).y(d => d[1])).attr('fill', 'rgba(59,130,246,0.15)').attr('stroke', '#3b82f6').attr('stroke-width', 1.5);
	scores.forEach((s, i) => { const an = a * i - Math.PI / 2; g.append('circle').attr('cx', r * (s / 100) * Math.cos(an)).attr('cy', r * (s / 100) * Math.sin(an)).attr('r', 3).attr('fill', s >= 80 ? '#22c55e' : s >= 50 ? '#eab308' : '#ef4444'); });
}
