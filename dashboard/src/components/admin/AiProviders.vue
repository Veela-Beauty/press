<template>
	<div class="space-y-4">
		<div class="flex items-center justify-between">
			<div>
				<h2 class="text-lg font-semibold">Providers</h2>
				<p class="text-xs text-gray-500">
					Add any AI account here. API-key providers join the billed gateway pool; Claude Code / ChatGPT are
					own-use logins (your subscription, per-team, never pooled or billed).
				</p>
			</div>
			<Button variant="solid" @click="openAdd()">Add account</Button>
		</div>

		<!-- Gateway pool -->
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<h3 class="mb-3 text-sm font-semibold">Gateway pool <span class="font-normal text-gray-400">(api-key, billed, load-balanced)</span></h3>
			<table class="w-full text-xs">
				<thead>
					<tr class="border-b border-gray-100 text-left text-gray-500"><th class="py-2">Provider</th><th>Serves as</th><th>Region</th><th>Cost MTD</th><th></th></tr>
				</thead>
				<tbody>
					<tr v-for="(p, i) in providers" :key="i" class="border-b border-gray-50">
						<td class="py-2 text-gray-800">{{ p.provider }}</td>
						<td class="font-mono text-gray-500">{{ p.tier }}</td>
						<td>{{ p.region || '—' }}</td>
						<td><span v-if="p.connected" class="font-mono">${{ fmt(p.cost) }}</span><span v-else class="text-gray-400">not connected</span></td>
						<td class="text-right"><Button v-if="!p.connected" size="sm" variant="outline" @click="openAdd(p.tier)">Connect</Button></td>
					</tr>
					<tr v-if="loading"><td colspan="5" class="py-6 text-center text-gray-400">Loading…</td></tr>
					<tr v-if="!loading && providers.length === 0"><td colspan="5" class="py-6 text-center text-gray-400">No gateway providers yet.</td></tr>
				</tbody>
			</table>
		</div>

		<!-- Own-use -->
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<h3 class="mb-3 text-sm font-semibold">Own-use accounts <span class="font-normal text-gray-400">(Claude / ChatGPT subscriptions, per-team)</span></h3>
			<table class="w-full text-xs">
				<thead>
					<tr class="border-b border-gray-100 text-left text-gray-500"><th class="py-2">Provider</th><th>Label</th><th>Assigned team</th><th>Status</th><th></th></tr>
				</thead>
				<tbody>
					<tr v-for="a in ownUse" :key="a.name" class="border-b border-gray-50">
						<td class="py-2">{{ a.provider }}</td>
						<td class="font-medium text-gray-800">{{ a.label }}</td>
						<td><input v-model="a.team" class="w-32 rounded border border-gray-200 px-2 py-1 text-xs focus:border-blue-400 focus:outline-none" placeholder="unassigned" @change="assignTeam(a)" /></td>
						<td><span class="rounded-full px-2 py-0.5 text-[10px] font-medium" :class="a.status === 'linked' ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'">{{ a.status }}</span></td>
						<td class="text-right"><Button size="sm" variant="subtle" theme="red" @click="unlinkOwnUse(a)">Unlink</Button></td>
					</tr>
					<tr v-if="!loading && ownUse.length === 0"><td colspan="5" class="py-6 text-center text-gray-400">No own-use accounts linked.</td></tr>
				</tbody>
			</table>
		</div>

		<!-- Unified Add-account dialog -->
		<Dialog :options="{ title: 'Add account', size: 'md' }" v-model="show">
			<template #body-content>
				<div class="space-y-3">
					<FormControl type="select" label="Provider" v-model="f.provider" :options="providerOptions" :disabled="!!codex" @change="onProvider" />

					<!-- api_key (gateway pool) -->
					<template v-if="authClass === 'api_key'">
						<FormControl type="password" label="API key" v-model="f.token" placeholder="paste the provider API key" />
						<FormControl label="Account label" v-model="f.label" placeholder="e.g. Z.AI #2" />
						<FormControl label="Serve as model" v-model="f.serve_as_model" placeholder="glm-4.5-air" />
						<div class="grid grid-cols-2 gap-3">
							<FormControl type="number" label="Weight" v-model="f.weight" placeholder="1" />
							<FormControl type="number" label="Monthly budget (USD)" v-model="f.monthly_budget" placeholder="optional" />
						</div>
						<p class="text-xs text-gray-400">Two accounts with the same “Serve as model” load-balance by weight.</p>
					</template>

					<!-- Claude (own-use) -->
					<template v-else-if="authClass === 'personal_only'">
						<FormControl label="Label" v-model="f.label" placeholder="e.g. Claude Max #1" />
						<FormControl label="Assign to team" v-model="f.team" placeholder="team name (optional)" />
						<FormControl type="password" label="Claude OAuth token" v-model="f.token" placeholder="run `claude setup-token`, paste here" />
						<p class="text-xs text-gray-400">Own-use: your Claude Max subscription. Stored encrypted; never pooled or billed.</p>
					</template>

					<!-- ChatGPT (own-use) -->
					<template v-else-if="authClass === 'chatgpt_oauth'">
						<FormControl label="Label" v-model="f.label" placeholder="e.g. ChatGPT #1" :disabled="!!codex" />
						<FormControl label="Assign to team" v-model="f.team" placeholder="team name (optional)" :disabled="!!codex" />
						<div v-if="codex" class="rounded-md border border-blue-200 bg-blue-50 p-3">
							<p class="text-xs text-gray-600">1. Open <a :href="codex.verification_uri" target="_blank" class="font-medium text-blue-600 underline">{{ codex.verification_uri }}</a></p>
							<p class="mt-1 text-xs text-gray-600">2. Enter this code:</p>
							<div class="mt-1 font-mono text-2xl font-bold tracking-widest text-gray-900">{{ codex.user_code }}</div>
							<p class="mt-2 text-xs" :class="codex.error ? 'text-red-600' : 'text-gray-500'">{{ codex.note }}</p>
						</div>
						<details v-if="!codex" class="text-xs text-gray-500">
							<summary class="cursor-pointer">Device login not available? Paste auth.json</summary>
							<div class="mt-2 space-y-2">
								<FormControl type="textarea" v-model="f.codexAuthJson" placeholder="paste ~/.codex/auth.json" />
								<Button size="sm" variant="subtle" :loading="busy.paste" @click="pasteCodex">Save auth.json</Button>
							</div>
						</details>
						<p v-if="!codex" class="text-xs text-gray-400">Own-use: your ChatGPT subscription. Best-effort device login; paste-auth.json always works.</p>
					</template>
				</div>
			</template>
			<template #actions>
				<Button v-if="authClass === 'api_key'" variant="solid" :loading="busy.connect" @click="submitGateway">Test &amp; connect</Button>
				<Button v-else-if="authClass === 'personal_only'" variant="solid" :loading="busy.claude" @click="submitClaude">Link Claude</Button>
				<Button v-else-if="authClass === 'chatgpt_oauth' && !codex" variant="solid" :loading="busy.codex" @click="startCodex">Start device login</Button>
				<Button v-else-if="codex" variant="subtle" @click="cancelCodex">Cancel</Button>
			</template>
		</Dialog>
	</div>
</template>

<script>
import { Button, Dialog, FormControl, call } from 'frappe-ui';
import { toast } from 'vue-sonner';

const EMPTY = () => ({ provider: '', label: '', team: '', token: '', serve_as_model: '', weight: 1, monthly_budget: null, codexAuthJson: '' });

export default {
	name: 'AiProviders',
	components: { Button, Dialog, FormControl },
	data() {
		return {
			providers: [], ownUse: [], catalog: [], loading: false, show: false,
			f: EMPTY(), codex: null, _timer: null,
			busy: { connect: false, claude: false, codex: false, paste: false },
		};
	},
	computed: {
		providerOptions() {
			// Full catalog — api_key first, then own-use; the form branches by auth_class.
			return (this.catalog || []).map((r) => ({ label: r.label || r.provider_key, value: r.provider_key }));
		},
		authClass() {
			const row = (this.catalog || []).find((r) => r.provider_key === this.f.provider);
			return row ? row.auth_class : '';
		},
	},
	mounted() { this.load(); },
	beforeUnmount() { this.stopPoll(); },
	methods: {
		async load() {
			this.loading = true;
			try { this.providers = this.mapProviders(await call('sanad_ai_control_center.api.get_accounts_overview')); } catch (e) {}
			try { this.ownUse = await call('sanad_ai_control_center.own_use.list_accounts'); } catch (e) {}
			this.loading = false;
		},
		async openAdd(prefillModel) {
			this.f = EMPTY();
			this.f.serve_as_model = prefillModel || '';
			this.codex = null;
			if (!this.catalog.length) {
				try { this.catalog = await call('sanad_ai_control_center.gateway.catalog.get_provider_catalog'); }
				catch (e) { toast.error('Could not load the provider catalog'); return; }
			}
			if (!this.f.provider && this.providerOptions.length) this.f.provider = this.providerOptions[0].value;
			this.show = true;
		},
		onProvider() { this.cancelCodex(); },
		async submitGateway() {
			const f = this.f;
			if (!f.provider || !f.token || !f.serve_as_model) { toast.error('Provider, API key, and Serve-as-model are required'); return; }
			this.busy.connect = true;
			try {
				await call('sanad_ai_control_center.api.connect_account', {
					provider: f.provider, token: f.token, account_label: f.label || f.provider,
					serve_as_model: f.serve_as_model, weight: f.weight || 1, monthly_budget: f.monthly_budget || null,
				});
				toast.success('Provider connected to the gateway pool');
				this.show = false; this.load();
			} catch (e) { toast.error(e.messages?.[0] || 'Could not connect the provider'); }
			this.busy.connect = false;
		},
		async submitClaude() {
			if (!this.f.token.trim()) { toast.error('Paste your Claude token'); return; }
			this.busy.claude = true;
			try {
				await call('sanad_ai_control_center.own_use.link_claude', { label: this.f.label, team: this.f.team, token: this.f.token });
				toast.success('Claude account linked'); this.show = false; this.load();
			} catch (e) { toast.error(e.messages?.[0] || 'Could not link Claude'); }
			this.busy.claude = false;
		},
		async startCodex() {
			this.busy.codex = true;
			try {
				const r = await call('sanad_ai_control_center.own_use.codex_device_start', { label: this.f.label, team: this.f.team });
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
			if (r.status === 'success') { this.stopPoll(); this.codex = null; this.show = false; toast.success('ChatGPT account linked'); this.load(); }
			else if (r.status === 'pending') { this.schedulePoll((r.interval || this.codex.interval || 5) * 1000); }
			else { this.codex.error = true; this.codex.note = r.error === 'expired' ? 'Code expired — cancel and start again.' : ('Login failed: ' + (r.error || 'unknown')); this.stopPoll(); }
		},
		cancelCodex() { this.stopPoll(); this.codex = null; },
		async pasteCodex() {
			if (!this.f.codexAuthJson.trim()) { toast.error('Paste your auth.json'); return; }
			this.busy.paste = true;
			try {
				await call('sanad_ai_control_center.own_use.paste_codex_authjson', { label: this.f.label, team: this.f.team, auth_json: this.f.codexAuthJson });
				toast.success('ChatGPT account linked'); this.show = false; this.load();
			} catch (e) { toast.error(e.messages?.[0] || 'Could not save auth.json'); }
			this.busy.paste = false;
		},
		async assignTeam(a) {
			try { await call('sanad_ai_control_center.own_use.assign_team', { account: a.name, team: a.team || '' }); toast.success('Team updated'); }
			catch (e) { toast.error(e.messages?.[0] || 'Could not update team'); }
		},
		async unlinkOwnUse(a) {
			try { await call('sanad_ai_control_center.own_use.delete_account', { account: a.name }); toast.success('Unlinked'); this.load(); }
			catch (e) { toast.error(e.messages?.[0] || 'Could not unlink'); }
		},
		mapProviders(data) {
			const groups = (data && data.groups) || [];
			const rows = [];
			groups.forEach((grp) => {
				const accounts = grp.accounts || [];
				if (accounts.length === 0) { rows.push({ provider: grp.model || '—', tier: grp.tier || grp.model || '—', region: grp.region || '—', cost: grp.cost || 0, connected: false }); return; }
				accounts.forEach((acc) => rows.push({
					provider: acc.account_label || acc.provider || grp.model || '—',
					tier: acc.serve_as_model || acc.tier || grp.tier || grp.model || '—',
					region: acc.region || '—',
					cost: acc.spend_to_date != null ? acc.spend_to_date : acc.cost != null ? acc.cost : 0,
					connected: acc.connected != null ? acc.connected : true,
				}));
			});
			return rows;
		},
		fmt(n) { const v = Number(n); return v ? v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'; },
	},
};
</script>
