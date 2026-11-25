// The AccuHub task pipeline, in order (accuhub_link.pipeline.STAGE_SQL; prototype ACM-SP-08): one list for the
// Integrations page's columns and the stage page's tabs, so the two never name or order a stage differently.
export const STAGES = [
	{ key: 'backlog', label: 'Backlog', hint: 'With us, nobody assigned yet' },
	{ key: 'optiflow', label: 'With OptiFlow', hint: 'A developer is on it' },
	{ key: 'accurate', label: 'With Accurate', hint: 'Accurate is testing or reviewing it' },
	{ key: 'closed', label: 'Closed, 30 days', hint: 'Completed or cancelled in the last 30 days' },
];

export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// The stage's tasks as a tree (accuhub_link 0.6.0, prototype ACH-SP-06): a group not in the stage comes as a heading,
// never counted. A link older than 0.6.0 sends no in_stage and no depth: every row is a task, flat, as before.
export const isHeading = (row) => row.in_stage === false;
export const stageCount = (rows) => rows.filter((row) => !isHeading(row)).length;
export const indent = (row) => `${Math.min(Number(row.depth) || 0, 6) * 20}px`;

// "23 Nov" from the client's "2026-11-23 13:26:01"; the year too when it is not this year
export function taskDay(stamp, thisYear = new Date().getFullYear()) {
	if (!stamp) return '';
	const text = String(stamp);
	const day = `${Number(text.slice(8, 10))} ${MONTHS[Number(text.slice(5, 7)) - 1]}`;
	return Number(text.slice(0, 4)) === thisYear ? day : `${day} ${text.slice(0, 4)}`;
}
