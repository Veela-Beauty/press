const CHUNK_THRESHOLD = 100 * 1024 * 1024; // 100MB — files larger than this use chunked upload

export default class DirectFileUploader {
	constructor() {
		this.listeners = {};
	}

	on(event, handler) {
		this.listeners[event] = this.listeners[event] || [];
		this.listeners[event].push(handler);
	}

	trigger(event, data) {
		const handlers = this.listeners[event] || [];
		handlers.forEach((handler) => handler.call(this, data));
	}

	upload(file, options) {
		if (file.size > CHUNK_THRESHOLD) {
			return this._chunkedUpload(file);
		}
		return this._directUpload(file);
	}

	_directUpload(file) {
		return new Promise((resolve, reject) => {
			const xhr = new XMLHttpRequest();
			xhr.upload.addEventListener('loadstart', () => this.trigger('start'));
			xhr.upload.addEventListener('progress', (e) => {
				if (e.lengthComputable) {
					this.trigger('progress', { uploaded: e.loaded, total: e.total });
				}
			});
			xhr.upload.addEventListener('load', () => this.trigger('finish'));
			xhr.addEventListener('error', () => {
				this.trigger('error');
				reject(new Error('Network error'));
			});
			xhr.onreadystatechange = () => {
				if (xhr.readyState === XMLHttpRequest.DONE) {
					if (xhr.status === 200) {
						try {
							const r = JSON.parse(xhr.responseText);
							resolve(r.message || r);
						} catch (e) {
							resolve(xhr.responseText);
						}
					} else {
						let error;
						try {
							error = JSON.parse(xhr.responseText);
							if (error._server_messages) {
								const msg = JSON.parse(JSON.parse(error._server_messages)[0]).message;
								reject(new Error(msg));
								return;
							}
						} catch (e) {
							error = xhr.responseText;
						}
						reject(error);
					}
				}
			};

			xhr.open('POST', '/api/method/press.api.site.upload_backup_file', true);
			xhr.setRequestHeader('Accept', 'application/json');
			this._setCsrf(xhr);

			const form_data = new FormData();
			form_data.append('file', file, file.name);
			form_data.append('type', file.type || 'application/octet-stream');
			xhr.send(form_data);
		});
	}

	async _chunkedUpload(file) {
		this.trigger('start');

		// Step 1: Initialize upload session
		const initRes = await this._apiCall('press.api.site.init_chunked_upload', {
			file_name: file.name,
			file_size: file.size,
			file_type: file.type || 'application/octet-stream',
		});
		const { upload_id, chunk_size } = initRes;
		const totalChunks = Math.ceil(file.size / chunk_size);
		let totalUploaded = 0;

		// Step 2: Upload chunks sequentially with progress
		for (let i = 0; i < totalChunks; i++) {
			const start = i * chunk_size;
			const end = Math.min(start + chunk_size, file.size);
			const chunk = file.slice(start, end);

			await this._uploadSingleChunk(upload_id, i, chunk, file.size, totalUploaded);
			totalUploaded += (end - start);
			this.trigger('progress', { uploaded: totalUploaded, total: file.size });
		}

		// Step 3: Finalize — reassemble chunks on server
		const result = await this._apiCall('press.api.site.finalize_chunked_upload', {
			upload_id,
		});

		this.trigger('finish');
		return result;
	}

	_uploadSingleChunk(uploadId, chunkIndex, blob, totalSize, previouslyUploaded) {
		return new Promise((resolve, reject) => {
			const xhr = new XMLHttpRequest();
			xhr.upload.addEventListener('progress', (e) => {
				if (e.lengthComputable) {
					this.trigger('progress', {
						uploaded: previouslyUploaded + e.loaded,
						total: totalSize,
					});
				}
			});
			xhr.addEventListener('error', () => {
				this.trigger('error');
				reject(new Error('Chunk upload failed'));
			});
			xhr.onreadystatechange = () => {
				if (xhr.readyState === XMLHttpRequest.DONE) {
					if (xhr.status === 200) {
						resolve();
					} else {
						let msg = 'Chunk upload failed';
						try {
							const err = JSON.parse(xhr.responseText);
							if (err._server_messages) {
								msg = JSON.parse(JSON.parse(err._server_messages)[0]).message;
							}
						} catch (e) { /* ignore parse error */ }
						reject(new Error(msg));
					}
				}
			};

			xhr.open('POST', '/api/method/press.api.site.upload_chunk', true);
			xhr.setRequestHeader('Accept', 'application/json');
			this._setCsrf(xhr);

			const formData = new FormData();
			formData.append('upload_id', uploadId);
			formData.append('chunk_index', chunkIndex);
			formData.append('file', blob, 'chunk_' + chunkIndex);
			xhr.send(formData);
		});
	}

	async _apiCall(method, args) {
		const headers = {
			'Accept': 'application/json',
			'Content-Type': 'application/json',
		};
		if (window.csrf_token && window.csrf_token !== '{{ csrf_token }}') {
			headers['X-Frappe-CSRF-Token'] = window.csrf_token;
		}
		const res = await fetch('/api/method/' + method, {
			method: 'POST',
			headers,
			body: JSON.stringify(args),
		});
		if (!res.ok) {
			let msg = 'Server error ' + res.status;
			try {
				const err = await res.json();
				if (err._server_messages) {
					msg = JSON.parse(JSON.parse(err._server_messages)[0]).message;
				}
			} catch (e) { /* ignore */ }
			throw new Error(msg);
		}
		const data = await res.json();
		return data.message;
	}

	_setCsrf(xhr) {
		if (window.csrf_token && window.csrf_token !== '{{ csrf_token }}') {
			xhr.setRequestHeader('X-Frappe-CSRF-Token', window.csrf_token);
		}
	}
}
