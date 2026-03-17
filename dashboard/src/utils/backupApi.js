// Centralized API helpers for Daman Backup dashboard actions
// All methods call existing whitelisted Python APIs — no new backend code

const BASE_JOB = 'daman_backup.daman_backup.doctype.backup_job.backup_job';
const BASE_QUEUE = 'daman_backup.daman_backup.doctype.backup_job_queue.backup_job_queue';

async function call(method, args) {
	var res = await fetch('/api/method/' + method, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			'X-Frappe-CSRF-Token': window.csrf_token || '',
		},
		body: JSON.stringify(args),
	});
	if (!res.ok) {
		throw new Error('HTTP ' + res.status);
	}
	var data = await res.json();
	if (data.exc) {
		var msg = 'Unknown error';
		try { msg = JSON.parse(data.exc)[0]; } catch (e) { /* ignore */ }
		throw new Error(msg);
	}
	return data.message || data;
}

// --- Backup Job actions ---

export function runBackupJob(jobName, mode, priority) {
	return call(BASE_JOB + '.run_backup_job', {
		job_name: jobName,
		mode: mode || 'run',
		priority: priority || null,
	});
}

export function toggleJobStatus(jobName) {
	return call(BASE_JOB + '.toggle_job_status', { job_name: jobName });
}

export function toggleSchedule(jobName) {
	return call(BASE_JOB + '.toggle_schedule', { job_name: jobName });
}

export function setupJob(jobName) {
	return call(BASE_JOB + '.setup_job', { job_name: jobName });
}

export function listJobArchives(jobName) {
	return call(BASE_JOB + '.list_job_archives', { job_name: jobName });
}

export function getRepoInfo(jobName) {
	return call(BASE_JOB + '.get_repo_info', { job_name: jobName });
}

export function getJobStatistics(jobName) {
	return call(BASE_JOB + '.get_job_statistics', { job_name: jobName });
}

export function getJobHistory(jobName, limit) {
	return call(BASE_JOB + '.get_job_history', { job_name: jobName, limit: limit || 50 });
}

// --- Backup Job Queue actions ---

export function cancelJob(queueName) {
	return call(BASE_QUEUE + '.cancel_job', { job_queue_name: queueName });
}

export function retryJob(queueName) {
	return call(BASE_QUEUE + '.retry_job', { job_queue_name: queueName });
}

export function forceCompleteJob(queueName) {
	return call(BASE_QUEUE + '.force_complete_job', { job_queue_name: queueName });
}

export function getJobProgress(queueName) {
	return call(BASE_QUEUE + '.get_job_progress', { job_queue_name: queueName });
}

export function bulkCancelJobs(names) {
	return call(BASE_QUEUE + '.bulk_cancel_jobs', { names: names });
}
