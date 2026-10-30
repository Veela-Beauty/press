// Real frappe-ui components; only the server `call` is faked so the dialog renders offline.
export * from '../node_modules/frappe-ui/src/index.ts';

const SITES = [
	{ name: 'accuhub-dev-v15.sandbox.mvpstorm.com', group: 'bench-0015', is_confidential: 1 },
	{ name: 'claudecodelearn.sandbox.mvpstorm.com', group: 'bench-0015', is_confidential: 0 },
	{ name: 'tchworx.sandbox.mvpstorm.com', group: 'bench-0015', is_confidential: 0 },
	{ name: 'hstp-stg.sandbox.mvpstorm.com', group: 'bench-0044', is_confidential: 0 },
];
const RGS = [
	{ name: 'bench-0015', title: 'AccuHub dev v15' },
	{ name: 'bench-0044', title: 'HSTP staging' },
];

window.__calls = [];
export async function call(method, args) {
	window.__calls.push({ method, args });
	if (method.endsWith('list_my_sites')) return SITES;
	if (method.endsWith('list_my_release_groups')) return RGS;
	if (method.endsWith('issue_token')) {
		const confidential = (args.allowed_sites || []).filter((n) => SITES.find((s) => s.name === n)?.is_confidential);
		if (confidential.length && args.confidential_pin !== '1234') throw { messages: ['Incorrect PIN'] };
		return { token: 'pmcp_fake_token_for_render', confidential_sites: confidential };
	}
	return null;
}
