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
							v-if="codeServerStatus[bench.name]?.status === 'Running' && codeServerStatus[bench.name]?.url"
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
						<Button
							v-else-if="codeServerStatus[bench.name]?.status === 'Pending'"
							class="whitespace-nowrap"
							:loading="true"
							disabled
						>Code Server starting…</Button>
						<Button
							v-else
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
			revealedPasswords: {},
			rotateLoading: {},
			durationEdits: {},
			benches: createListResource({
				doctype: 'Bench',
				fields: ['name', 'status', 'is_development_bench'],
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
					statuses[b.name] = { enabled: false, exists: false, status: null };
				}
			}
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
	},
};
</script>
