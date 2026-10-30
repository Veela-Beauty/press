import { reactive } from 'vue';
import { createResource } from 'frappe-ui';

// In-flight unit actions (unit _id -> 'stopping' ...), shared so collapsing and re-opening
// a server row mid-action keeps its buttons disabled.
export const unitBusy = reactive({});

// Polled read of the whole infra tree (server-side cache, cleared after a unit action).
export function useInfraTree() {
	return createResource({ url: 'press.api.infra_board.get_infra_tree', auto: true });
}

// Gate-0 preflight: is the managed-host control plane provisioned? Drives the
// banner that tells an operator what is missing instead of a silent "Unreachable".
export function useGate0Status() {
	return createResource({ url: 'press.api.infra_board.gate0_status', auto: true });
}

// Promise wrapper for a one-shot whitelisted call (mirrors utils/backupApi.js).
function call(url, params) {
	return new Promise((resolve, reject) => {
		const r = createResource({ url, onSuccess: resolve, onError: reject });
		r.submit(params);
	});
}

export const unitAction = (host, unit_id, action) =>
	call('press.api.infra_board.host_unit_action', { host, unit_id, action });
export const unitLog = (host, unit_id, tail = 200) =>
	call('press.api.infra_board.get_host_log', { host, unit_id, tail });
export const testConnection = (host) => call('press.api.infra_board.test_connection', { host });
export const addHost = (p) => call('press.api.infra_board.add_managed_host', p);
