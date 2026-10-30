// Real frappe-ui components; only the server `call` is faked so the dialog renders offline.
export * from '../node_modules/frappe-ui/src/index.ts';

const SITES = [
	{ name: 'accuhub-dev-v15.sandbox.mvpstorm.com', group: 'bench-0015', is_confidential: 1 },
	{ name: 'claudecodelearn.sandbox.mvpstorm.com', group: 'bench-0015' },
	{ name: 'tchworx.sandbox.mvpstorm.com', group: 'bench-0015' },
	{ name: 'hstp-stg.sandbox.mvpstorm.com', group: 'bench-0044' },
];
const RGS = [
	{ name: 'bench-0015', title: 'AccuHub dev v15' },
	{ name: 'bench-0044', title: 'HSTP staging' },
];

export async function call(method) {
	if (method.endsWith('list_my_sites')) return SITES;
	if (method.endsWith('list_my_release_groups')) return RGS;
	if (method.endsWith('issue_token')) throw { messages: [window.__issueError || 'Incorrect PIN'] };
	return null;
}
