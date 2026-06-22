<template>
	<div class="space-y-4">
		<div>
			<h2 class="text-lg font-semibold">Own-use AI Logins</h2>
			<p class="text-xs text-gray-500">
				Your personal Claude Max / ChatGPT subscriptions, used to run our own agents under our own login.
				These are <b>not</b> gateway providers — never pooled, never billed to a client.
			</p>
		</div>

		<!-- Claude Code -->
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-sm font-semibold">Claude Code (Claude Max)</h3>
				<span class="rounded-full px-2 py-0.5 text-[10px] font-medium" :class="status.claude_linked ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'">
					{{ status.claude_linked ? 'Linked' : 'Not linked' }}
				</span>
			</div>
			<div v-if="!status.claude_linked" class="space-y-2">
				<p class="text-xs text-gray-500">Run <code class="rounded bg-gray-100 px-1">claude setup-token</code> in your terminal, then paste the token here.</p>
				<FormControl type="password" v-model="claudeToken" placeholder="paste the Claude OAuth token" />
				<Button variant="solid" size="sm" :loading="busy.claude" @click="linkClaude">Link Claude</Button>
			</div>
			<div v-else class="flex items-center gap-3">
				<span class="text-xs text-gray-500">Linked and ready for agent runs.</span>
				<Button size="sm" variant="subtle" theme="red" @click="unlink('claude')">Unlink</Button>
			</div>
		</div>

		<!-- ChatGPT / Codex -->
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-sm font-semibold">ChatGPT / Codex</h3>
				<span class="rounded-full px-2 py-0.5 text-[10px] font-medium" :class="status.codex_linked ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'">
					{{ status.codex_linked ? 'Linked' : 'Not linked' }}
				</span>
			</div>

			<div v-if="status.codex_linked" class="flex items-center gap-3">
				<span class="text-xs text-gray-500">Linked{{ status.codex_account ? ' · ' + status.codex_account : '' }}.</span>
				<Button size="sm" variant="subtle" theme="red" @click="unlink('codex')">Unlink</Button>
			</div>

			<div v-else-if="codex" class="space-y-3">
				<div class="rounded-md border border-blue-200 bg-blue-50 p-3">
					<p class="text-xs text-gray-600">1. Open <a :href="codex.verification_uri" target="_blank" class="font-medium text-blue-600 underline">{{ codex.verification_uri }}</a></p>
					<p class="mt-1 text-xs text-gray-600">2. Enter this code:</p>
					<div class="mt-1 font-mono text-2xl font-bold tracking-widest text-gray-900">{{ codex.user_code }}</div>
					<p class="mt-2 text-xs" :class="codex.error ? 'text-red-600' : 'text-gray-500'">{{ codex.note }}</p>
				</div>
				<Button size="sm" variant="subtle" @click="cancelCodex">Cancel</Button>
			</div>

			<div v-else class="space-y-2">
				<Button variant="solid" size="sm" :loading="busy.codex" @click="startCodex">Start device login</Button>
				<details class="text-xs text-gray-500">
					<summary class="cursor-pointer">Device login not available? Paste auth.json instead</summary>
					<div class="mt-2 space-y-2">
						<FormControl type="textarea" v-model="codexAuthJson" placeholder="paste the contents of ~/.codex/auth.json" />
						<Button size="sm" variant="subtle" :loading="busy.paste" @click="pasteCodex">Save auth.json</Button>
					</div>
				</details>
			</div>
		</div>
	</div>
</template>

<script>
import { Button, FormControl, call } from 'frappe-ui';
import { toast } from 'vue-sonner';

export default {
	name: 'AiOwnUseLogins',
	components: { Button, FormControl },
	data() {
		return {
			status: { claude_linked: false, codex_linked: false, codex_account: '' },
			claudeToken: '',
			codexAuthJson: '',
			codex: null, // { handle, user_code, verification_uri, interval, note, error }
			busy: { claude: false, codex: false, paste: false },
			_timer: null,
		};
	},
	mounted() { this.load(); },
	beforeUnmount() { this.stopPoll(); },
	methods: {
		async load() {
			try { this.status = await call('sanad_ai_control_center.own_use.get_status'); }
			catch (e) { /* control-center unreachable */ }
		},
		async linkClaude() {
			if (!this.claudeToken.trim()) { toast.error('Paste your Claude token'); return; }
			this.busy.claude = true;
			try {
				await call('sanad_ai_control_center.own_use.link_claude', { token: this.claudeToken });
				toast.success('Claude linked');
				this.claudeToken = '';
				this.load();
			} catch (e) { toast.error(e.messages?.[0] || 'Could not link Claude'); }
			this.busy.claude = false;
		},
		async unlink(provider) {
			try { await call('sanad_ai_control_center.own_use.unlink', { provider }); toast.success('Unlinked'); this.load(); }
			catch (e) { toast.error(e.messages?.[0] || 'Could not unlink'); }
		},
		async startCodex() {
			this.busy.codex = true;
			try {
				const r = await call('sanad_ai_control_center.own_use.codex_device_start');
				this.codex = { ...r, note: 'Waiting for you to approve in the browser…', error: false };
				this.schedulePoll((r.interval || 5) * 1000);
			} catch (e) { toast.error(e.messages?.[0] || 'Could not start ChatGPT login'); }
			this.busy.codex = false;
		},
		schedulePoll(ms) {
			this.stopPoll();
			this._timer = setTimeout(() => this.poll(), ms);
		},
		stopPoll() { if (this._timer) { clearTimeout(this._timer); this._timer = null; } },
		async poll() {
			if (!this.codex) return;
			let r;
			try { r = await call('sanad_ai_control_center.own_use.codex_device_poll', { handle: this.codex.handle }); }
			catch (e) { this.schedulePoll(5000); return; }
			if (r.status === 'success') {
				this.stopPoll();
				this.codex = null;
				toast.success('ChatGPT linked');
				this.load();
			} else if (r.status === 'pending') {
				this.schedulePoll((r.interval || this.codex.interval || 5) * 1000);
			} else {
				this.codex.error = true;
				this.codex.note = r.error === 'expired' ? 'Code expired — start again.' : ('Login failed: ' + (r.error || 'unknown'));
				this.stopPoll();
			}
		},
		cancelCodex() { this.stopPoll(); this.codex = null; },
		async pasteCodex() {
			if (!this.codexAuthJson.trim()) { toast.error('Paste your auth.json'); return; }
			this.busy.paste = true;
			try {
				await call('sanad_ai_control_center.own_use.paste_codex_authjson', { auth_json: this.codexAuthJson });
				toast.success('ChatGPT linked');
				this.codexAuthJson = '';
				this.load();
			} catch (e) { toast.error(e.messages?.[0] || 'Could not save auth.json'); }
			this.busy.paste = false;
		},
	},
};
</script>
