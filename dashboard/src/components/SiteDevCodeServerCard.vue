<template>
	<a v-if="state === 'running'" :href="codeServer.url" target="_blank"
		class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm font-medium text-green-700 shadow-sm transition-colors hover:border-green-400">
		<svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
			<path d="M16.5 3L21 7.5 9 19.5 3 15l13.5-12z"/><path d="M12 7.5L16.5 12"/><path d="M3 15l4.5-4.5"/>
		</svg>
		<span>
			<span class="block text-sm font-semibold">Open Code Server</span>
			<span class="block text-xs text-green-500">{{ codeServer.name }} · Running</span>
		</span>
		<svg class="ml-auto h-3.5 w-3.5 text-green-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
			<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
		</svg>
	</a>
	<button v-else-if="state === 'launch'" @click="launch"
		:disabled="launching"
		class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700 shadow-sm transition-colors hover:border-blue-400 disabled:opacity-50">
		<svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
			<path d="M16.5 3L21 7.5 9 19.5 3 15l13.5-12z"/><path d="M12 7.5L16.5 12"/><path d="M3 15l4.5-4.5"/>
		</svg>
		<span>
			<span class="block text-sm font-semibold">{{ launching ? 'Setting up…' : 'Launch Code Server' }}</span>
			<span class="block text-xs text-blue-400">Per-user web VS Code for this bench</span>
		</span>
	</button>
	<div v-else-if="state === 'starting'"
		class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm font-medium text-yellow-700">
		<svg class="h-5 w-5 flex-shrink-0 animate-spin" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
			<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>
		</svg>
		<span>
			<span class="block text-sm font-semibold">Code Server Starting…</span>
			<span class="block text-xs text-yellow-500">{{ codeServer.name }}</span>
		</span>
	</div>
	<div v-else-if="state === 'failed' || state === 'stopped'"
		class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
		<svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
			<path d="M16.5 3L21 7.5 9 19.5 3 15l13.5-12z"/><path d="M12 7.5L16.5 12"/><path d="M3 15l4.5-4.5"/>
		</svg>
		<span>
			<span class="block text-sm font-semibold">{{ state === 'stopped' ? 'Code Server stopped' : 'Code Server failed' }}</span>
			<span class="block text-xs text-red-500">{{ codeServer.name }}</span>
		</span>
		<Button class="ml-auto" size="sm" :loading="restarting" @click="restart">Restart Code Server</Button>
	</div>
</template>

<script>
import { call } from 'frappe-ui';
import { toast } from 'vue-sonner';
import { cardState, shouldPoll, POLL_MS } from './code-server-derive';

const API = 'press.press.doctype.bench.bench_dev_overview';

export default {
	name: 'SiteDevCodeServerCard',
	props: { bench: { type: String, default: '' } },
	data() {
		return {
			codeServer: { enabled: false, exists: false, status: null, url: null, name: null },
			launching: false,
			restarting: false,
			pollTimer: null,
			polls: 0,
		};
	},
	computed: {
		state() { return cardState(this.codeServer); },
	},
	watch: {
		bench: { immediate: true, handler(b) { if (b) this.refresh(); } },
	},
	beforeUnmount() {
		clearTimeout(this.pollTimer);
	},
	methods: {
		async load() {
			clearTimeout(this.pollTimer);
			try {
				const res = await call(`${API}.get_code_server_status`, { bench_name: this.bench });
				this.codeServer = res || this.codeServer;
			} catch (e) { /* keep the last known state */ }
			// Keep checking while the agent job runs, so "Starting…" turns into Running or failed by itself.
			if (shouldPoll(this.codeServer, this.polls)) {
				this.polls += 1;
				this.pollTimer = setTimeout(() => this.load(), POLL_MS);
			}
		},
		refresh() {
			this.polls = 0;
			this.load();
		},
		async launch() {
			this.launching = true;
			const subdomain = `code-${this.bench.replace(/[^a-z0-9]/g, '-').slice(0, 30)}`;
			try {
				const res = await call(`${API}.setup_code_server`, { bench_name: this.bench, subdomain });
				if (res?.error) { toast.error(res.error); }
				else { toast.success('Code Server setup started'); this.refresh(); }
			} catch (e) { toast.error(e?.messages?.join(', ') || 'Failed to setup Code Server'); }
			finally { this.launching = false; }
		},
		async restart() {
			this.restarting = true;
			try {
				const res = await call(`${API}.restart_code_server`, { bench_name: this.bench });
				if (res?.error) { toast.error(res.error); }
				else { toast.success('Code Server restarting'); this.refresh(); }
			} catch (e) { toast.error(e?.messages?.join(', ') || 'Failed to restart Code Server'); }
			finally { this.restarting = false; }
		},
	},
};
</script>
