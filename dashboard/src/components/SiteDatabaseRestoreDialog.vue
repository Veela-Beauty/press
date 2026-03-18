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
						This will overwrite all <b>data</b> & <b>apps</b> in your site with
						those from the backup
					</div>
				</div>

				<!-- Upload Progress Panel (shown during upload) -->
				<div
					v-if="uploadingFiles"
					class="rounded-lg border border-blue-200 bg-blue-50 p-4 space-y-3"
				>
					<!-- Overall progress bar -->
					<div class="space-y-1.5">
						<div class="flex items-center justify-between text-sm">
							<span class="font-medium text-gray-800">
								{{ uploadPhaseLabel }}
							</span>
							<span class="text-gray-600 tabular-nums">
								{{ overallProgress }}%
							</span>
						</div>
						<div class="h-3 w-full overflow-hidden rounded-full bg-gray-200">
							<div
								class="h-full rounded-full transition-all duration-300 ease-out"
								:class="overallProgress >= 100 ? 'bg-green-500' : 'bg-blue-500'"
								:style="{ width: `${overallProgress}%` }"
							/>
						</div>
						<!-- Speed + ETA + Size -->
						<div class="flex items-center justify-between text-xs text-gray-500">
							<span>{{ uploadedSizeLabel }} / {{ totalSizeLabel }}</span>
							<span v-if="uploadSpeed">
								{{ uploadSpeed }} &middot; {{ etaLabel }}
							</span>
						</div>
					</div>

					<!-- Per-file status -->
					<div class="space-y-1.5 border-t border-blue-100 pt-2">
						<div
							v-for="fs in fileStatuses"
							:key="fs.type"
							class="flex items-center justify-between text-xs"
						>
							<div class="flex items-center gap-1.5">
								<!-- Status icon -->
								<span v-if="fs.status === 'done'" class="text-green-600">&#10003;</span>
								<span v-else-if="fs.status === 'uploading'" class="text-blue-600 animate-pulse">&#9679;</span>
								<span v-else-if="fs.status === 'connecting'" class="text-amber-500 animate-pulse">&#9679;</span>
								<span v-else-if="fs.status === 'error'" class="text-red-600">&#10007;</span>
								<span v-else class="text-gray-400">&#9675;</span>
								<span :class="fs.status === 'uploading' ? 'font-medium text-gray-800' : 'text-gray-600'">
									{{ fs.label }}
								</span>
							</div>
							<span class="tabular-nums text-gray-500">
								<template v-if="fs.status === 'uploading'">
									{{ fs.progress }}% &middot; {{ formatBytes(fs.uploaded) }}
								</template>
								<template v-else-if="fs.status === 'done'">
									{{ formatBytes(fs.total) }} &#10003;
								</template>
								<template v-else-if="fs.status === 'error'">
									<span class="text-red-500">{{ fs.errorMessage || 'Failed' }}</span>
								</template>
								<template v-else-if="fs.status === 'connecting'">
									Connecting...
								</template>
								<template v-else-if="fs.status === 'waiting'">
									{{ formatBytes(fs.fileSize) }}
								</template>
							</span>
						</div>
					</div>
				</div>

				<BackupFilesUploader
					ref="backupFilesUploader"
					v-model:backupFiles="selectedFiles"
					:site="this.site"
					:disableUploadButton="this.uploadingFiles"
					:onError="
						(errorMessage) => {
							this.errorMessageFromUploader = errorMessage;
							this.uploadingFiles = false;
							this.stopProgressTracking();
						}
					"
					@uploadComplete="(files) => startRestore(files)"
					@abortUpload="(e) => failureHandler(e)"
				/>
			</div>
			<div class="mt-3">
				<!-- Skip Failing Checkbox -->
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
			<Button
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
							<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
							<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
						</svg>
						Uploading {{ overallProgress }}%
					</span>
				</template>
				<template v-else-if="$resources.restoreBackup.loading">
					Triggering Restore...
				</template>
				<template v-else>
					Upload &amp; Restore
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
		site: {
			type: String,
			required: true,
		},
	},
	components: {
		BackupFilesUploader,
		Button,
	},
	data() {
		return {
			showRestoreDialog: true,
			selectedFiles: {
				database: null,
				public: null,
				private: null,
				config: null,
			},
			skipFailingPatches: false,
			errorMessageFromUploader: '',
			uploadingFiles: false,
			// Progress tracking
			uploadPhase: '', // 'checking' | 'uploading' | ''
			progressTimer: null,
			uploadStartTime: null,
			lastUploadedBytes: 0,
			lastSpeedCheckTime: null,
			currentSpeed: 0,
			fileStatuses: [],
		};
	},
	computed: {
		filesUploaded() {
			return this.selectedFiles.database;
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
			return this.fileStatuses
				.filter((f) => f.fileSize > 0)
				.reduce((sum, f) => sum + f.total, 0);
		},
		uploadedSizeLabel() {
			return this.formatBytes(this.totalUploadedBytes);
		},
		totalSizeLabel() {
			return this.formatBytes(this.totalBytes);
		},
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
			const uploading = this.fileStatuses.filter(
				(f) => f.status === 'uploading',
			);
			if (uploading.length) return `Uploading ${uploading[0].label}...`;
			const connecting = this.fileStatuses.filter(
				(f) => f.status === 'connecting',
			);
			if (connecting.length) return `Connecting to storage for ${connecting[0].label}...`;
			const allDone = this.fileStatuses.every(
				(f) => f.status === 'done',
			);
			if (allDone && this.fileStatuses.length) return 'Upload complete — starting restore...';
			return 'Preparing upload...';
		},
	},
	methods: {
		async startUploadFiles() {
			this.errorMessageFromUploader = '';
			this.uploadingFiles = true;
			this.uploadPhase = 'checking';
			this.uploadStartTime = Date.now();
			this.lastSpeedCheckTime = Date.now();
			this.lastUploadedBytes = 0;
			this.currentSpeed = 0;

			// Build file list immediately so UI shows what will be uploaded
			this.buildFileStatuses();

			// Start polling immediately — shows phases even before XHR starts
			this.startProgressTracking();

			const success = await this.$refs.backupFilesUploader.uploadFiles();
			if (!success) {
				this.uploadingFiles = false;
				this.stopProgressTracking();
				return;
			}

			// Mark phase as uploading (presigned URL + XHR now in progress)
			this.uploadPhase = 'uploading';

			// Check if already done (small files)
			if (this.$refs.backupFilesUploader.isAllFilesUploaded()) {
				this.startRestore(this.selectedFiles);
			}
		},
		startProgressTracking() {
			this.progressTimer = setInterval(() => {
				this.updateProgress();
			}, 250);
		},
		stopProgressTracking() {
			if (this.progressTimer) {
				clearInterval(this.progressTimer);
				this.progressTimer = null;
			}
		},
		buildFileStatuses() {
			const uploader = this.$refs.backupFilesUploader;
			if (!uploader) return;

			const types = ['database', 'public', 'private', 'config'];
			const labels = {
				database: 'Database Backup',
				public: 'Public Files',
				private: 'Private Files',
				config: 'Site Config',
			};

			this.fileStatuses = types
				.filter((type) => {
					const fileData = uploader.files?.find((f) => f.type === type);
					return fileData?.file;
				})
				.map((type) => {
					const fileData = uploader.files.find((f) => f.type === type);
					return {
						type,
						label: labels[type],
						fileSize: fileData?.file?.size || 0,
						uploaded: 0,
						total: fileData?.file?.size || 0,
						progress: 0,
						status: 'waiting',
					};
				});
		},
		updateProgress() {
			const uploader = this.$refs.backupFilesUploader;
			if (!uploader) return;

			for (const fs of this.fileStatuses) {
				const ref = uploader.$refs?.[fs.type];
				const fu = ref?.[0]; // FileUploader component instance
				if (!fu) continue;

				if (fu.finishedUploading && !fu.error) {
					fs.status = 'done';
					fs.uploaded = fs.total;
					fs.progress = 100;
				} else if (fu.error) {
					fs.status = 'error';
					fs.errorMessage = typeof fu.error === 'string' ? fu.error : 'Upload failed';
				} else if (fu.uploading) {
					fs.status = 'uploading';
					fs.uploaded = fu.uploaded || 0;
					fs.total = fu.total || fs.fileSize;
					fs.progress = fu.progress || 0;
				} else if (fu.uploader && this.uploadPhase === 'uploading') {
					// uploadFile() was called, uploader created,
					// but XHR hasn't started yet (fetching presigned URL)
					fs.status = 'connecting';
				}
			}

			// Detect stalled upload — if connecting/0% for too long
			const hasAnyProgress = this.fileStatuses.some(
				(f) => f.status === 'uploading' || f.status === 'done',
			);
			const hasError = this.fileStatuses.some((f) => f.status === 'error');
			if (hasError) {
				// An error was detected — stop tracking and show it
				this.stopProgressTracking();
				this.uploadingFiles = false;
				const errorFile = this.fileStatuses.find((f) => f.status === 'error');
				this.errorMessageFromUploader =
					`Upload failed for ${errorFile?.label || 'file'}: ${errorFile?.errorMessage || 'Unknown error'}. Please try again or check storage configuration.`;
				return;
			}
			const secondsSinceStart = (Date.now() - this.uploadStartTime) / 1000;
			if (!hasAnyProgress && secondsSinceStart > 120) {
				this.stopProgressTracking();
				this.uploadingFiles = false;
				this.errorMessageFromUploader =
					'Upload stalled — the server is not responding. Please try again.';
				return;
			}

			// Calculate speed (smoothed over 2-second window)
			const now = Date.now();
			const elapsed = (now - this.lastSpeedCheckTime) / 1000;
			if (elapsed >= 2) {
				const bytesDelta = this.totalUploadedBytes - this.lastUploadedBytes;
				this.currentSpeed = Math.max(0, bytesDelta / elapsed);
				this.lastUploadedBytes = this.totalUploadedBytes;
				this.lastSpeedCheckTime = now;
			}
		},
		startRestore(files) {
			this.stopProgressTracking();
			this.uploadingFiles = false;
			if (files) {
				this.selectedFiles = files;
			}
			this.$resources.restoreBackup.submit({
				name: this.site,
				files: this.selectedFiles,
				skip_failing_patches: this.skipFailingPatches,
			});
		},
		failureHandler(e) {
			if (e) return;
			this.stopProgressTracking();
			this.uploadingFiles = false;
			this.errorMessageFromUploader =
				'Failed to upload files. Please try again.';
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
		restoreBackup() {
			return {
				url: 'press.api.site.restore',
				onSuccess() {
					this.selectedFiles = {};
					this.$router.push({
						name: 'Site Jobs',
						params: { name: this.site },
					});
					this.showRestoreDialog = false;
					this.$toast.success('Restoration triggered successfully.');
				},
			};
		},
	},
	beforeUnmount() {
		this.stopProgressTracking();
	},
};
</script>
