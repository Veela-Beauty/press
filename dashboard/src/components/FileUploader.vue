<template>
	<div>
		<input
			ref="input"
			type="file"
			:accept="fileTypes"
			class="hidden"
			@change="onFileAdd"
		/>
		<slot
			v-bind="{
				file,
				uploading,
				progress,
				uploaded,
				message,
				error,
				total,
				success,
				openFileSelector,
			}"
		/>
	</div>
</template>

<script>
import FileUploader from '@/controllers/fileUploader';
import S3FileUploader from '@/controllers/s3FileUploader';
import DirectFileUploader from '@/controllers/directFileUploader';
import { trypromise } from '@/utils';

// Cache S3 availability check globally (shared across all FileUploader instances)
let _s3CheckResult = null;
let _s3CheckPromise = null;

async function checkS3Available() {
	if (_s3CheckResult !== null) return _s3CheckResult;
	if (_s3CheckPromise) return _s3CheckPromise;
	_s3CheckPromise = fetch('/api/method/press.api.site.is_s3_configured')
		.then((res) => res.json())
		.then((data) => {
			_s3CheckResult = !!data.message;
			return _s3CheckResult;
		})
		.catch(() => {
			_s3CheckResult = false;
			return false;
		});
	return _s3CheckPromise;
}

export default {
	name: 'FileUploader',
	props: [
		'fileTypes',
		'uploadArgs',
		's3',
		'type',
		'fileValidator',
		'disableAutoUpload',
	],
	emits: ['success', 'failure', 'setFile'],
	data() {
		return {
			uploader: null,
			uploading: false,
			uploaded: 0,
			error: null,
			message: '',
			total: 0,
			file: null,
			finishedUploading: false,
			s3Available: null,
		};
	},
	computed: {
		progress() {
			let value = Math.floor((this.uploaded / this.total) * 100);
			return isNaN(value) ? 0 : value;
		},
		success() {
			return this.finishedUploading && !this.error;
		},
	},
	methods: {
		openFileSelector() {
			this.$refs['input'].click();
		},
		async onFileAdd(e) {
			this.error = null;
			this.finishedUploading = false;
			this.uploading = false;
			this.uploaded = 0;
			this.total = 0;
			this.message = '';

			this.file = e.target.files[0];

			if (this.file && this.fileValidator) {
				let [error, _] = await trypromise(this.fileValidator(this.file));
				if (error) {
					this.error = error;
				}
			}

			if (this.error) {
				this.$emit('failure', this.error);
				return;
			}

			this.$emit('setFile', this.file);
			if (!this.disableAutoUpload) await this.uploadFile();
		},
		async uploadFile() {
			if (this.uploaded || this.finishedUploading || this.error || !this.file) {
				return;
			}
			this.error = null;
			this.uploaded = 0;
			this.total = 0;

			// Auto-detect: if s3 prop is true, check if S3 is actually configured
			if (this.s3 && this.s3Available === null) {
				this.s3Available = await checkS3Available();
			}
			this.uploader = this.s3
				? (this.s3Available ? new S3FileUploader() : new DirectFileUploader())
				: new FileUploader();
			this.uploader.on('start', () => {
				this.uploading = true;
			});
			this.uploader.on('progress', (data) => {
				this.uploaded = data.uploaded;
				this.total = data.total;
			});
			this.uploader.on('error', () => {
				this.uploading = false;
				this.error = 'Error Uploading File';
			});
			this.uploader.on('finish', () => {
				this.uploading = false;
				this.finishedUploading = true;
			});
			this.uploader
				.upload(this.file, this.uploadArgs || {})
				.then((data) => {
					this.$emit('success', data);
				})
				.catch((error) => {
					this.uploading = false;
					let errorMessage = 'Error Uploading File';
					if (error._server_messages) {
						errorMessage = JSON.parse(
							JSON.parse(error._server_messages)[0],
						).message;
					} else if (error.exc) {
						errorMessage = JSON.parse(error.exc)[0]
							.split('\n')
							.slice(-2, -1)[0];
					}
					this.error = errorMessage;
					this.$emit('failure', errorMessage);
				});
		},
	},
};
</script>
