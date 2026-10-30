// Real frappe-ui components; only server access (call / resources) is faked so pages render offline.
import { reactive } from 'vue';
export * from '../node_modules/frappe-ui/src/index.ts';

const SITES = [
	{ name: 'accuhub-dev-v15.sandbox.mvpstorm.com', group: 'bench-0015', is_confidential: 1, status: 'Active' },
	{ name: 'claudecodelearn.sandbox.mvpstorm.com', group: 'bench-0015', is_confidential: 0, status: 'Active' },
	{ name: 'tchworx.sandbox.mvpstorm.com', group: 'bench-0015', is_confidential: 0, status: 'Suspended' },
	{ name: 'hstp-stg.sandbox.mvpstorm.com', group: 'bench-0044', is_confidential: 0, status: 'Updating' },
];
const RGS = [
	{ name: 'bench-0015', title: 'Accurate System Bench 15', version: 'Version 15', active_benches: 1, site_count: 3,
		apps: [{ app: 'frappe' }, { app: 'erpnext' }, { app: 'hrms' }, { app: 'payments' }, { app: 'ksa_compliance' }],
		server: 'f1', server_title: 'press-f1 (Hetzner, Falkenstein)', server_provider: 'Hetzner' },
	{ name: 'bench-0044', title: 'HSTP staging', version: 'Version 15', active_benches: 1, site_count: 1,
		apps: [{ app: 'frappe' }, { app: 'erpnext' }], server: 'u4', server_title: 'u4-default', server_provider: 'Generic' },
	{ name: 'bench-0071', title: 'Onboarding Suite Staging', version: 'Version 15', active_benches: 0, site_count: 0,
		apps: [{ app: 'frappe' }, { app: 'erpnext' }, { app: 'onboarding_suite' }],
		server: 'f1', server_title: 'press-f1 (Hetzner, Falkenstein)', server_provider: 'Hetzner' },
];
const APPS = ['ERPNext', 'HRMS', 'Payments', 'Lending', 'Helpdesk', 'Insights'].map((t) => ({
	name: t.toLowerCase(), title: t, description: `${t} by Frappe`, image: '',
	sources: [{ name: `src-${t.toLowerCase()}`, repository_owner: 'frappe' }],
}));

window.__calls = [];
export async function call(method, args) {
	window.__calls.push({ method, args });
	if (method.endsWith('list_my_sites')) return SITES.map((s) => ({ name: s.name, group: s.group, is_confidential: s.is_confidential }));
	if (method.endsWith('list_my_release_groups')) return RGS.map((r) => ({ name: r.name, title: r.title }));
	if (method.endsWith('issue_token')) {
		const confidential = (args.allowed_sites || []).filter((n) => SITES.find((s) => s.name === n)?.is_confidential);
		if (confidential.length && args.confidential_pin !== '1234') throw { messages: ['Incorrect PIN'] };
		return { token: 'pmcp_fake_token_for_render', confidential_sites: confidential };
	}
	return null;
}

function rows(doctype, filters) {
	if (doctype === 'Release Group') {
		const like = filters.title?.[1]?.replaceAll('%', '').toLowerCase();
		return RGS.filter((r) => (!like || r.title.toLowerCase().includes(like)) && (!filters.version || r.version === filters.version));
	}
	if (doctype === 'Site') {
		return SITES.filter((s) => s.group === filters.group).map((s) => ({
			name: s.name, status: s.status, host_name: s.name, server: s.group === 'bench-0015' ? 'press-f1' : 'u4-default',
			cluster_title: 'Falkenstein', cluster_image: '',
		}));
	}
	return [];
}

export function createListResource(opts) {
	const r = reactive({
		data: null, list: { loading: false }, hasNextPage: false, filters: { ...(opts.filters || {}) },
		reload() {
			window.__calls.push({ method: `list:${opts.doctype}`, args: { filters: r.filters, fields: opts.fields } });
			r.data = rows(opts.doctype, r.filters);
			opts.onSuccess?.(r.data);
			return Promise.resolve(r.data);
		},
		update(o) { if (o.filters) r.filters = o.filters; },
		next() {},
		fetch() { return r.reload(); },
	});
	if (opts.auto) r.reload();
	return r;
}

export function createResource(opts) {
	const r = reactive({
		data: opts.initialData ?? null, loading: false, params: opts.params,
		async submit(params) {
			window.__calls.push({ method: opts.url, args: params });
			let data = null;
			if (opts.url.endsWith('all_apps')) data = APPS.map((a) => ({ ...a }));
			if (opts.url.endsWith('deploy_information')) data = { apps: [] };
			if (opts.url.endsWith('deploy_and_update')) data = 'DC-0001';
			if (opts.transform) data = opts.transform(data);
			r.data = data;
			await opts.onSuccess?.(data);
			return data;
		},
		fetch() { return r.submit(r.params); },
		reload() { return r.submit(r.params); },
	});
	if (opts.auto) r.fetch();
	return r;
}

export function createDocumentResource(opts) {
	return reactive({ doc: { name: opts.name }, delete: { loading: false, submit: () => Promise.resolve() } });
}
