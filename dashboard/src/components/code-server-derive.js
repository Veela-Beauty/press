// Pure view logic for SiteDevCodeServerCard (tested in code-server-derive.test.js).

export const POLL_MS = 10000;
export const MAX_POLLS = 30; // 5 minutes; a reload starts polling again

// Which card to show for a get_code_server_status() result.
export const cardState = (cs = {}) => {
	if (cs.status === 'Running') return 'running';
	if (!cs.exists && cs.status !== 'Pending') return 'launch';
	if (cs.exists && cs.status === 'Pending') return 'starting';
	if (cs.exists) return cs.status === 'Stopped' ? 'stopped' : 'failed';
	return 'none';
};

export const shouldPoll = (cs = {}, polls = 0) => cs.status === 'Pending' && polls < MAX_POLLS;
