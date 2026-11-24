// The AccuHub task pipeline, in order (accuhub_link.pipeline.STAGE_SQL; prototype ACM-SP-08): one list for the
// Integrations page's columns and the stage page's tabs, so the two never name or order a stage differently.
export const STAGES = [
	{ key: 'backlog', label: 'Backlog', hint: 'With us, nobody assigned yet' },
	{ key: 'optiflow', label: 'With OptiFlow', hint: 'A developer is on it' },
	{ key: 'accurate', label: 'With Accurate', hint: 'Accurate is testing or reviewing it' },
	{ key: 'closed', label: 'Closed, 30 days', hint: 'Completed or cancelled in the last 30 days' },
];
