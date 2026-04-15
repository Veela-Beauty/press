<template>
	<Dialog
		v-model="showRestoreDialog"
		:disableOutsideClickToClose="true"
		:options="{ title: 'Restore' }"
	>
		<template v-slot:body-content>
			<div class="space-y-4">
				<p class="text-base">Restore your site using a previous backup.</p>
				<div
					class="flex items-center rounded border border-gray-200 bg-gray-100 p-4 text-sm text-gray-600"
				>
					<lucide-alert-triangle class="mr-4 inline-block h-6 w-6" />
					<div>
						This will overwrite all <b>data</b> &amp; <b>apps</b> in your site with
						those from the backup
					</div>
				</div>

				<!-- Upload Progress Panel (shown during upload) -->
				<div
					v-if="uploadingFiles"
					class="rounded-lg border border-blue-200 bg-blue-50 p-4 space-y-3"
				>
					<div class="space-y-1.5">
						<div class="flex items-center justify-between text-sm">
							<span class="font-medium text-gray-800">{{ uploadPhaseLabel }}</span>
							<span class="text-gray-600 tabular-nums">{{ overallProgress }}%</span>
						</div>
						<div class="h-3 w-full overflow-hidden rounded-full bg-gray-200">
							<div
								class="h-full rounded-full transition-all duration-300 ease-out"
								:class="overallProgress >= 100 ? 'bg-green-500' : 'bg-blue-500'"
								:style="{ width: `${overallProgress}%` }"
							/>
						</div>
						<div class="flex items-center justify-between text-xs text-gray-500">
							<span>{{ uploadedSizeLabel }} / {{ totalSizeLabel }}</span>
							<span v-if="uploadSpeed">{{ uploadSpeed }} &middot; {{ etaLabel }}</span>
						</div>
					</div>
					<div class="space-y-1.5 border-t border-blue-100 pt-2">
						<div v-for="fs in fileStatuses" :key="fs.type" class="flex items-center justify-between text-xs">
							<div class="flex items-center gap-1.5">
								<span v-if="fs.status === 'done'" class="text-green-600">&#10003;</span>
								<span v-else-if="fs.status === 'uploading'" class="text-blue-600 animate-pulse">&#9679;</span>
								<span v-else-if="fs.status === 'connecting'" class="text-amber-500 animate-pulse">&#9679;</span>
								<span v-else-if="fs.status === 'error'" class="text-red-600">&#10007;</span>
								<span v-else class="text-gray-400">&#9675;</span>
								<span :class="fs.status === 'uploading' ? 'font-medium text-gray-800' : 'text-gray-600'">{{ fs.label }}</span>
							</div>
							<span class="tabular-nums text-gray-500">
								<template v-if="fs.status === 'uploading'">{{ fs.progress }}% &middot; {{ formatBytes(fs.uploaded) }}</template>
								<template v-else-if="fs.status === 'done'">{{ formatBytes(fs.total) }} &#10003;</template>
								<template v-else-if="fs.status === 'error'"><span class="text-red-500">{{ fs.errorMessage || 'Failed' }}</span></template>
								<template v-else-if="fs.status === 'connecting'">Connecting...</template>
								<template v-else-if="fs.status === 'waiting'">{{ formatBytes(fs.fileSize) }}</template>
							</span>
						</div>
					</div>
				</div>

				<!-- ─── ANALYZING SPINNER ─────────────────────────────── -->
				<div v-if="analyzing" class="rounded-lg border border-indigo-200 bg-indigo-50 p-4 flex items-center gap-3">
					<svg class="h-5 w-5 animate-spin text-indigo-500 shrink-0" viewBox="0 0 24 24" fill="none">
						<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
						<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
					</svg>
					<div>
						<p class="text-sm font-medium text-indigo-800">Scanning backup...</p>
						<p class="text-xs text-indigo-600 mt-0.5">Checking which tables can be safely skipped to speed up restore</p>
					</div>
				</div>

				<!-- ─── ANALYSIS RESULTS ──────────────────────────────── -->
				<div v-if="analysisResult" class="rounded-lg border border-gray-200 bg-gray-50 p-4 space-y-3">
					<!-- Summary header -->
					<div class="flex items-start justify-between">
						<div>
							<p class="text-sm font-semibold text-gray-800">Backup Analysis</p>
							<p class="text-xs text-gray-500 mt-0.5">
								{{ analysisResult.total_row_count.toLocaleString() }} total rows across {{ Object.keys(analysisResult.tables).length }} tables
							</p>
						</div>
						<div v-if="selectedNoiseTables.length" class="text-right">
							<p class="text-xs font-medium text-green-700">
								{{ selectedNoiseRowCount.toLocaleString() }} rows skipped
							</p>
							<p class="text-xs text-green-600">~{{ estimatedTimeSaved }} faster</p>
						</div>
					</div>

					<!-- Noise tables list -->
					<div v-if="analysisResult.noise_tables.length" class="space-y-1">
						<p class="text-xs font-medium text-gray-600 uppercase tracking-wide">
							Log &amp; Activity Tables
							<span class="ml-1 text-gray-400 font-normal normal-case">(safe to skip — regenerated automatically)</span>
						</p>
						<div class="rounded border border-gray-200 bg-white divide-y divide-gray-100">
							<label
								v-for="tableName in sortedNoiseTables"
								:key="tableName"
								class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-gray-50 gap-3"
							>
								<div class="flex items-center gap-2 min-w-0">
									<input
										type="checkbox"
										class="h-4 w-4 shrink-0 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
										:value="tableName"
										v-model="selectedNoiseTables"
									/>
									<span class="text-xs text-gray-700 truncate">{{ tableName }}</span>
								</div>
								<span class="text-xs text-gray-400 tabular-nums shrink-0">
									{{ analysisResult.tables[tableName].rows.toLocaleString() }} rows
								</span>
							</label>
						</div>
						<div class="flex items-center justify-between pt-1">
							<button
								class="text-xs text-blue-600 hover:underline"
								type="button"
								@click="toggleAllNoise"
							>
								{{ selectedNoiseTables.length === analysisResult.noise_tables.length ? 'Deselect all' : 'Select all' }}
							</button>
							<span class="text-xs text-gray-400">
								{{ selectedNoiseTables.length }}/{{ analysisResult.noise_tables.length }} selected to skip
							</span>
						</div>
					</div>

					<div v-else class="text-xs text-gray-500 italic">
						No large noise tables found — restore will proceed normally.
					</div>

					<!-- Custom data confirmation note -->
					<div class="rounded bg-amber-50 border border-amber-200 p-2.5 text-xs text-amber-800 flex gap-2">
						<lucide-shield-check class="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
						<span>
							Custom fields, scripts, workflows, and all business data are
							<strong>always restored</strong> — only the selected log tables are skipped.
						</span>
					</div>
				</div>

				<!-- File uploader (hidden once analysis shown) -->
				<BackupFilesUploader
					v-show="!analysisResult"
					ref="backupFilesUploader"
					v-model:backupFiles="selectedFiles"
					:site="this.site"
					:disableUploadButton="this.uploadingFiles"
					:onError="(errorMessage) => { this.errorMessageFromUploader = errorMessage; this.uploadingFiles = false; this.stopProgressTracking(); }"
					@uploadComplete="(files) => afterUpload(files)"
					@abortUpload="(e) => failureHandler(e)"
				/>
			</div>

			<div class="mt-3">
				<input
					id="skip-failing"
					type="checkbox"
					class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
					v-model="skipFailingPatches"
				/>
				<label for="skip-failing" class="ml-2 text-sm text-gray-900">
					Skip failing patches (if any patch fails)
				</label>
			</div>
			<ErrorMessage
				class="mt-2"
				:message="$resources.restoreBackup.error || errorMessageFromUploader"
			/>
		</template>

		<template v-slot:actions>
			<!-- While uploading -->
			<Button
				v-if="uploadingFiles || (!analysisResult && !analyzing)"
				class="w-full"
				variant="solid"
				theme="red"
				:loading="$resources.restoreBackup.loading"
				:disabled="uploadingFiles"
				@click="() => startUploadFiles()"
			>
				<template v-if="uploadingFiles">
					<span class="flex items-center gap-2">
						<svg class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
							<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
							<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
						</svg>
						Uploading {{ overallProgress }}%
					</span>
				</template>
				<template v-else>Upload &amp; Restore</template>
			</Button>

			<!-- While analyzing -->
			<Button v-else-if="analyzing" class="w-full" variant="solid" :disabled="true">
				<span class="flex items-center gap-2">
					<svg class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
						<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
						<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
					</svg>
					Analyzing backup...
				</span>
			</Button>

			<!-- After analysis — confirm restore -->
			<Button
				v-else-if="analysisResult"
				class="w-full"
				variant="solid"
				theme="red"
				:loading="$resources.restoreBackup.loading"
				@click="confirmRestore"
			>
				<template v-if="$resources.restoreBackup.loading">Triggering Restore...</template>
				<template v-else>
					Restore
					<span v-if="selectedNoiseTables.length" class="ml-1 opacity-75 text-xs">
						(skipping {{ selectedNoiseTables.length }} log tables)
					</span>
				</template>
			</Button>
		</template>
	</Dialog>
</template>

<script>
import { Button } from 'frappe-ui';
import BackupFilesUploader from './BackupFilesUploader.vue';
import { toast } from 'vue-sonner';

export default {
	name: 'SiteDatabaseRestoreDialog',
	props: {
		site: { type: String, required: true },
	},
	components: { BackupFilesUploader, Button },
	data() {
		return {
			showRestoreDialog: true,
			selectedFiles: { database: null, public: null, private: null, config: null },
			skipFailingPatches: false,
			errorMessageFromUploader: '',
			uploadingFiles: false,
			// Analysis state
			analyzing: false,
			analysisJobName: null,
			analysisResult: null,
			selectedNoiseTables: [],
			analysisPollTimer: null,
			// Upload progress
			uploadPhase: '',
			progressTimer: null,
			uploadStartTime: null,
			lastUploadedBytes: 0,
			lastSpeedCheckTime: null,
			currentSpeed: 0,
			fileStatuses: [],
		};
	},
	computed: {
		sortedNoiseTables() {
			if (!this.analysisResult) return [];
			return [...this.analysisResult.noise_tables].sort((a, b) => {
				return (
					this.analysisResult.tables[b].rows -
					this.analysisResult.tables[a].rows
				);
			});
		},
		selectedNoiseRowCount() {
			if (!this.analysisResult) return 0;
			return this.selectedNoiseTables.reduce((sum, t) => {
				return sum + (this.analysisResult.tables[t]?.rows || 0);
			}, 0);
		},
		estimatedTimeSaved() {
			// Rough estimate: ~300k rows/min for MariaDB import on this server
			const rowsPerMin = 300000;
			const mins = Math.round(this.selectedNoiseRowCount / rowsPerMin);
			if (mins < 1) return '<1 min';
			if (mins < 60) return `~${mins} min`;
			const h = Math.floor(mins / 60);
			const m = mins % 60;
			return m > 0 ? `~${h}h ${m}m` : `~${h}h`;
		},
		overallProgress() {
			if (!this.fileStatuses.length) return 0;
			const active = this.fileStatuses.filter((f) => f.fileSize > 0);
			if (!active.length) return 0;
			const totalBytes = active.reduce((sum, f) => sum + f.total, 0);
			const uploadedBytes = active.reduce((sum, f) => sum + f.uploaded, 0);
			if (!totalBytes) return 0;
			return Math.min(Math.floor((uploadedBytes / totalBytes) * 100), 100);
		},
		totalUploadedBytes() {
			return this.fileStatuses.reduce((sum, f) => sum + f.uploaded, 0);
		},
		totalBytes() {
			return this.fileStatuses.filter((f) => f.fileSize > 0).reduce((sum, f) => sum + f.total, 0);
		},
		uploadedSizeLabel() { return this.formatBytes(this.totalUploadedBytes); },
		totalSizeLabel() { return this.formatBytes(this.totalBytes); },
		uploadSpeed() {
			if (!this.currentSpeed) return '';
			return `${this.formatBytes(this.currentSpeed)}/s`;
		},
		etaLabel() {
			if (!this.currentSpeed) return '';
			const remaining = this.totalBytes - this.totalUploadedBytes;
			if (remaining <= 0) return 'Complete';
			const seconds = Math.ceil(remaining / this.currentSpeed);
			if (seconds < 60) return `~${seconds}s left`;
			if (seconds < 3600) return `~${Math.ceil(seconds / 60)}m left`;
			const h = Math.floor(seconds / 3600);
			const m = Math.ceil((seconds % 3600) / 60);
			return `~${h}h ${m}m left`;
		},
		uploadPhaseLabel() {
			if (this.uploadPhase === 'checking') return 'Checking server disk space...';
			const uploading = this.fileStatuses.filter((f) => f.status === 'uploading');
			if (uploading.length) return `Uploading ${uploading[0].label}...`;
			const connecting = this.fileStatuses.filter((f) => f.status === 'connecting');
			if (connecting.length) return `Connecting to storage for ${connecting[0].label}...`;
			const allDone = this.fileStatuses.every((f) => f.status === 'done');
			if (allDone && this.fileStatuses.length) return 'Upload complete — scanning backup...';
			return 'Preparing upload...';
		},
	},
	methods: {
		// ─── Upload flow ────────────────────────────────────────────
		async startUploadFiles() {
			this.errorMessageFromUploader = '';
			this.uploadingFiles = true;
			this.uploadPhase = 'checking';
			this.uploadStartTime = Date.now();
			this.lastSpeedCheckTime = Date.now();
			this.lastUploadedBytes = 0;
			this.currentSpeed = 0;
			this.buildFileStatuses();
			this.startProgressTracking();
			const success = await this.$refs.backupFilesUploader.uploadFiles();
			if (!success) {
				this.uploadingFiles = false;
				this.stopProgressTracking();
				return;
			}
			this.uploadPhase = 'uploading';
			if (this.$refs.backupFilesUploader.isAllFilesUploaded()) {
				this.afterUpload(this.selectedFiles);
			}
		},
		startProgressTracking() {
			this.progressTimer = setInterval(() => this.updateProgress(), 250);
		},
		stopProgressTracking() {
			if (this.progressTimer) { clearInterval(this.progressTimer); this.progressTimer = null; }
		},
		buildFileStatuses() {
			const uploader = this.$refs.backupFilesUploader;
			if (!uploader) return;
			const labels = { database: 'Database Backup', public: 'Public Files', private: 'Private Files', config: 'Site Config' };
			this.fileStatuses = ['database', 'public', 'private', 'config']
				.filter((type) => uploader.files?.find((f) => f.type === type)?.file)
				.map((type) => {
					const fileData = uploader.files.find((f) => f.type === type);
					return { type, label: labels[type], fileSize: fileData?.file?.size || 0, uploaded: 0, total: fileData?.file?.size || 0, progress: 0, status: 'waiting' };
				});
		},
		updateProgress() {
			const uploader = this.$refs.backupFilesUploader;
			if (!uploader) return;
			for (const fs of this.fileStatuses) {
				const ref = uploader.$refs?.[fs.type];
				const fu = ref?.[0];
				if (!fu) continue;
				if (fu.finishedUploading && !fu.error) { fs.status = 'done'; fs.uploaded = fs.total; fs.progress = 100; }
				else if (fu.error) { fs.status = 'error'; fs.errorMessage = typeof fu.error === 'string' ? fu.error : 'Upload failed'; }
				else if (fu.uploading) { fs.status = 'uploading'; fs.uploaded = fu.uploaded || 0; fs.total = fu.total || fs.fileSize; fs.progress = fu.progress || 0; }
				else if (fu.uploader && this.uploadPhase === 'uploading') { fs.status = 'connecting'; }
			}
			const hasError = this.fileStatuses.some((f) => f.status === 'error');
			if (hasError) {
				this.stopProgressTracking();
				this.uploadingFiles = false;
				const errorFile = this.fileStatuses.find((f) => f.status === 'error');
				this.errorMessageFromUploader = `Upload failed for ${errorFile?.label || 'file'}: ${errorFile?.errorMessage || 'Unknown error'}.`;
				return;
			}
			const secondsSinceStart = (Date.now() - this.uploadStartTime) / 1000;
			const hasAnyProgress = this.fileStatuses.some((f) => f.status === 'uploading' || f.status === 'done');
			if (!hasAnyProgress && secondsSinceStart > 120) {
				this.stopProgressTracking(); this.uploadingFiles = false;
				this.errorMessageFromUploader = 'Upload stalled — the server is not responding.';
				return;
			}
			const now = Date.now();
			const elapsed = (now - this.lastSpeedCheckTime) / 1000;
			if (elapsed >= 2) {
				const bytesDelta = this.totalUploadedBytes - this.lastUploadedBytes;
				this.currentSpeed = Math.max(0, bytesDelta / elapsed);
				this.lastUploadedBytes = this.totalUploadedBytes;
				this.lastSpeedCheckTime = now;
			}
		},

		// ─── After upload: trigger analysis ─────────────────────────
		async afterUpload(files) {
			this.stopProgressTracking();
			this.uploadingFiles = false;
			if (files) this.selectedFiles = files;

			// Only analyze if there's a database file
			if (!this.selectedFiles.database) {
				this.startRestoreRequest([]);
				return;
			}

			this.analyzing = true;
			try {
				const result = await this.$resources.analyzeBackup.submit({
					name: this.site,
					files: this.selectedFiles,
				});
				if (result) this.analysisJobName = result;
				this.startAnalysisPoll();
			} catch (e) {
				// If analysis fails, fall back to normal restore
				this.analyzing = false;
				this.startRestoreRequest([]);
			}
		},
		startAnalysisPoll() {
			this.analysisPollTimer = setInterval(async () => {
				try {
					const result = await this.$resources.getAnalyzeResult.submit({
						name: this.site,
						job_name: this.analysisJobName,
					});
					if (result && result.status === 'Success' && result.data) {
						clearInterval(this.analysisPollTimer);
						this.analyzing = false;
						this.analysisResult = result.data;
						// Pre-select all noise tables
						this.selectedNoiseTables = [...(result.data.noise_tables || [])];
					} else if (result && result.status === 'Failure') {
						clearInterval(this.analysisPollTimer);
						this.analyzing = false;
						// Fall back to normal restore
						this.startRestoreRequest([]);
					}
				} catch {
					clearInterval(this.analysisPollTimer);
					this.analyzing = false;
					this.startRestoreRequest([]);
				}
			}, 3000);
		},
		toggleAllNoise() {
			if (!this.analysisResult) return;
			if (this.selectedNoiseTables.length === this.analysisResult.noise_tables.length) {
				this.selectedNoiseTables = [];
			} else {
				this.selectedNoiseTables = [...this.analysisResult.noise_tables];
			}
		},
		confirmRestore() {
			this.startRestoreRequest(this.selectedNoiseTables);
		},
		startRestoreRequest(skipTables) {
			this.$resources.restoreBackup.submit({
				name: this.site,
				files: this.selectedFiles,
				skip_failing_patches: this.skipFailingPatches,
				skip_tables: skipTables,
			});
		},
		failureHandler(e) {
			if (e) return;
			this.stopProgressTracking();
			this.uploadingFiles = false;
			this.errorMessageFromUploader = 'Failed to upload files. Please try again.';
			this.showRestoreDialog = false;
			toast.error(this.errorMessageFromUploader);
		},
		formatBytes(bytes) {
			if (!bytes || bytes === 0) return '0 B';
			const k = 1024;
			const sizes = ['B', 'KB', 'MB', 'GB'];
			const i = Math.floor(Math.log(bytes) / Math.log(k));
			const val = bytes / Math.pow(k, i);
			return `${val < 10 ? val.toFixed(1) : Math.round(val)} ${sizes[i]}`;
		},
	},
	resources: {
		analyzeBackup() {
			return {
				url: 'press.api.site.analyze_restore_backup',
				onError(e) {
					console.warn('Backup analysis failed, proceeding with full restore:', e);
				},
			};
		},
		getAnalyzeResult() {
			return { url: 'press.api.site.get_analyze_result' };
		},
		restoreBackup() {
			return {
				url: 'press.api.site.restore',
				onSuccess() {
					this.selectedFiles = {};
					this.$router.push({ name: 'Site Jobs', params: { name: this.site } });
					this.showRestoreDialog = false;
					this.$toast.success('Restoration triggered successfully.');
				},
			};
		},
	},
	beforeUnmount() {
		this.stopProgressTracking();
		if (this.analysisPollTimer) clearInterval(this.analysisPollTimer);
	},
};
</script>
