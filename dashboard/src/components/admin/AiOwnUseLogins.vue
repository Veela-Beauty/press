<template>
	<div class="space-y-4">
		<div class="flex items-center justify-between">
			<div>
				<h2 class="text-lg font-semibold">Own-use AI Logins</h2>
				<p class="text-xs text-gray-500">
					Your personal Claude Max / ChatGPT accounts for running our own agents. Link several and assign each to a
					team. <b>Not</b> gateway providers — never pooled or billed.
				</p>
			</div>
			<div class="flex gap-2">
				<Button size="sm" variant="subtle" @click="openClaude">Add Claude</Button>
				<Button size="sm" variant="solid" @click="openCodex">Add ChatGPT</Button>
			</div>
		</div>

		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<table class="w-full text-xs">
				<thead>
					<tr class="border-b border-gray-100 text-left text-gray-500">
						<th class="py-2">Provider</th><th>Label</th><th>Assigned team</th><th>Account</th><th>Status</th><th></th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="a in accounts" :key="a.name" class="border-b border-gray-50">
						<td class="py-2">{{ a.provider }}</td>
						<td class="font-medium text-gray-800">{{ a.label }}</td>
						<td>
							<input
								v-model="a.team"
								class="w-32 rounded border border-gray-200 px-2 py-1 text-xs focus:border-blue-400 focus:outline-none"
								placeholder="unassigned"
								@change="assignTeam(a)"
							/>
						</td>
						<td class="font-mono text-gray-400">{{ a.account || '—' }}</td>
						<td>
							<span class="rounded-full px-2 py-0.5 text-[10px] font-medium" :class="a.status === 'linked' ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'">{{ a.status }}</span>
						</td>
						<td class="text-right"><Button size="sm" variant="subtle" theme="red" @click="unlink(a)">Unlink</Button></td>
					</tr>
					<tr v-if="loading"><td colspan="6" class="py-6 text-center text-gray-400">Loading…</td></tr>
					<tr v-if="!loading && accounts.length === 0"><td colspan="6" class="py-6 text-center text-gray-400">No accounts linked yet. Add a Claude or ChatGPT account.</td></tr>
				</tbody>
			</table>
		</div>

		<!-- Add Claude -->
		<Dialog :options="{ title: 'Add Claude account', size: 'md' }" v-model="showClaude">
			<template #body-content>
				<div class="space-y-3">
					<FormControl label="Label" v-model="claudeForm.label" placeholder="e.g. Claude Max #1" />
					<FormControl label="Assign to team" v-model="claudeForm.team" placeholder="team name (optional)" />
					<FormControl type="password" label="Claude OAuth token" v-model="claudeForm.token" placeholder="run `claude setup-token`, paste here" />
					<p class="text-xs text-gray-400">Stored encrypted; used as CLAUDE_CODE_OAUTH_TOKEN when running our agents.</p>
				</div>
			</template>
			<template #actions><Button variant="solid" :loading="busy.claude" @click="addClaude">Link Claude</Button></template>
		</Dialog>

		<!-- Add ChatGPT -->
		<Dialog :options="{ title: 'Add ChatGPT account', size: 'md' }" v-model="showCodex">
			<template #body-content>
				<div class="space-y-3">
					<FormControl label="Label" v-model="codexForm.label" placeholder="e.g. ChatGPT #1" :disabled="!!codex" />
					<FormControl label="Assign to team" v-model="codexForm.team" placeholder="team name (optional)" :disabled="!!codex" />

					<div v-if="codex" class="rounded-md border border-blue-200 bg-blue-50 p-3">
						<p class="text-xs text-gray-600">1. Open <a :href="codex.verification_uri" target="_blank" class="font-medium text-blue-600 underline">{{ codex.verification_uri }}</a></p>
						<p class="mt-1 text-xs text-gray-600">2. Enter this code:</p>
						<div class="mt-1 font-mono text-2xl font-bold tracking-widest text-gray-900">{{ codex.user_code }}</div>
						<p class="mt-2 text-xs" :class="codex.error ? 'text-red-600' : 'text-gray-500'">{{ codex.note }}</p>
					</div>

					<details v-if="!codex" class="text-xs text-gray-500">
						<summary class="cursor-pointer">Device login not available? Paste auth.json instead</summary>
						<div class="mt-2 space-y-2">
							<FormControl type="textarea" v-model="codexAuthJson" placeholder="paste the contents of ~/.codex/auth.json" />
							<Button size="sm" variant="subtle" :loading="busy.paste" @click="pasteCodex">Save auth.json</Button>
						</div>
					</details>
				</div>
			</template>
			<template #actions>
				<Button v-if="!codex" variant="solid" :loading="busy.codex" @click="startCodex">Start device login</Button>
				<Button v-else variant="subtle" @click="cancelCodex">Cancel</Button>
			</template>
		</Dialog>
	</div>
</template>

<script>
import { Button, Dialog, FormControl, call } from 'frappe-ui';
import { toast } from 'vue-sonner';

export default {
	name: 'AiOwnUseLogins',
	components: { Button, Dialog, FormControl },
	data() {
		return {
			accounts: [],
			loading: false,
			showClaude: false,
			showCodex: false,
			claudeForm: { label: '', team: '', token: '' },
			codexForm: { label: '', team: '' },
			codexAuthJson: '',
			codex: null, // device flow state
			busy: { claude: false, codex: false, paste: false },
			_timer: null,
		};
	},
	mounted() { this.load(); },
	beforeUnmount() { this.stopPoll(); },
	methods: {
		async load() {
			this.loading = true;
			try { this.accounts = await call('sanad_ai_control_center.own_use.list_accounts'); }
			catch (e) { /* control-center unreachable */ }
			this.loading = false;
		},
		openClaude() { this.claudeForm = { label: '', team: '', token: '' }; this.showClaude = true; },
		async addClaude() {
			if (!this.claudeForm.token.trim()) { toast.error('Paste your Claude token'); return; }
			this.busy.claude = true;
			try {
				await call('sanad_ai_control_center.own_use.link_claude', { ...this.claudeForm });
				toast.success('Claude account linked');
				this.showClaude = false;
				this.load();
			} catch (e) { toast.error(e.messages?.[0] || 'Could not link Claude'); }
			this.busy.claude = false;
		},
		openCodex() { this.codexForm = { label: '', team: '' }; this.codex = null; this.codexAuthJson = ''; this.showCodex = true; },
		async startCodex() {
			this.busy.codex = true;
			try {
				const r = await call('sanad_ai_control_center.own_use.codex_device_start', { ...this.codexForm });
				this.codex = { ...r, note: 'Waiting for you to approve in the browser…', error: false };
				this.schedulePoll((r.interval || 5) * 1000);
			} catch (e) { toast.error(e.messages?.[0] || 'Could not start ChatGPT login'); }
			this.busy.codex = false;
		},
		schedulePoll(ms) { this.stopPoll(); this._timer = setTimeout(() => this.poll(), ms); },
		stopPoll() { if (this._timer) { clearTimeout(this._timer); this._timer = null; } },
		async poll() {
			if (!this.codex) return;
			let r;
			try { r = await call('sanad_ai_control_center.own_use.codex_device_poll', { handle: this.codex.handle }); }
			catch (e) { this.schedulePoll(5000); return; }
			if (r.status === 'success') {
				this.stopPoll();
				this.codex = null;
				this.showCodex = false;
				toast.success('ChatGPT account linked');
				this.load();
			} else if (r.status === 'pending') {
				this.schedulePoll((r.interval || this.codex.interval || 5) * 1000);
			} else {
				this.codex.error = true;
				this.codex.note = r.error === 'expired' ? 'Code expired — cancel and start again.' : ('Login failed: ' + (r.error || 'unknown'));
				this.stopPoll();
			}
		},
		cancelCodex() { this.stopPoll(); this.codex = null; },
		async pasteCodex() {
			if (!this.codexAuthJson.trim()) { toast.error('Paste your auth.json'); return; }
			this.busy.paste = true;
			try {
				await call('sanad_ai_control_center.own_use.paste_codex_authjson', { ...this.codexForm, auth_json: this.codexAuthJson });
				toast.success('ChatGPT account linked');
				this.showCodex = false;
				this.load();
			} catch (e) { toast.error(e.messages?.[0] || 'Could not save auth.json'); }
			this.busy.paste = false;
		},
		async assignTeam(a) {
			try { await call('sanad_ai_control_center.own_use.assign_team', { account: a.name, team: a.team || '' }); toast.success('Team updated'); }
			catch (e) { toast.error(e.messages?.[0] || 'Could not update team'); }
		},
		async unlink(a) {
			try { await call('sanad_ai_control_center.own_use.delete_account', { account: a.name }); toast.success('Unlinked'); this.load(); }
			catch (e) { toast.error(e.messages?.[0] || 'Could not unlink'); }
		},
	},
};
</script>
