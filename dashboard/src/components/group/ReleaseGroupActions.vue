<template>
	<div class="mx-auto max-w-3xl space-y-4">
		<div v-if="benches.data?.length" class="rounded border border-gray-200">
			<div class="border-b border-gray-200 p-5 text-lg font-semibold">Dev Actions</div>

			<!-- Collapsible workflow explainer -->
			<div class="border-b border-gray-200">
				<button
					type="button"
					class="flex w-full items-center justify-between px-5 py-3 text-left transition hover:bg-gray-50"
					@click="showWorkflow = !showWorkflow"
				>
					<div class="flex items-center gap-2">
						<FeatherIcon name="info" class="h-4 w-4 text-blue-600" />
						<span class="text-sm font-medium text-gray-900">How to use a Dev Bench</span>
						<span class="hidden text-xs text-gray-500 sm:inline">— edit code in the bench, see changes live, push back to GitHub</span>
					</div>
					<FeatherIcon
						:name="showWorkflow ? 'chevron-up' : 'chevron-down'"
						class="h-4 w-4 text-gray-400"
					/>
				</button>
				<div
					v-if="showWorkflow"
					class="space-y-3 border-t border-gray-200 bg-gray-50 px-5 py-4 text-sm text-gray-700"
				>
					<div>
						<div class="font-medium text-gray-900">1. Mark the bench as a Dev Bench</div>
						<p class="mt-0.5 text-xs leading-relaxed">
							Click <strong>Mark as Dev Bench</strong> on the bench tile below. Sets
							<code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">is_development_bench=1</code>
							and enables developer-mode in
							<code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">site_config.json</code>
							so Python changes hot-reload.
						</p>
					</div>
					<div>
						<div class="font-medium text-gray-900">2. Edit the code</div>
						<ul class="mt-0.5 list-disc space-y-1 pl-5 text-xs leading-relaxed">
							<li>
								<strong>Open in VS Code</strong> tile — local VS Code Desktop over Remote-SSH (recommended). One click handles SSH cert + launch.
							</li>
							<li>
								Or SSH directly:
								<code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">
									ssh -A &lt;bench-name&gt;@&lt;proxy_server&gt; -p 2222
								</code>
								<span class="text-gray-500">(generate a cert first via the SSH Certificate tile)</span>
							</li>
							<li>
								In container, app code lives at
								<code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">~/frappe-bench/apps/&lt;app_name&gt;/</code>
							</li>
						</ul>
					</div>
					<div>
						<div class="font-medium text-gray-900">3. See changes take effect</div>
						<ul class="mt-0.5 space-y-1 text-xs leading-relaxed">
							<li>
								<strong>Python</strong> (controllers, hooks, server scripts):
								<code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">bench --site &lt;site&gt; restart</code>
							</li>
							<li>
								<strong>Client script / DocType JSON / JS:</strong> hard-reload browser (Ctrl+F5)
							</li>
							<li>
								<strong>Schema change / new DocType:</strong>
								<code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">bench --site &lt;site&gt; migrate</code>
							</li>
							<li>
								<strong>CSS rebuild:</strong>
								<code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">bench build --app &lt;app&gt;</code>
							</li>
						</ul>
					</div>
					<div>
						<div class="font-medium text-gray-900">4. Push changes back to GitHub</div>
						<p class="mt-0.5 text-xs leading-relaxed">
							Open any site in this bench →
							<strong>Dev</strong> tab (URL:
							<code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">/dashboard/sites/&lt;site&gt;/dev</code>).
							The <strong>App Status</strong> table shows each app as
							<span class="rounded bg-green-100 px-1 text-[11px] text-green-700">Clean</span>
							or
							<span class="rounded bg-orange-100 px-1 text-[11px] text-orange-700">N dirty</span>.
							Click <strong>Push&nbsp;↓</strong> on a dirty row → edit the commit message → click
							<strong>Push to GitHub</strong>. The dashboard configures the remote, checks out the
							working branch, and pushes via your team's GitHub token.
							<br />
							<span class="text-gray-500">
								Don't run
								<code class="rounded bg-gray-200 px-1 py-0.5 text-[11px]">git remote add origin</code>
								manually inside the container — the deploy keys are read-only and auth will fail.
								The dashboard handles this for you.
							</span>
							<br />
							<span class="text-gray-500">
								The bench-level <strong>Apps</strong> tab only shows
								<em>Update Available</em> (pulling upstream). The push direction lives on the
								Site Dev tab.
							</span>
						</p>
					</div>
					<div class="flex items-start gap-2 rounded border border-yellow-200 bg-yellow-50 p-2.5 text-xs text-yellow-800">
						<FeatherIcon name="alert-triangle" class="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
						<div>
							<strong>Edits live only in the running container.</strong>
							If the container restarts before you push to GitHub, your changes are lost.
							Always push before any deploy / restart action.
						</div>
					</div>
				</div>
			</div>

			<div
				v-for="bench in benches.data"
				:key="bench.name"
				class="border-b border-gray-200 p-5 last:border-b-0"
			>
				<!-- Bench head: name + helper + status pill -->
				<div class="mb-4 flex items-start justify-between gap-4">
					<div>
						<h3 class="font-mono text-base font-semibold text-gray-900">{{ bench.name }}</h3>
						<p class="mt-0.5 text-sm text-gray-500">
							{{
								bench.is_development_bench
									? 'This bench is marked as a development bench'
									: 'Mark this bench for development use only'
							}}
						</p>
					</div>
					<span
						v-if="codeServerStatus[bench.name]?.can_use !== false"
						class="inline-flex flex-shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
						:class="codeServerStatusClass(bench)"
					>
						<span class="h-1.5 w-1.5 rounded-full" :class="codeServerDotClass(bench)"></span>
						{{ codeServerStatusLabel(bench) }}
					</span>
				</div>

				<!-- Code Server KV panel (gated by can_use — feature must be enabled for the team) -->
				<div
					v-if="codeServerStatus[bench.name]?.can_use !== false"
					class="mb-3 overflow-hidden rounded-lg border border-gray-200 bg-gray-50"
				>
					<div class="border-b border-gray-200 bg-white px-4 py-2.5">
						<span class="text-xs font-semibold text-gray-900">Code Server</span>
					</div>

					<template v-if="codeServerStatus[bench.name]?.status === 'Running' && codeServerStatus[bench.name]?.url">
						<div class="grid grid-cols-[90px_1fr] items-center gap-3 px-4 py-2.5">
							<div class="text-[11px] font-medium uppercase tracking-wider text-gray-500">URL</div>
							<div class="flex min-w-0 items-center gap-1.5 font-mono text-[12.5px] text-gray-900">
								<span class="flex-1 truncate">{{ codeServerStatus[bench.name].url }}</span>
								<button
									class="inline-flex h-6 w-6 items-center justify-center rounded text-gray-500 hover:bg-gray-200 hover:text-gray-900"
									@click="copyToClipboard(codeServerStatus[bench.name].url, 'URL copied')"
									title="Copy URL"
								>
									<FeatherIcon name="copy" class="h-3.5 w-3.5" />
								</button>
								<a
									:href="codeServerStatus[bench.name].url"
									target="_blank"
									class="inline-flex h-6 w-6 items-center justify-center rounded text-gray-500 hover:bg-gray-200 hover:text-gray-900"
									title="Open in new tab"
								>
									<FeatherIcon name="external-link" class="h-3.5 w-3.5" />
								</a>
							</div>
						</div>
						<div class="grid grid-cols-[90px_1fr] items-center gap-3 border-t border-gray-200 px-4 py-2.5">
							<div class="text-[11px] font-medium uppercase tracking-wider text-gray-500">Password</div>
							<div class="flex min-w-0 items-center gap-1.5 font-mono text-[12.5px]">
								<span
									class="flex-1 truncate select-none"
									:class="revealedPasswords[bench.name] ? 'select-text font-medium text-gray-900' : 'tracking-widest text-gray-500'"
								>
									{{ revealedPasswords[bench.name] ? codeServerStatus[bench.name].password : '••••••••••••' }}
								</span>
								<button
									class="inline-flex h-6 w-6 items-center justify-center rounded text-gray-500 hover:bg-gray-200 hover:text-gray-900"
									:class="revealedPasswords[bench.name] && 'text-blue-600'"
									@click="togglePasswordReveal(bench)"
									:title="revealedPasswords[bench.name] ? 'Hide password' : 'Show password'"
								>
									<FeatherIcon :name="revealedPasswords[bench.name] ? 'eye-off' : 'eye'" class="h-3.5 w-3.5" />
								</button>
								<button
									class="inline-flex h-6 w-6 items-center justify-center rounded text-gray-500 hover:bg-gray-200 hover:text-gray-900"
									@click="copyCodeServerPassword(bench)"
									title="Copy password"
								>
									<FeatherIcon name="copy" class="h-3.5 w-3.5" />
								</button>
							</div>
						</div>
						<div class="space-y-1.5 border-t border-gray-200 bg-white px-4 py-2.5 text-xs text-gray-500">
							<div class="flex items-center gap-2">
								<span :class="codeServerStatus[bench.name]?.password_is_expired ? 'font-medium text-red-600' : ''">
									{{ formatExpiry(codeServerStatus[bench.name].password_expires_at) }}
								</span>
								<span class="text-gray-300">·</span>
								<button
									:disabled="rotateLoading[bench.name]"
									@click="rotateCodeServerPassword(bench)"
									class="font-medium text-gray-700 hover:text-gray-900 hover:underline"
								>
									{{ rotateLoading[bench.name] ? 'Rotating…' : 'Rotate now' }}
								</button>
								<span class="text-gray-300">·</span>
								<button
									:disabled="restartLoading[bench.name]"
									@click="restartCodeServer(bench)"
									class="font-medium text-gray-700 hover:text-gray-900 hover:underline"
								>
									{{ restartLoading[bench.name] ? 'Restarting…' : 'Restart' }}
								</button>
							</div>
							<div class="flex items-center gap-1.5">
								<span>Auto-rotate every</span>
								<input
									type="number"
									min="0"
									class="w-9 rounded border border-gray-200 px-1 py-0 text-right text-xs focus:border-blue-500 focus:outline-none"
									v-model.number="durationEdits[bench.name]"
									@blur="saveDuration(bench)"
									@keyup.enter="saveDuration(bench)"
								/>
								<span>days</span>
							</div>
						</div>
					</template>

					<template v-else-if="codeServerStatus[bench.name]?.exists && codeServerStatus[bench.name]?.status !== 'Running'">
						<div class="flex flex-col items-center gap-2 px-4 py-6 text-center text-sm text-gray-500">
							<span>Code Server {{ codeServerStatus[bench.name].status === 'Pending' ? 'starting…' : codeServerStatus[bench.name].status.toLowerCase() }}</span>
							<Button
								:loading="restartLoading[bench.name]"
								@click="restartCodeServer(bench)"
								class="mt-1"
							>
								Restart Code Server
							</Button>
						</div>
					</template>

					<template v-else>
						<div class="flex flex-col items-center gap-2 px-4 py-6 text-center text-sm text-gray-500">
							<span>Code Server is not running for this bench.</span>
							<Button
								:loading="codeServerLoading[bench.name]"
								variant="solid"
								@click="launchCodeServer(bench)"
								class="mt-1"
							>
								Launch Code Server
							</Button>
						</div>
					</template>
				</div>

				<!-- Code Server feature gated by team plan -->
				<div
					v-else
					class="mb-3 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm italic text-gray-500"
				>
					Code Server is not enabled on your team plan.
				</div>

				<!-- 4-tile action grid -->
				<div class="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
					<button
						type="button"
						class="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-3.5 text-left transition hover:border-gray-300 hover:shadow-sm"
						@click="openVscodeDialog(bench)"
					>
						<div class="flex h-7 w-7 items-center justify-center rounded-md bg-blue-50 text-blue-600">
							<FeatherIcon name="code" class="h-4 w-4" />
						</div>
						<div>
							<h4 class="text-[13px] font-semibold text-gray-900">Open in VS Code</h4>
							<p class="mt-0.5 text-[11.5px] leading-snug text-gray-500">
								Local VS Code Desktop via Remote-SSH.
							</p>
						</div>
					</button>

					<button
						type="button"
						class="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-3.5 text-left transition hover:border-gray-300 hover:shadow-sm disabled:cursor-wait disabled:opacity-60"
						:disabled="devLoading[bench.name]"
						@click="toggleDevBench(bench)"
					>
						<div class="flex h-7 w-7 items-center justify-center rounded-md bg-gray-100 text-gray-700">
							<FeatherIcon name="tag" class="h-4 w-4" />
						</div>
						<div>
							<h4 class="text-[13px] font-semibold text-gray-900">
								{{ bench.is_development_bench ? 'Unset Dev Bench' : 'Mark as Dev Bench' }}
							</h4>
							<p class="mt-0.5 text-[11.5px] leading-snug text-gray-500">
								Tag this bench for development use only.
							</p>
						</div>
					</button>

					<button
						type="button"
						class="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-3.5 text-left transition hover:border-gray-300 hover:shadow-sm"
						@click="openSshDialog(bench)"
					>
						<div class="flex h-7 w-7 items-center justify-center rounded-md bg-gray-100 text-gray-700">
							<FeatherIcon name="lock" class="h-4 w-4" />
						</div>
						<div>
							<h4 class="text-[13px] font-semibold text-gray-900">Generate SSH Certificate</h4>
							<p class="mt-0.5 text-[11.5px] leading-snug text-gray-500">
								Required for "Open in VS Code". Valid 6 hours.
							</p>
						</div>
					</button>

					<button
						type="button"
						class="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-3.5 text-left transition hover:border-gray-300 hover:shadow-sm"
						@click="confirmRestartBench(bench)"
					>
						<div class="flex h-7 w-7 items-center justify-center rounded-md bg-gray-100 text-gray-700">
							<FeatherIcon name="refresh-cw" class="h-4 w-4" />
						</div>
						<div>
							<h4 class="text-[13px] font-semibold text-gray-900">Restart Bench</h4>
							<p class="mt-0.5 text-[11.5px] leading-snug text-gray-500">
								Restart all bench workers (web, scheduler, queues).
							</p>
						</div>
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
import {
	call,
	createListResource,
	getCachedDocumentResource,
	FeatherIcon,
	Button,
} from 'frappe-ui';
import { h, defineAsyncComponent } from 'vue';
import { toast } from 'vue-sonner';
import { renderDialog, confirmDialog } from '../../utils/components';
import SSHCertificateDialog from './SSHCertificateDialog.vue';
import ReleaseGroupActionCell from './ReleaseGroupActionCell.vue';

const VSCodeLaunchDialog = defineAsyncComponent(
	() => import('./VSCodeLaunchDialog.vue'),
);

export default {
	props: ['releaseGroup'],
	components: { FeatherIcon, Button, ReleaseGroupActionCell },
	data() {
		return {
			showWorkflow: false,
			devLoading: {},
			codeServerLoading: {},
			codeServerStatus: {},
			revealedPasswords: {},
			rotateLoading: {},
			restartLoading: {},
			durationEdits: {},
			benches: createListResource({
				doctype: 'Bench',
				fields: ['name', 'status', 'is_development_bench', 'group'],
				filters: { group: this.releaseGroup, status: ['not in', ['Archived']] },
				orderBy: 'creation desc',
				auto: true,
				onSuccess: (data) => this.loadCodeServerStatuses(data),
			}),
		};
	},
	computed: {
		$releaseGroup() {
			return getCachedDocumentResource('Release Group', this.releaseGroup);
		},
		actions() {
			if (!this.$releaseGroup?.doc?.actions) return [];
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
			const results = await Promise.allSettled(
				benches.map((b) =>
					call(
						'press.press.doctype.bench.bench_dev_overview.get_code_server_status',
						{ bench_name: b.name },
					),
				),
			);
			benches.forEach((b, i) => {
				const r = results[i];
				if (r.status === 'fulfilled') {
					statuses[b.name] = r.value;
					if (r.value?.password_expiry_days != null) {
						durations[b.name] = r.value.password_expiry_days;
					}
				} else {
					// On fetch error: fail-open for the UI so the Launch button is still visible.
					// The backend mutation endpoints will still deny unauthorized access via
					// _ensure_code_server_role_access. This prevents a transient network blip
					// from making the Code Server controls disappear with no recourse.
					statuses[b.name] = { enabled: false, exists: false, status: null, can_use: true };
				}
			});
			this.codeServerStatus = statuses;
			this.durationEdits = durations;
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
				}
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to launch Code Server');
			} finally {
				this.codeServerLoading = { ...this.codeServerLoading, [bench.name]: false };
			}
		},

		togglePasswordReveal(bench) {
			this.revealedPasswords = {
				...this.revealedPasswords,
				[bench.name]: !this.revealedPasswords[bench.name],
			};
		},

		async copyCodeServerPassword(bench) {
			const pwd = this.codeServerStatus[bench.name]?.password;
			if (!pwd) return;
			await this.copyToClipboard(pwd, 'Code Server password copied');
		},

		async copyToClipboard(text, message = 'Copied') {
			try {
				await navigator.clipboard.writeText(text);
				toast.success(message);
			} catch (e) {
				toast.error('Could not copy — your browser may be blocking clipboard access');
			}
		},

		formatExpiry(ts) {
			if (!ts) return 'no expiry';
			const target = new Date(ts);
			const diff = target - new Date();
			if (diff <= 0) return 'expired — rotating on next check';
			const days = Math.floor(diff / 86400000);
			const hours = Math.floor((diff % 86400000) / 3600000);
			const minutes = Math.floor((diff % 3600000) / 60000);
			if (days > 0) return `Expires in ${days}d ${hours}h`;
			if (hours > 0) return `Expires in ${hours}h ${minutes}m`;
			return `Expires in ${minutes}m`;
		},

		rotateCodeServerPassword(bench) {
			confirmDialog({
				title: 'Rotate Code Server Password',
				message:
					'Rotate the password now? Any active browser session will be disconnected.',
				primaryAction: {
					label: 'Rotate',
					variant: 'solid',
					theme: 'red',
					onClick: ({ hide }) => {
						this.rotateLoading = {
							...this.rotateLoading,
							[bench.name]: true,
						};
						return toast.promise(
							call(
								'press.press.doctype.bench.bench_dev_overview.rotate_code_server_password',
								{ bench_name: bench.name },
							)
								.then(async () => {
									await this.loadCodeServerStatuses(
										this.benches.data || [],
									);
									hide();
								})
								.finally(() => {
									this.rotateLoading = {
										...this.rotateLoading,
										[bench.name]: false,
									};
								}),
							{
								loading: 'Rotating password…',
								success: 'Password rotated',
								error: (e) =>
									e?.messages?.join(', ') ||
									'Failed to rotate password',
							},
						);
					},
				},
			});
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
				setTimeout(() => this.loadCodeServerStatuses(this.benches.data || []), 8000);
			} catch (e) {
				toast.error(e?.messages?.join(', ') || 'Failed to restart Code Server');
			} finally {
				this.restartLoading = { ...this.restartLoading, [bench.name]: false };
			}
		},

		openVscodeDialog(bench) {
			renderDialog(
				h(VSCodeLaunchDialog, {
					bench: bench.name,
					releaseGroup: this.releaseGroup,
				}),
			);
		},

		openSshDialog(bench) {
			renderDialog(
				h(SSHCertificateDialog, {
					bench: bench.name,
					releaseGroup: this.releaseGroup,
				}),
			);
		},

		confirmRestartBench(bench) {
			confirmDialog({
				title: 'Restart Bench',
				message: `Are you sure you want to restart the bench <b>${bench.name}</b>?`,
				primaryAction: {
					label: 'Restart',
					variant: 'solid',
					theme: 'red',
					onClick: ({ hide }) => {
						toast.promise(
							call('press.api.client.run_doc_method', {
								dt: 'Bench',
								dn: bench.name,
								method: 'restart',
							}),
							{
								loading: 'Restarting bench...',
								success: () => {
									hide();
									return 'Bench will restart shortly';
								},
								error: (e) =>
									e?.messages?.join('\n') || 'Failed to restart bench',
							},
						);
					},
				},
			});
		},

		codeServerStatusClass(bench) {
			const s = this.codeServerStatus[bench.name];
			if (s?.status === 'Running') return 'bg-green-50 text-green-700';
			if (s?.exists) return 'bg-yellow-50 text-yellow-700';
			return 'bg-gray-100 text-gray-600';
		},
		codeServerDotClass(bench) {
			const s = this.codeServerStatus[bench.name];
			if (s?.status === 'Running') return 'bg-green-500';
			if (s?.exists) return 'bg-yellow-500';
			return 'bg-gray-400';
		},
		codeServerStatusLabel(bench) {
			const s = this.codeServerStatus[bench.name];
			if (s?.status === 'Running') return 'Code Server running';
			if (s?.status === 'Pending') return 'Code Server starting';
			if (s?.exists) return `Code Server ${String(s.status || '').toLowerCase()}`;
			return 'Code Server stopped';
		},
	},
};
</script>
