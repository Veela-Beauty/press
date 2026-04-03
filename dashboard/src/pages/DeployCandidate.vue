<template>
	<div class="p-5">
		<div v-if="isLoading" class="flex items-center justify-center h-96">
			<div class="text-center">
				<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
				<p class="text-gray-600">Loading build information...</p>
			</div>
		</div>
		<div v-else-if="!deploy" class="mt-20">
			<div class="rounded-lg border border-red-200 bg-red-50 p-4">
				<h3 class="text-sm font-medium text-red-900">Build Not Found</h3>
				<p class="mt-2 text-sm text-red-700">
					The build <code class="bg-red-100 px-2 py-1 rounded">{{ id }}</code> could not be found or you don't have access to it.
				</p>
				<Button :route="{ name: `${object.doctype} Detail Deploys` }" class="mt-4">
					<template #prefix>
						<lucide-arrow-left class="inline-block h-4 w-4" />
					</template>
					All deploys
				</Button>
			</div>
		</div>
		<template v-else>
		<!-- Failure Banner -->
		<div v-if="deploy.status === 'Failure'" class="mb-5 rounded-lg border border-red-200 bg-red-50 p-4">
			<div class="flex items-start gap-3">
				<lucide-alert-triangle class="mt-0.5 h-5 w-5 flex-shrink-0 text-red-600" />
				<div class="flex-1 min-w-0">
					<h3 class="text-sm font-semibold text-red-900">
						Build Failed
						<span v-if="failureDetails?.failed_step" class="font-normal">
							at <strong>{{ failureDetails.failed_step.stage }} / {{ failureDetails.failed_step.step }}</strong>
						</span>
						<span v-else class="font-normal"> — no step details recorded</span>
					</h3>
					<p v-if="failureDetails?.build_error" class="mt-1 text-sm text-red-700">
						{{ failureDetails.build_error }}
					</p>
					<div v-if="failureDetails" class="mt-2 flex items-center gap-4 text-xs text-red-600">
						<span>{{ failureDetails.completed_steps }} / {{ failureDetails.total_steps }} steps completed</span>
					</div>
					<div v-if="failureDetails?.failed_step?.output" class="mt-3">
						<details class="group">
							<summary class="cursor-pointer text-xs font-medium text-red-700 hover:text-red-900">
								Show error output
							</summary>
							<pre class="mt-2 max-h-48 overflow-auto rounded bg-red-100 p-3 text-xs text-red-900 font-mono whitespace-pre-wrap">{{ failureDetails.failed_step.output }}</pre>
						</details>
					</div>
				</div>
			</div>
		</div>

		<AlertAddressableError
			v-if="error"
			class="mb-5"
			:name="error.name"
			:title="error.title"
			@done="$resources.errors.reload()"
		/>
		<AlertAddressableError
			v-for="w in warningItems"
			:key="w.name"
			class="mb-5"
			:name="w.name"
			:title="w.title"
			type="warning"
			@done="$resources.warnings.reload()"
		/>

		<AlertBanner
			v-if="alertMessage && !error && !warningItems.length"
			:title="alertMessage"
			type="warning"
			class="mb-5"
		/>
		<div class="flex items-center gap-3">
			<Button :route="{ name: `${object.doctype} Detail Deploys` }">
				<template #prefix>
					<lucide-arrow-left class="inline-block h-4 w-4" />
				</template>
				All deploys
			</Button>
			<Button v-if="previousBuildId" size="sm" variant="subtle" :route="{ name: 'Deploy Candidate', params: { id: previousBuildId } }">
				<template #prefix>
					<lucide-history class="h-3.5 w-3.5" />
				</template>
				Previous build
			</Button>
		</div>

		<div class="mt-3">
			<div class="flex w-full items-center">
				<h2 class="text-lg font-semibold text-gray-900">
					{{ deploy.deploy_candidate }}
				</h2>
				<Badge class="ml-2" :label="deploy.status" :theme="statusBadgeTheme" />
				<div v-if="isBuilding" class="ml-4 flex flex-1 items-center gap-3">
					<div class="flex-1">
						<div class="h-2 w-full overflow-hidden rounded-full bg-gray-200">
							<div
								class="h-full rounded-full transition-all duration-1000 ease-linear"
								:class="progressColor"
								:style="{ width: progressPercent + '%' }"
							></div>
						</div>
					</div>
					<div class="flex flex-col items-end gap-0.5">
						<span class="whitespace-nowrap text-sm text-gray-600">
							{{ elapsedFormatted }} / ~{{ estimateFormatted }}
							<span v-if="estimateConfidence === 'low'" class="text-xs text-gray-400">(est.)</span>
						</span>
						<span v-if="currentRunningStep" class="text-xs text-blue-600 truncate max-w-[200px]">
							{{ currentRunningStep }}
						</span>
					</div>
				</div>
				<div v-else-if="deploy.status === 'Success' && deploy.build_duration" class="ml-4 text-sm text-gray-500">
					Completed in {{ $format.duration(deploy.build_duration) }}
					<span v-if="durationComparison" :class="durationComparison.startsWith('↓') ? 'text-green-600' : 'text-orange-500'" class="ml-1 text-xs">
						{{ durationComparison }}
					</span>
				</div>
				<div class="ml-auto flex items-center space-x-2">
					<Button
						@click="retryDeploy"
						v-if="deploy && ['Failure', 'Draft'].includes(deploy.status)"
						variant="solid"
						:loading="retrying"
					>
						<template #prefix>
							<lucide-rotate-ccw class="h-4 w-4" />
						</template>
						Retry Deploy
					</Button>
					<Button
						@click="stopBuild"
						v-if="deploy && ['Running', 'Pending', 'Preparing', 'Scheduled'].includes(deploy.status)"
						theme="red"
					>
						{{ deploy.status === 'Running' ? 'Stop Build' : 'Cancel Build' }}
					</Button>
					<Button
						@click="forceRetry"
						v-if="deploy && deploy.status === 'Running' && isStuck"
						theme="red"
						variant="outline"
						:loading="retrying"
					>
						Force Retry
					</Button>
					<Button
						@click="$resources.deploy.reload()"
						:loading="$resources.deploy.get.loading"
					>
						<template #icon>
							<lucide-refresh-ccw class="h-4 w-4" />
						</template>
					</Button>
					<Dropdown v-if="dropdownOptions?.length" :options="dropdownOptions">
						<template v-slot="{ open }">
							<Button>
								<template #icon>
									<lucide-more-horizontal class="h-4 w-4" />
								</template>
							</Button>
						</template>
					</Dropdown>
				</div>
			</div>
			<div>
				<div class="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
					<div>
						<div class="text-sm font-medium text-gray-500">Creation</div>
						<div class="mt-2 text-sm text-gray-900">
							{{ $format.date(deploy.creation, 'lll') }}
						</div>
					</div>
					<div>
						<div class="text-sm font-medium text-gray-500">Creator</div>
						<div class="mt-2 text-sm text-gray-900">
							{{ deploy.owner }}
						</div>
					</div>
					<div>
						<div class="text-sm font-medium text-gray-500">Duration</div>
						<div class="mt-2 text-sm text-gray-900">
							{{
								deploy.build_end ? $format.duration(deploy.build_duration) : '-'
							}}
						</div>
					</div>
					<div>
						<div class="text-sm font-medium text-gray-500">Start</div>
						<div class="mt-2 text-sm text-gray-900">
							{{ $format.date(deploy.build_start, 'lll') }}
						</div>
					</div>
					<div>
						<div class="text-sm font-medium text-gray-500">End</div>
						<div class="mt-2 text-sm text-gray-900">
							{{
								deploy.build_end ? $format.date(deploy.build_end, 'lll') : '-'
							}}
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- Build Steps grouped by stage -->
		<div :class="deploy.build_error ? 'mt-4' : 'mt-8'" class="space-y-3">
			<div v-for="group in groupedSteps" :key="group.stage" class="rounded-lg border border-gray-200">
				<button
					class="flex w-full items-center justify-between px-3 py-2 text-left text-sm font-medium hover:bg-gray-50"
					:class="{ 'bg-red-50': group.status === 'Failure', 'bg-green-50': group.status === 'Success' && !group.hasRunning }"
					@click="stageOpenState[group.stage] = !stageOpenState[group.stage]"
				>
					<div class="flex items-center gap-2">
						<lucide-chevron-right class="h-4 w-4 transition-transform" :class="{ 'rotate-90': stageOpenState[group.stage] }" />
						<span>{{ group.stage }}</span>
						<Badge size="sm" :label="`${group.completed}/${group.total}`" :theme="group.status === 'Failure' ? 'red' : group.status === 'Success' ? 'green' : 'gray'" />
					</div>
					<span v-if="group.duration" class="text-xs text-gray-500">{{ group.duration }}</span>
				</button>
				<div v-show="stageOpenState[group.stage]" class="border-t border-gray-200 px-1 py-1 space-y-1">
					<JobStep v-for="step in group.steps" :step="step" :key="step.name" />
				</div>
			</div>
			<JobStep v-for="job in deploy.jobs" :step="job" :key="job.name" />
		</div>
		</template>
	</div>
</template>
<script>
import { createResource, getCachedDocumentResource } from 'frappe-ui';
import { h } from 'vue';
import { toast } from 'vue-sonner';
import AlertAddressableError from '../components/AlertAddressableError.vue';
import AlertBanner from '../components/AlertBanner.vue';
import JobStep from '../components/JobStep.vue';
import AppVersionsDialog from '../dialogs/AppVersionsDialog.vue';
import { getObject } from '../objects';
import { confirmDialog, renderDialog } from '../utils/components';

export default {
	name: 'DeployCandidate',
	props: ['id', 'objectType'],
	components: {
		JobStep,
		AlertBanner,
		AlertAddressableError,
	},
	resources: {
		deploy() {
			return {
				type: 'document',
				doctype: 'Deploy Candidate Build',
				name: this.id,
				transform: this.transformDeploy,
			};
		},
		estimate() {
			return {
				url: 'press.press.doctype.deploy_candidate_build.deploy_candidate_build.get_build_estimate',
				params: { group: this.$resources.deploy?.doc?.group },
				auto: false,
			};
		},
		failureDiag() {
			return {
				url: 'press.press.doctype.deploy_candidate_build.build_diagnostics.get_failure_details',
				params: { dn: this.id },
				auto: false,
			};
		},
		warnings() {
			return {
				type: 'list',
				cache: [
					'Press Notification',
					'Warning',
					'Deploy Candidate Build',
					this.id,
				],
				doctype: 'Press Notification',
				auto: true,
				fields: ['title', 'name'],
				filters: {
					document_type: 'Deploy Candidate Build',
					document_name: this.id,
					class: 'Warning',
				},
				limit: 5,
			};
		},
		errors() {
			return {
				type: 'list',
				cache: [
					'Press Notification',
					'Error',
					'Deploy Candidate Build',
					this.id,
				],
				doctype: 'Press Notification',
				auto: true,
				fields: ['title', 'name'],
				filters: {
					document_type: 'Deploy Candidate Build',
					document_name: this.id,
					is_actionable: true,
					class: 'Error',
				},
				limit: 1,
			};
		},
	},
	data() {
		return {
			elapsedSeconds: 0,
			elapsedTimer: null,
			autoRefreshTimer: null,
			retrying: false,
			previousBuildId: null,
			stageOpenState: {},
		};
	},
	watch: {
		'deploy.group'(group) {
			if (group && this.isBuilding) {
				this.$resources.estimate.submit({ group });
			}
		},
		'deploy.status': {
			handler(status) {
				if (['Running', 'Pending', 'Preparing', 'Scheduled'].includes(status)) {
					this.startTimer();
					this.startAutoRefresh();
				} else {
					this.stopTimer();
					this.stopAutoRefresh();
				}
				if (status === 'Failure') {
					this.$resources.failureDiag.submit({ dn: this.id });
				}
				if (status === 'Success') {
					this.$resources.estimate.submit({ group: this.deploy?.group });
				}
			},
			immediate: true,
		},
	},
	mounted() {
		this.previousBuildId = this.$route?.query?.previous || null;
		this.$socket.emit('doc_subscribe', 'Deploy Candidate Build', this.id);
		this.$socket.on(`bench_deploy:${this.id}:steps`, (data) => {
			if (data.name === this.id && this.$resources.deploy.doc) {
				this.$resources.deploy.doc.build_steps = this.transformDeploy({
					build_steps: data.steps,
				})?.build_steps;
			}
		});
		this.$socket.on(`bench_deploy:${this.id}:finished`, () => {
			const rgDoc = getCachedDocumentResource(
				'Release Group',
				this.$resources.deploy.doc?.group,
			);
			if (rgDoc) rgDoc.reload();
			this.$resources.deploy.reload();
			this.$resources.errors.reload();
			this.$resources.warnings.reload();
		});
	},
	beforeUnmount() {
		this.$socket.emit('doc_unsubscribe', 'Deploy Candidate Build', this.id);
		this.$socket.off(`bench_deploy:${this.id}:steps`);
		this.$socket.off(`bench_deploy:${this.id}:finished`);
		this.stopTimer();
		this.stopAutoRefresh();
	},
	computed: {
		deploy() {
			return this.$resources.deploy?.doc;
		},
		isLoading() {
			return this.$resources.deploy?.get?.loading && !this.$resources.deploy?.get?.fetched;
		},
		isBuilding() {
			return this.deploy && ['Running', 'Pending', 'Preparing', 'Scheduled'].includes(this.deploy.status);
		},
		isStuck() {
			// Show "Force Retry" if build has been running for more than 10 minutes
			if (!this.deploy?.build_start || this.deploy.status !== 'Running') return false;
			return this.elapsedSeconds > 600;
		},
		failureDetails() {
			return this.$resources.failureDiag?.data ?? null;
		},
		estimatedSeconds() {
			return this.$resources.estimate?.data?.estimated_seconds || 120;
		},
		estimateConfidence() {
			return this.$resources.estimate?.data?.confidence || 'low';
		},
		statusBadgeTheme() {
			const map = { Success: 'green', Failure: 'red', Running: 'blue', Preparing: 'blue', Pending: 'orange', Scheduled: 'orange', Draft: 'gray' };
			return map[this.deploy?.status] || 'gray';
		},
		currentRunningStep() {
			if (!this.deploy?.build_steps) return null;
			const running = this.deploy.build_steps.find(s => s.status === 'Running');
			return running ? `${running.stage} / ${running.step}` : null;
		},
		durationComparison() {
			const est = this.$resources.estimate?.data;
			if (!est || !this.deploy?.build_duration || est.sample_size < 1) return null;
			const avg = est.estimated_seconds / 1.15; // Remove 15% buffer to get raw average
			const actual = this.deploy.build_duration;
			const diff = Math.round(((actual - avg) / avg) * 100);
			if (Math.abs(diff) < 5) return null;
			return diff < 0 ? `↓ ${Math.abs(diff)}% faster` : `↑ ${diff}% slower`;
		},
		groupedSteps() {
			if (!this.deploy?.build_steps) return [];
			const groups = [];
			let current = null;
			for (const step of this.deploy.build_steps) {
				if (!current || current.stage !== step.stage) {
					current = { stage: step.stage, steps: [], status: 'Pending', completed: 0, total: 0, duration: null };
					groups.push(current);
				}
				current.steps.push(step);
				current.total++;
				if (step.status === 'Success') current.completed++;
				if (step.status === 'Running') { current.status = 'Running'; this.stageOpenState[step.stage] ??= true; }
				if (step.status === 'Failure') { current.status = 'Failure'; this.stageOpenState[step.stage] ??= true; }
			}
			for (const g of groups) {
				if (g.completed === g.total && g.total > 0) g.status = 'Success';
				const durations = g.steps.filter(s => s.duration && !isNaN(parseFloat(s.duration))).map(s => parseFloat(s.duration));
				if (durations.length) g.duration = `${Math.round(durations.reduce((a, b) => a + b, 0))}s`;
				g.hasRunning = g.steps.some(s => s.status === 'Running');
			}
			return groups;
		},
		progressPercent() {
			if (!this.isBuilding) return 100;
			const pct = Math.min((this.elapsedSeconds / this.estimatedSeconds) * 100, 98);
			return Math.round(pct);
		},
		progressColor() {
			if (this.progressPercent > 90) return 'bg-yellow-500';
			return 'bg-blue-500';
		},
		elapsedFormatted() {
			return this.formatDuration(this.elapsedSeconds);
		},
		estimateFormatted() {
			return this.formatDuration(this.estimatedSeconds);
		},
		object() {
			return getObject(this.objectType);
		},
		error() {
			return this.$resources.errors?.data?.[0] ?? null;
		},
		warningItems() {
			return (this.$resources.warnings?.data ?? []).slice(0, 5);
		},
		alertMessage() {
			if (!this.deploy) {
				return null;
			}

			if (this.deploy.retry_count > 0 && this.deploy.status === 'Scheduled') {
				return 'Previous deploy failed, re-deploy will be attempted soon';
			}
			return null;
		},
		dropdownOptions() {
			return [
				{
					label: 'View in Desk',
					icon: 'external-link',
					condition: () => this.$team?.doc?.is_desk_user,
					onClick: () => {
						window.open(
							`${window.location.protocol}//${window.location.host}/app/deploy-candidate-build/${this.id}`,
							'_blank',
						);
					},
				},
				{
					label: 'View App Versions',
					icon: 'package',
					onClick: () => {
						this.appVersions();
					},
				},
			].filter((option) => option.condition?.() ?? true);
		},
	},
	methods: {
		formatDuration(secs) {
			const m = Math.floor(secs / 60), s = secs % 60;
			return m > 0 ? `${m}m ${s}s` : `${s}s`;
		},
		startTimer() {
			if (this.elapsedTimer) return;
			const startMs = this.deploy?.build_start ? new Date(this.deploy.build_start).getTime() : Date.now();
			this.elapsedSeconds = Math.max(0, Math.floor((Date.now() - startMs) / 1000));
			this.elapsedTimer = setInterval(() => {
				this.elapsedSeconds = Math.max(0, Math.floor((Date.now() - startMs) / 1000));
			}, 1000);
			if (this.deploy?.group) this.$resources.estimate.submit({ group: this.deploy.group });
		},
		stopTimer() {
			if (this.elapsedTimer) { clearInterval(this.elapsedTimer); this.elapsedTimer = null; }
		},
		startAutoRefresh() {
			if (this.autoRefreshTimer) return;
			this.autoRefreshTimer = setInterval(() => { this.$resources.deploy.reload(); }, 5000);
		},
		stopAutoRefresh() {
			if (this.autoRefreshTimer) { clearInterval(this.autoRefreshTimer); this.autoRefreshTimer = null; }
		},
		transformDeploy(deploy) {
			if (!deploy || !deploy.build_steps) {
				return deploy;
			}
			for (let step of deploy.build_steps) {
				if (step.status === 'Running') {
					step.isOpen = true;
				} else {
					step.isOpen = this.$resources.deploy?.doc?.build_steps?.find(
						(s) => s.name === step.name,
					)?.isOpen;
				}
				step.title = `${step.stage} - ${step.step}`;
				step.output =
					step.command || step.output
						? `${step.command || ''}\n${step.output || ''}`.trim()
						: '';
				step.duration = ['Success', 'Failure'].includes(step.status)
					? step.cached
						? 'Cached'
						: `${step.duration}s`
					: null;
			}
			return deploy;
		},
		retryDeploy() {
			confirmDialog({
				title: 'Retry Deploy',
				message: `This will create a <strong>new build</strong> with the same app versions and start it immediately.<br><br>
				<div class="text-bg-base bg-gray-100 p-2 rounded-md">
				The current failed build will remain in history for reference.
				</div>`,
				primaryAction: {
					label: 'Retry Deploy',
					variant: 'solid',
					onClick: ({ hide }) => {
						this.retrying = true;
						createResource({
							url: 'press.press.doctype.deploy_candidate_build.deploy_candidate_build.redeploy',
							params: { dn: this.deploy.name },
						})
							.fetch()
							.then((result) => {
								hide();
								this.retrying = false;
								toast.success('New deploy triggered');
								if (result?.name) {
									this.$router.push({
										name: 'Deploy Candidate',
										params: { id: result.name },
										query: { previous: this.deploy.name },
									});
								}
							})
							.catch(() => {
								hide();
								this.retrying = false;
								toast.error('Failed to retry deploy');
							});
					},
				},
			});
		},
		forceRetry() {
			confirmDialog({
				title: 'Force Retry — Stop & Redeploy',
				message: `This will <strong>stop the current stuck build</strong> and immediately start a <strong>new one</strong>.<br><br>
				<div class="text-bg-base bg-red-50 p-2 rounded-md border border-red-200">
				Use this only if the build appears stuck (no progress for 10+ minutes).
				</div>`,
				primaryAction: {
					label: 'Force Retry',
					variant: 'solid',
					theme: 'red',
					onClick: ({ hide }) => {
						this.retrying = true;
						createResource({
							url: 'press.press.doctype.deploy_candidate_build.deploy_candidate_build.fail_and_redeploy',
							params: { dn: this.deploy.name },
						})
							.fetch()
							.then((result) => {
								hide();
								this.retrying = false;
								toast.success('Build stopped and new deploy triggered');
								if (result?.name) {
									this.$router.push({
										name: 'Deploy Candidate',
										params: { id: result.name },
										query: { previous: this.deploy.name },
									});
								}
							})
							.catch(() => {
								hide();
								this.retrying = false;
								toast.error('Failed to force retry');
							});
					},
				},
			});
		},
		stopBuild() {
			const deploy = this.deploy;
			const isRunning = deploy.status === 'Running';

			confirmDialog({
				title: isRunning ? 'Stop Running Build' : 'Cancel Pending Build',
				message: isRunning
					? `Are you sure you want to stop this running build?<br><br>
					<div class="text-bg-base bg-gray-100 p-2 rounded-md">
					This will <strong>stop the current build immediately</strong>.
					All progress made so far will be <strong>discarded</strong>, and the next triggered build will start from scratch.
					<br><br>
					Use this option if a build is stuck, taking unusually long, or is expected to fail.
					</div>`
					: `Are you sure you want to cancel this pending build?<br><br>
					<div class="text-bg-base bg-gray-100 p-2 rounded-md">
					This will <strong>mark the build as failed</strong> and allow you to trigger a new deploy.
					</div>`,
				primaryAction: {
					label: isRunning ? 'Stop Build' : 'Cancel Build',
					variant: 'solid',
					theme: 'red',
					onClick({ hide }) {
						createResource({
							url: 'press.press.doctype.deploy_candidate_build.deploy_candidate_build.stop_and_fail',
							params: { dn: deploy.name },
						})
							.fetch()
							.then(() => {
								hide();
								toast.success('Build cancelled');
							})
							.catch(() => {
								hide();
								toast.error(
									'Unable to cancel build — please wait for the status to update',
								);
							});
					},
				},
			});
		},

		appVersions() {
			const deploy = this.deploy;
			renderDialog(
				h(AppVersionsDialog, {
					dc_name: deploy.name,
					group: deploy.group,
					status: deploy.status,
				}),
			);
		},
	},
};
</script>
