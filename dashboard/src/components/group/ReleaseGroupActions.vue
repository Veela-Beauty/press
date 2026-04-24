<template>
	<div class="mx-auto max-w-3xl space-y-4">
		<!-- Dev Actions — benches in this release group -->
		<div
			v-if="benches.data?.length"
			class="divide-y rounded border border-gray-200 p-5"
		>
			<div class="pb-3 text-lg font-semibold">Dev Actions</div>
			<div
				class="py-3 first:pt-0 last:pb-0"
				v-for="bench in benches.data"
				:key="bench.name"
			>
				<div class="flex items-center justify-between gap-1">
					<div>
						<h3 class="text-base font-medium">{{ bench.name }}</h3>
						<p class="mt-1 text-p-base text-gray-600">
							{{
								bench.is_development_bench
									? 'This bench is marked as a development bench'
									: 'Mark this bench for development use only'
							}}
						</p>
					</div>
					<div class="flex items-center gap-2">
						<div
							v-if="codeServerStatus[bench.name]?.can_use && codeServerStatus[bench.name]?.status === 'Running' && codeServerStatus[bench.name]?.url"
							class="flex flex-col items-end gap-1"
						>
							<a
								:href="codeServerStatus[bench.name].url"
								target="_blank"
								class="inline-flex items-center gap-1 rounded border border-green-300 bg-green-50 px-3 py-1.5 text-sm font-medium text-green-700 hover:bg-green-100 whitespace-nowrap"
							>✓ Open Code Server ↗</a>
							<button
								v-if="codeServerStatus[bench.name]?.password"
								@click="copyCodeServerPassword(bench)"
								class="text-xs text-gray-500 hover:text-gray-900 font-mono whitespace-nowrap"
								title="Click to copy password"
							>{{ revealedPasswords[bench.name] ? codeServerStatus[bench.name].password : '••••••••••  copy password' }}</button>
							<div
								v-if="codeServerStatus[bench.name]?.password_expires_at"
								class="flex items-center gap-2 text-xs whitespace-nowrap"
							>
								<span :class="codeServerStatus[bench.name]?.password_is_expired ? 'text-red-600 font-medium' : 'text-gray-500'">
									⏲ {{ formatExpiry(codeServerStatus[bench.name].password_expires_at) }}
								</span>
								<button
									:disabled="rotateLoading[bench.name]"
									@click="rotateCodeServerPassword(bench)"
									class="text-blue-600 hover:text-blue-800 underline"
								>{{ rotateLoading[bench.name] ? 'Rotating…' : 'Rotate Now' }}</button>
								<span class="text-gray-300">|</span>
								<button
									:disabled="restartLoading[bench.name]"
									@click="restartCodeServer(bench)"
									class="text-blue-600 hover:text-blue-800 underline"
								>{{ restartLoading[bench.name] ? 'Restarting…' : 'Restart' }}</button>
							</div>
							<div class="flex items-center gap-1 text-xs text-gray-400">
								<span>auto-rotate every</span>
								<input
									type="number"
									min="0"
									class="w-12 rounded border border-gray-200 px-1 py-0 text-right focus:border-blue-500 focus:outline-none"
									v-model.number="durationEdits[bench.name]"
									@blur="saveDuration(bench)"
									@keyup.enter="saveDuration(bench)"
								/>
								<span>days</span>
							</div>
						</div>
						<div
							v-else-if="codeServerStatus[bench.name]?.can_use && codeServerStatus[bench.name]?.exists && codeServerStatus[bench.name]?.status !== 'Running'"
							class="flex flex-col items-end gap-1"
						>
							<span class="text-sm text-gray-500 italic whitespace-nowrap">Code Server {{ codeServerStatus[bench.name].status === 'Pending' ? 'starting…' : codeServerStatus[bench.name].status }}</span>
							<button
								:disabled="restartLoading[bench.name]"
								@click="restartCodeServer(bench)"
								class="text-xs text-blue-600 hover:text-blue-800 underline"
							>{{ restartLoading[bench.name] ? 'Restarting…' : 'Restart Code Server' }}</button>
						</div>
						<Button
							v-else-if="codeServerStatus[bench.name]?.can_use"
							class="whitespace-nowrap"
							:loading="codeServerLoading[bench.name]"
							@click="launchCodeServer(bench)"
						>Launch Code Server</Button>
						<Button
							class="whitespace-nowrap"
							:loading="devLoading[bench.name]"
							@click="toggleDevBench(bench)"
						>
							<p>{{ bench.is_development_bench ? 'Unset Dev Bench' : 'Mark Dev Bench' }}</p>
						</Button>
					</div>
				</div>

				<!-- Bench Quick Actions (matches SiteDevTab styling) -->
				<div class="mt-4 flex flex-wrap gap-3">
					<!-- Code Server: Open (Running) / Launch (none) / Starting (Pending) -->
					<a v-if="codeServerStatus[bench.name]?.can_use && codeServerStatus[bench.name]?.status === 'Running' && codeServerStatus[bench.name]?.url"
						:href="codeServerStatus[bench.name].url" target="_blank"
						class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm font-medium text-green-700 shadow-sm transition-colors hover:border-green-400">
						<svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
							<path d="M16.5 3L21 7.5 9 19.5 3 15l13.5-12z"/><path d="M12 7.5L16.5 12"/><path d="M3 15l4.5-4.5"/>
						</svg>
						<span>
							<span class="block text-sm font-semibold">Open Code Server</span>
							<span class="block text-xs text-green-500">{{ codeServerStatus[bench.name].name }} · Running</span>
						</span>
						<svg class="ml-auto h-3.5 w-3.5 text-green-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
							<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
						</svg>
					</a>
					<button v-else-if="codeServerStatus[bench.name]?.can_use && !codeServerStatus[bench.name]?.exists && codeServerStatus[bench.name]?.status !== 'Pending'"
						@click="launchCodeServer(bench)" :disabled="codeServerLoading[bench.name]"
						class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700 shadow-sm transition-colors hover:border-blue-400 disabled:opacity-50">
						<svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
							<path d="M16.5 3L21 7.5 9 19.5 3 15l13.5-12z"/><path d="M12 7.5L16.5 12"/><path d="M3 15l4.5-4.5"/>
						</svg>
						<span>
							<span class="block text-sm font-semibold">{{ codeServerLoading[bench.name] ? 'Setting up…' : 'Launch Code Server' }}</span>
							<span class="block text-xs text-blue-400">Per-user web VS Code for this bench</span>
						</span>
					</button>
					<div v-else-if="codeServerStatus[bench.name]?.can_use && codeServerStatus[bench.name]?.exists && codeServerStatus[bench.name]?.status === 'Pending'"
						class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm font-medium text-yellow-700">
						<svg class="h-5 w-5 flex-shrink-0 animate-spin" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
							<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>
						</svg>
						<span>
							<span class="block text-sm font-semibold">Code Server Starting…</span>
							<span class="block text-xs text-yellow-500">{{ codeServerStatus[bench.name].name }}</span>
						</span>
					</div>

					<!-- Local VS Code (SSH Remote) — 3 states: no key / no cert / valid cert -->
					<a v-if="sshCerts[bench.name]?.has_valid_cert" :href="localVscodeUrl(bench)"
						class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:border-purple-400 hover:text-purple-600">
						<svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
							<rect x="2" y="3" width="20" height="18" rx="2"/><path d="M8 10l3 3-3 3"/><line x1="14" y1="16" x2="18" y2="16"/>
						</svg>
						<span>
							<span class="block text-sm font-semibold">Local VS Code</span>
							<span class="block text-xs text-gray-400">SSH Remote → {{ devInfos[bench.name]?.server_ip }}:{{ devInfos[bench.name]?.ssh_port }}</span>
							<span class="block text-xs" :class="sshCerts[bench.name].expires_in_seconds < 1800 ? 'text-orange-600' : 'text-gray-400'">
								⏲ cert {{ formatCertExpiry(sshCerts[bench.name].expires_in_seconds) }}
								<button v-if="sshCerts[bench.name].expires_in_seconds < 1800"
									@click.prevent="generateCert(bench)" :disabled="certGenLoading[bench.name]"
									class="ml-2 text-orange-700 underline">Renew</button>
							</span>
						</span>
					</a>
					<button v-else-if="sshCerts[bench.name]?.has_ssh_key && !sshCerts[bench.name]?.has_valid_cert"
						@click="generateCert(bench)" :disabled="certGenLoading[bench.name]"
						class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-orange-200 bg-orange-50 px-4 py-3 text-sm font-medium text-orange-700 shadow-sm transition-colors hover:border-orange-400 disabled:opacity-50">
						<svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
							<path d="M12 15v2m-6 4h12a2 2 0 0 0 2-2v-6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2z"/>
							<path d="M8 11V7a4 4 0 1 1 8 0v4"/>
						</svg>
						<span>
							<span class="block text-sm font-semibold">{{ certGenLoading[bench.name] ? 'Generating…' : 'Generate SSH Certificate' }}</span>
							<span class="block text-xs text-orange-500">One-click mint + download for {{ sshCerts[bench.name]?.principal }}</span>
						</span>
					</button>
					<a v-else-if="sshCerts[bench.name] && !sshCerts[bench.name]?.has_ssh_key" href="/dashboard/settings/developer"
						class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm font-medium text-yellow-700 shadow-sm transition-colors hover:border-yellow-400">
						<svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
							<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
						</svg>
						<span>
							<span class="block text-sm font-semibold">Setup SSH Key</span>
							<span class="block text-xs text-yellow-600">Required for Local VS Code</span>
						</span>
					</a>

					<!-- Restart Bench -->
					<button @click="restartBench(bench)" :disabled="benchRestartLoading[bench.name]"
						class="flex min-w-[140px] flex-1 items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:border-orange-400 hover:text-orange-600"
						:class="{ 'cursor-not-allowed opacity-60': benchRestartLoading[bench.name] }">
						<svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
							<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>
						</svg>
						<span>
							<span class="block text-sm font-semibold">{{ benchRestartLoading[bench.name] ? 'Restarting…' : 'Restart Bench' }}</span>
							<span class="block text-xs text-gray-400">Restart all bench workers</span>
						</span>
					</button>
				</div>
			</div>
		</div>

		<!-- Standard actions from Release Group doc.actions child table -->
		<div
			v-if="$releaseGroup?.doc?.actions"
			v-for="group in actions"
			:key="group.group"
			class="divide-y rounded border border-gray-200 p-5"
		>
			<div class="pb-3 text-lg font-semibold">{{ group.group }}</div>
			<div
				class="py-3 first:pt-0 last:pb-0"
				v-for="row in group.actions"
				:key="row.action"
			>
				<ReleaseGroupActionCell
					:benchName="releaseGroup"
					:group="group.group"
					:actionLabel="row.action"
					:method="row.doc_method"
					:description="row.description"
					:buttonLabel="row.button_label"
					:linkedVersionUpgrade="$releaseGroup?.doc?.linked_version_upgrade"
				/>
			</div>
		</div>
	</div>
</template>

<script>
import { call, createListResource, getCachedDocumentResource } from 'frappe-ui';
import { toast } from 'vue-sonner';
import ReleaseGroupActionCell from './ReleaseGroupActionCell.vue';

export default {
	props: ['releaseGroup'],
	components: { ReleaseGroupActionCell },
	data() {
		return {
			devLoading: {},
			codeServerLoading: {},
			codeServerStatus: {},
			devInfos: {},
			sshCerts: {},
			certGenLoading: {},
			revealedPasswords: {},
			rotateLoading: {},
			restartLoading: {},
			benchRestartLoading: {},
			durationEdits: {},
			benches: createListResource({
				doctype: 'Bench',
				fields: ['name', 'status', 'is_development_bench'],
				filters: { group: this.releaseGroup, status: ['not in', ['Archived']] },
				orderBy: 'creation desc',
				auto: true,
				onSuccess: (data) => {
					this.loadCodeServerStatuses(data);
					this.loadBenchDevInfos(data);
					this.loadSshCerts(data);
				},
			}),
		};
	},
	computed: {
		$releaseGroup() {
			return getCachedDocumentResource('Release Group', this.releaseGroup);
		},
		actions() {
			const groupedActions = this.$releaseGroup.doc.actions.reduce(
				(acc, action) => {
					const group = action.group || 'General Actions';
					if (!acc[group]) acc[group] = [];
					acc[group].push(action);
					return acc;
				},
				{},
			);
			return Object.keys(groupedActions).map((group) => ({
				group,
				actions: groupedActions[group],
			}));
		},
	},
	methods: {
		async toggleDevBench(bench) {
			const enabling = !bench.is_development_bench;
			this.devLoading = { ...this.devLoading, [bench.name]: true };
			try {
				await call('press.api.client.run_doc_method', {
					dt: 'Bench',
					dn: bench.name,
					method: 'set_development_bench',
					args: JSON.stringify({ enable: enabling ? 1 : 0 }),
				});
				toast.success(
					enabling
						? `${bench.name} marked as development bench`
						: `${bench.name} unset from development bench`,
				);
				this.benches.reload();
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to update bench');
			} finally {
				this.devLoading = { ...this.devLoading, [bench.name]: false };
			}
		},
		async loadCodeServerStatuses(benches) {
			const statuses = {};
			const durations = { ...this.durationEdits };
			for (const b of benches) {
				try {
					statuses[b.name] = await call(
						'press.press.doctype.bench.bench_dev_overview.get_code_server_status',
						{ bench_name: b.name },
					);
					if (statuses[b.name]?.password_expiry_days != null) {
						durations[b.name] = statuses[b.name].password_expiry_days;
					}
				} catch (e) {
					// On fetch error: fail-open for the UI so the Launch button is still visible.
					// The backend mutation endpoints will still deny unauthorized access via
					// _ensure_code_server_role_access. This prevents a transient network blip
					// from making the Code Server controls disappear with no recourse.
					statuses[b.name] = { enabled: false, exists: false, status: null, can_use: true };
				}
			}
			this.codeServerStatus = statuses;
			this.durationEdits = durations;
		},
		async loadBenchDevInfos(benches) {
			const infos = {};
			for (const b of benches) {
				try {
					infos[b.name] = await call(
						'press.press.doctype.bench.bench_dev_overview.get_bench_dev_info',
						{ bench_name: b.name },
					);
				} catch (e) {
					// Fail-open: leave devInfos[b.name] null so the SSH Key warning card hides.
					infos[b.name] = null;
				}
			}
			this.devInfos = infos;
		},
		async loadSshCerts(benches) {
			const certs = {};
			for (const b of benches) {
				try {
					certs[b.name] = await call(
						'press.press.doctype.bench.bench_dev_overview.get_ssh_certificate',
						{ bench_name: b.name },
					);
				} catch (e) {
					certs[b.name] = null;
				}
			}
			this.sshCerts = certs;
		},
		formatCertExpiry(secs) {
			if (!secs || secs <= 0) return 'expired';
			const h = Math.floor(secs / 3600);
			const m = Math.floor((secs % 3600) / 60);
			if (h > 0) return `expires in ${h}h ${m}m`;
			return `expires in ${m}m`;
		},
		async generateCert(bench) {
			if (this.certGenLoading[bench.name]) return;
			this.certGenLoading = { ...this.certGenLoading, [bench.name]: true };
			try {
				const result = await call(
					'press.press.doctype.bench.bench_dev_overview.generate_ssh_certificate',
					{ bench_name: bench.name },
				);
				this.sshCerts = { ...this.sshCerts, [bench.name]: result };
				// Trigger browser download of the cert as id_ed25519-cert.pub
				if (result?.certificate) {
					const blob = new Blob([result.certificate], { type: 'text/plain' });
					const url = URL.createObjectURL(blob);
					const a = document.createElement('a');
					a.href = url;
					a.download = 'id_ed25519-cert.pub';
					document.body.appendChild(a);
					a.click();
					document.body.removeChild(a);
					URL.revokeObjectURL(url);
				}
				toast.success(`Certificate minted for ${result.principal}. Save id_ed25519-cert.pub next to your private key.`);
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to generate SSH certificate');
			} finally {
				this.certGenLoading = { ...this.certGenLoading, [bench.name]: false };
			}
		},

		localVscodeUrl(bench) {
			const info = this.devInfos[bench.name];
			if (!info) return '#';
			return `vscode://vscode-remote/ssh-remote+frappe@${info.server_ip}:${info.ssh_port}${info.bench_path}/apps`;
		},
		async restartBench(bench) {
			if (!confirm(`Restart ALL workers on ${bench.name}?\\nAny in-flight jobs on sites hosted by this bench will be interrupted.`)) return;
			this.benchRestartLoading = { ...this.benchRestartLoading, [bench.name]: true };
			try {
				await call(
					'press.press.doctype.bench.bench_dev_overview.restart_bench_for_site',
					{ bench_name: bench.name },
				);
				toast.success('Bench restarted');
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to restart bench');
			} finally {
				this.benchRestartLoading = { ...this.benchRestartLoading, [bench.name]: false };
			}
		},

		async launchCodeServer(bench) {
			this.codeServerLoading = { ...this.codeServerLoading, [bench.name]: true };
			const subdomain = `code-${bench.name.replace(/[^a-z0-9]/g, '-').slice(0, 30)}`;
			try {
				const res = await call(
					'press.press.doctype.bench.bench_dev_overview.setup_code_server',
					{ bench_name: bench.name, subdomain },
				);
				if (res?.error) {
					toast.error(res.error);
				} else {
					toast.success('Code Server setup started');
					this.loadCodeServerStatuses(this.benches.data || []);
				this.loadBenchDevInfos(this.benches.data || []);
				this.loadSshCerts(this.benches.data || []);
				}
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to launch Code Server');
			} finally {
				this.codeServerLoading = { ...this.codeServerLoading, [bench.name]: false };
			}
		},
		async refreshCodeServerStatus(bench) {
			try {
				const s = await call(
					'press.press.doctype.bench.bench_dev_overview.get_code_server_status',
					{ bench_name: bench.name },
				);
				this.codeServerStatus = { ...this.codeServerStatus, [bench.name]: s };
			} catch (e) {
				// ignore
			}
		},
		async copyCodeServerPassword(bench) {
			const pwd = this.codeServerStatus[bench.name]?.password;
			if (!pwd) return;
			try {
				await navigator.clipboard.writeText(pwd);
				this.revealedPasswords = { ...this.revealedPasswords, [bench.name]: true };
				toast.success('Code Server password copied to clipboard');
				// Hide again after 15 s
				setTimeout(() => {
					this.revealedPasswords = { ...this.revealedPasswords, [bench.name]: false };
				}, 15000);
			} catch (e) {
				toast.error('Could not copy — select and copy manually');
				this.revealedPasswords = { ...this.revealedPasswords, [bench.name]: true };
			}
		},
		formatExpiry(ts) {
			if (!ts) return '';
			const target = new Date(ts);
			const diff = target - new Date();
			if (diff <= 0) return 'expired — rotating on next check';
			const days = Math.floor(diff / 86400000);
			const hours = Math.floor((diff % 86400000) / 3600000);
			const minutes = Math.floor((diff % 3600000) / 60000);
			if (days > 0) return `expires in ${days}d ${hours}h`;
			if (hours > 0) return `expires in ${hours}h ${minutes}m`;
			return `expires in ${minutes}m`;
		},
		async rotateCodeServerPassword(bench) {
			if (!confirm('Rotate the Code Server password now?\\nAny active browser session will be disconnected.')) return;
			this.rotateLoading = { ...this.rotateLoading, [bench.name]: true };
			try {
				await call(
					'press.press.doctype.bench.bench_dev_overview.rotate_code_server_password',
					{ bench_name: bench.name },
				);
				toast.success('Password rotated');
				await this.loadCodeServerStatuses(this.benches.data || []);
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to rotate password');
			} finally {
				this.rotateLoading = { ...this.rotateLoading, [bench.name]: false };
			}
		},
		async saveDuration(bench) {
			const cur = this.codeServerStatus[bench.name]?.password_expiry_days;
			const newVal = Number(this.durationEdits[bench.name]);
			if (Number.isNaN(newVal) || newVal < 0 || newVal === cur) return;
			try {
				await call(
					'press.press.doctype.bench.bench_dev_overview.set_code_server_password_expiry_days',
					{ bench_name: bench.name, days: newVal },
				);
				toast.success(`Auto-rotate set to ${newVal} day${newVal === 1 ? '' : 's'}`);
				await this.loadCodeServerStatuses(this.benches.data || []);
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to update duration');
			}
		},
		async restartCodeServer(bench) {
			this.restartLoading = { ...this.restartLoading, [bench.name]: true };
			try {
				await call(
					'press.press.doctype.bench.bench_dev_overview.restart_code_server',
					{ bench_name: bench.name },
				);
				toast.success('Code Server restart queued — should be back in 10–30 s');
				// Re-poll after 8 s so the UI picks up the new state
				setTimeout(() => this.loadCodeServerStatuses(this.benches.data || []), 8000);
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to restart Code Server');
			} finally {
				this.restartLoading = { ...this.restartLoading, [bench.name]: false };
			}
		},
	},
};
</script>
