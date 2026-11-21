<!-- Watch Tower (owner 2026-11-21, prototype ACM-SP-02, Production first): which client site needs action. Data from
sanad_ai_control_center.watch_tower_hub.overview.get_overview (Watch Tower Hub or System Manager, kept a minute; the hub
reads every site every 5 minutes). Rows open the desk records. -->
<template>
	<div class="flex h-full flex-col">
		<div class="sticky top-0 z-10 shrink-0">
			<Header>
				<Breadcrumbs :items="[{ label: 'Watch Tower', route: '/watch-tower' }]" />
			</Header>
		</div>

		<div class="space-y-4 p-5">
			<div v-if="resource.loading && !data" class="space-y-4">
				<div class="grid grid-cols-5 gap-2">
					<div v-for="i in 5" :key="i" class="h-10 animate-pulse rounded-lg border bg-gray-50" />
				</div>
				<div v-for="i in 3" :key="i" class="h-48 animate-pulse rounded-lg border bg-gray-50" />
			</div>

			<div v-else-if="resource.error" class="rounded-lg border p-8 text-center text-base text-gray-700">
				<p class="font-medium text-gray-900">Could not load Watch Tower</p>
				<p class="mt-1">{{ errorText }}</p>
				<button class="mt-3 text-sm font-medium text-gray-900 underline" @click="resource.reload()">Try again</button>
			</div>

			<template v-else-if="data">
				<div class="flex items-center">
					<div class="grid flex-1 grid-cols-5 gap-2 md:flex md:flex-none md:gap-2">
						<div
							v-for="c in chips"
							:key="c.status"
							class="flex flex-col items-center rounded-lg border px-3 py-1.5 text-sm text-gray-600 md:flex-row md:gap-1.5"
						>
							<span class="text-base font-semibold tabular-nums" :class="c.count ? c.tone : 'text-gray-900'">{{ c.count }}</span>
							{{ c.status }}
						</div>
					</div>
					<span class="ml-auto hidden text-sm text-gray-500 md:inline">
						The hub reads every site every 5 minutes · as of {{ data.as_of.slice(11, 16) }}
					</span>
				</div>

				<div v-if="!data.sites.length" class="rounded-lg border p-8 text-center text-base text-gray-700">
					<p class="font-medium text-gray-900">No client sites connected yet</p>
					<p class="mt-1">Add one in the desk: Monitored Site, then Connect and test.</p>
				</div>

				<template v-else>
					<section class="rounded-lg border">
						<div class="flex items-baseline gap-2 border-b px-4 py-3">
							<h3 class="text-base font-semibold">Client sites</h3>
							<span class="text-sm text-gray-500">Production first, then the ones that need action</span>
							<a class="ml-auto text-sm text-gray-600 hover:text-gray-900" href="/app/monitored-site">All in the desk</a>
						</div>
						<div class="overflow-x-auto">
							<table class="w-full text-base">
								<thead>
									<tr class="border-b text-left text-sm text-gray-600">
										<th class="px-4 py-2 font-medium">Client</th>
										<th class="px-4 py-2 font-medium">Environment</th>
										<th class="hidden px-4 py-2 font-medium lg:table-cell">Site</th>
										<th class="px-4 py-2 font-medium">Status</th>
										<th class="px-4 py-2 font-medium">Last read</th>
										<th class="px-4 py-2 text-right font-medium">Critical</th>
										<th class="px-4 py-2 text-right font-medium">High</th>
										<th class="px-4 py-2 text-right font-medium">Errors 24 h</th>
										<th class="px-4 py-2 font-medium">Email</th>
										<th class="hidden px-4 py-2 font-medium md:table-cell">Read problem</th>
									</tr>
								</thead>
								<tbody>
									<tr
										v-for="s in data.sites"
										:key="s.name"
										class="cursor-pointer border-b last:border-0 hover:bg-gray-50"
										@click="openDesk(`/app/monitored-site/${encodeURIComponent(s.name)}`)"
									>
										<td class="whitespace-nowrap px-4 py-2">{{ s.client_name }}</td>
										<td class="whitespace-nowrap px-4 py-2 text-gray-700">{{ s.environment }}</td>
										<td class="hidden whitespace-nowrap px-4 py-2 font-mono text-sm text-gray-600 lg:table-cell">{{ s.name }}</td>
										<td class="px-4 py-2"><span class="badge" :class="STATUS[s.status] || 'b-gray'">{{ s.status }}</span></td>
										<td class="whitespace-nowrap px-4 py-2 text-gray-600">{{ ago(s.last_read_at) }}</td>
										<td class="px-4 py-2 text-right tabular-nums" :class="s.open_critical ? 'font-semibold text-red-700' : ''">{{ s.open_critical }}</td>
										<td class="px-4 py-2 text-right tabular-nums">{{ s.open_high }}</td>
										<td class="px-4 py-2 text-right tabular-nums" :class="s.errors_24h ? 'text-amber-700' : ''" :title="topErrors(s)">{{ s.errors_24h }}</td>
										<td class="whitespace-nowrap px-4 py-2">{{ email(s) }}</td>
										<td class="hidden max-w-xs truncate px-4 py-2 text-sm text-gray-600 md:table-cell" :title="s.last_error">{{ s.last_error }}</td>
									</tr>
								</tbody>
							</table>
						</div>
					</section>

					<section class="rounded-lg border">
						<div class="flex items-baseline gap-2 border-b px-4 py-3">
							<h3 class="text-base font-semibold">Open Critical and High findings</h3>
							<span v-if="data.findings_total > data.findings.length" class="text-sm text-gray-500">
								showing {{ data.findings.length }} of {{ data.findings_total }}
							</span>
							<a class="ml-auto text-sm text-gray-600 hover:text-gray-900" href="/app/client-finding?status=Open">All in the desk</a>
						</div>
						<div v-if="!data.findings.length" class="p-8 text-center text-base text-gray-700">
							<p class="font-medium text-gray-900">No open Critical or High findings</p>
							<p class="mt-1">Medium and Low findings stay on each client's own board.</p>
						</div>
						<div v-else class="overflow-x-auto">
							<table class="w-full text-base">
								<thead>
									<tr class="border-b text-left text-sm text-gray-600">
										<th class="px-4 py-2 font-medium">Severity</th>
										<th class="px-4 py-2 font-medium">Client</th>
										<th class="px-4 py-2 font-medium">Finding</th>
										<th class="hidden px-4 py-2 font-medium md:table-cell">Person</th>
										<th class="hidden px-4 py-2 font-medium lg:table-cell">Subject</th>
										<th class="px-4 py-2 font-medium">Raised</th>
									</tr>
								</thead>
								<tbody>
									<tr
										v-for="f in data.findings"
										:key="f.name"
										class="cursor-pointer border-b last:border-0 hover:bg-gray-50"
										@click="openDesk(`/app/client-finding/${encodeURIComponent(f.name)}`)"
									>
										<td class="px-4 py-2"><span class="badge" :class="SEVERITY[f.severity]">{{ f.severity }}</span></td>
										<td class="whitespace-nowrap px-4 py-2">{{ f.client_name }}</td>
										<td class="px-4 py-2">{{ f.finding_type }}</td>
										<td class="hidden whitespace-nowrap px-4 py-2 font-mono text-sm text-gray-600 md:table-cell">{{ f.user }}</td>
										<td class="hidden px-4 py-2 lg:table-cell">{{ f.subject }}</td>
										<td class="whitespace-nowrap px-4 py-2 text-gray-600">{{ ago(f.raised_on) }}</td>
									</tr>
								</tbody>
							</table>
						</div>
					</section>

					<section class="rounded-lg border">
						<div class="flex items-baseline gap-2 border-b px-4 py-3">
							<h3 class="text-base font-semibold">Installed apps</h3>
							<span class="text-sm text-gray-500">
								against git: our apps marked older when behind; framework apps only when a whole major behind
							</span>
						</div>
						<div v-if="!appSites.length" class="p-8 text-center text-base text-gray-700">
							<p class="font-medium text-gray-900">No versions yet</p>
							<p class="mt-1">The hub reads them on its next run.</p>
						</div>
						<div v-else class="overflow-x-auto">
							<table class="w-full text-base">
								<thead>
									<tr class="border-b text-left text-sm text-gray-600">
										<th class="px-4 py-2 font-medium">App</th>
										<th class="whitespace-nowrap px-4 py-2 font-medium">Git</th>
										<th v-for="s in appSites" :key="s.name" class="whitespace-nowrap px-4 py-2 font-medium">{{ s.client_name }}</th>
									</tr>
								</thead>
								<tbody>
									<tr v-for="app in appNames" :key="app" class="border-b last:border-0">
										<td class="whitespace-nowrap px-4 py-1.5 font-mono text-sm">{{ app }}</td>
										<td class="whitespace-nowrap px-4 py-1.5 font-mono text-sm text-gray-600">{{ (data.git[app] || []).join(' / ') || '-' }}</td>
										<td v-for="s in appSites" :key="s.name" class="whitespace-nowrap px-4 py-1.5 font-mono text-sm" :title="cellTitle(s.apps[app])">
											<template v-if="s.apps[app]">
												{{ s.apps[app].version || '-' }}
												<span v-if="tag(app, s.apps[app])" class="tag">{{ tag(app, s.apps[app]) }}</span>
											</template>
											<span v-else class="text-gray-400">-</span>
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					</section>
				</template>
			</template>
		</div>
	</div>
</template>

<script setup>
import { computed } from 'vue';
import { createResource } from 'frappe-ui';

const STATUS = { Connected: 'b-green', Silent: 'b-amber', Revoked: 'b-red', Paused: 'b-red', New: 'b-gray' };
const SEVERITY = { Critical: 'b-red', High: 'b-amber' };
const CHIP_TONE = { Connected: 'text-green-700', Silent: 'text-amber-700', Revoked: 'text-red-700', Paused: 'text-red-700', New: 'text-gray-900' };
// framework apps trail by minor versions everywhere: only a whole major behind is worth a mark
const FRAMEWORK = new Set(['frappe', 'erpnext', 'hrms', 'payments', 'lending', 'insights', 'crm', 'webshop']);
const FIRST = ['frappe', 'erpnext'];

const resource = createResource({ url: 'sanad_ai_control_center.watch_tower_hub.overview.get_overview', auto: true });
const data = computed(() => resource.data);
const errorText = computed(
	() => resource.error?.messages?.[0] || resource.error?.message || 'Not permitted: needs the Watch Tower Hub or System Manager role.',
);

const chips = computed(() =>
	['Connected', 'Silent', 'Revoked', 'Paused', 'New'].map((status) => ({
		status,
		count: data.value.sites.filter((s) => s.status === status).length,
		tone: CHIP_TONE[status],
	})),
);
const appSites = computed(() => data.value.sites.filter((s) => Object.keys(s.apps || {}).length));
const appNames = computed(() =>
	[...new Set(appSites.value.flatMap((s) => Object.keys(s.apps)))].sort(
		(a, b) => (FIRST.indexOf(a) + 1 || 99) - (FIRST.indexOf(b) + 1 || 99) || a.localeCompare(b),
	),
);

// times are the hub's own clock (as_of comes from the same server), so the browser's time zone never skews them
function ago(when) {
	if (!when) return 'never';
	const at = (value) => Date.parse(value.slice(0, 19).replace(' ', 'T')); // microseconds: not every browser parses them
	const minutes = Math.round((at(data.value.as_of) - at(when)) / 60000);
	if (minutes < 1) return 'just now';
	if (minutes < 60) return `${minutes} min ago`;
	if (minutes < 1440) return `${Math.round(minutes / 60)} h ago`;
	return `${Math.round(minutes / 1440)} d ago`;
}
function topErrors(s) {
	return (s.top_errors || []).map((e) => `${e.count} x ${e.title}`).join('\n');
}
function email(s) {
	const parts = [s.email_failed && `${s.email_failed} failed`, s.email_stuck && `${s.email_stuck} stuck`].filter(Boolean);
	return parts.join(' · ') || '-';
}
function tag(app, cell) {
	if (cell.standing === 'major behind') return 'major behind';
	if (cell.standing === 'behind' && !FRAMEWORK.has(app)) return 'older';
	return '';
}
function cellTitle(cell) {
	return cell?.git ? `Git: ${cell.git}` : '';
}
function openDesk(path) {
	window.location.href = path;
}
</script>

<style scoped>
.badge {
	display: inline-block;
	border-radius: 5px;
	padding: 1px 8px;
	font-size: 12.5px;
	font-weight: 550;
	white-space: nowrap;
}
.b-green {
	background: #e7f4ec;
	color: #18794e;
}
.b-amber {
	background: #fdf3d6;
	color: #8a5a00;
}
.b-red {
	background: #c0392b;
	color: #fff;
}
.b-gray {
	background: #f0f1f2;
	color: #525a64;
}
.tag {
	margin-left: 6px;
	border-radius: 5px;
	padding: 0 6px;
	font-family: inherit;
	font-size: 11.5px;
	font-weight: 550;
	background: #fdf3d6;
	color: #8a5a00;
}
</style>
