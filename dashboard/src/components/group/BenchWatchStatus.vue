<template>
	<!-- Watch panel — self-hides when the bench isn't a Dev Bench so this
	     component is safe to mount unconditionally on any bench surface. -->
	<div
		v-if="!status || status.is_dev_bench !== false"
		class="overflow-hidden rounded-lg border border-gray-200 bg-gray-50"
	>
		<div class="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-2.5">
			<div class="flex items-center gap-2">
				<span class="text-xs font-semibold text-gray-900">Auto-Rebuild (bench watch)</span>
				<span
					class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium"
					:class="badgeClass"
				>
					<span class="h-1.5 w-1.5 rounded-full" :class="dotClass"></span>
					{{ badgeLabel }}
				</span>
			</div>
			<div class="flex items-center gap-1.5">
				<button
					v-if="!loading"
					type="button"
					class="text-[11px] text-gray-500 transition hover:text-gray-900"
					@click="refresh()"
					title="Refresh status"
				>
					<FeatherIcon name="refresh-cw" class="h-3 w-3" />
				</button>
				<button
					v-if="!status?.running && !restarting"
					type="button"
					class="rounded border border-blue-200 bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700 transition hover:bg-blue-100"
					@click="restart()"
				>
					Start watch
				</button>
				<span v-if="restarting" class="text-[11px] text-gray-500">Starting…</span>
			</div>
		</div>

		<div class="grid grid-cols-[90px_1fr] items-center gap-3 px-4 py-2 text-[12.5px]">
			<div class="text-[11px] font-medium uppercase tracking-wider text-gray-500">PID</div>
			<div class="font-mono text-gray-700">{{ status?.pid || '—' }}</div>
		</div>

		<div v-if="status?.log_tail" class="border-t border-gray-200 bg-gray-900 px-4 py-2">
			<div class="mb-1 text-[10px] uppercase tracking-wider text-gray-400">Last 5 log lines</div>
			<pre class="overflow-x-auto whitespace-pre-wrap break-words text-[11px] leading-snug text-gray-200">{{ status.log_tail }}</pre>
		</div>

		<div v-else-if="!status?.running" class="border-t border-gray-200 px-4 py-2 text-[11px] text-gray-500">
			Watch is not running. Edit-on-save rebuild is OFF — JS/CSS edits won't reflect until you start it.
		</div>

		<div v-else class="border-t border-gray-200 px-4 py-2 text-[11px] text-gray-500">
			Edit a JS/CSS file in any app → ~1s rebuild → hard-reload your browser (Ctrl + F5).
		</div>
	</div>
</template>

<script>
import { call, FeatherIcon } from 'frappe-ui';
import { toast } from 'vue-sonner';

const POLL_MS = 10000;

export default {
	name: 'BenchWatchStatus',
	components: { FeatherIcon },
	props: { benchName: { type: String, required: true } },
	data() {
		return {
			status: null,
			loading: false,
			restarting: false,
			pollTimer: null,
		};
	},
	computed: {
		badgeLabel() {
			if (this.loading && !this.status) return 'checking…';
			if (this.restarting) return 'starting…';
			return this.status?.running ? 'running' : 'stopped';
		},
		badgeClass() {
			if (this.status?.running) return 'bg-green-100 text-green-700';
			if (this.restarting || this.loading) return 'bg-gray-100 text-gray-600';
			return 'bg-orange-100 text-orange-700';
		},
		dotClass() {
			if (this.status?.running) return 'bg-green-500';
			if (this.restarting || this.loading) return 'bg-gray-400 animate-pulse';
			return 'bg-orange-500';
		},
	},
	mounted() {
		this.refresh();
		this.pollTimer = setInterval(() => this.refresh({ silent: true }), POLL_MS);
	},
	beforeUnmount() {
		if (this.pollTimer) clearInterval(this.pollTimer);
	},
	methods: {
		async refresh({ silent = false } = {}) {
			if (!silent) this.loading = true;
			try {
				const res = await call(
					'press.press.doctype.bench.bench_dev_watch.get_watch_status',
					{ bench_name: this.benchName }
				);
				this.status = res || res?.message || null;
			} catch (e) {
				if (!silent) toast.error('Could not fetch watch status');
			} finally {
				this.loading = false;
			}
		},
		async restart() {
			this.restarting = true;
			try {
				await call(
					'press.press.doctype.bench.bench_dev_watch.restart_watch',
					{ bench_name: this.benchName }
				);
				await this.refresh();
				if (this.status?.running) toast.success('Watch started');
				else toast.error('Watch failed to start — check container is running');
			} catch (e) {
				toast.error('Could not start watch: ' + (e?.message || e));
			} finally {
				this.restarting = false;
			}
		},
	},
};
</script>
