import { createResource } from 'frappe-ui';

// ── Backend contract: press/api/infra_telephony.py ───────────────────────────
// The page binds to press.api.infra_telephony.* (NOT press.api.telephony.*).
//
// IMPLEMENTED today (verbatim signatures from infra_telephony.py):
//   telephony_describe(host)                         -> { host, trunk_registered, active_calls, listener_connected }  (secret-free per-host read)
//   telephony_provision(host, site_url, oc_instance, api_token=None) -> { ok, host, instance, public_ip }  (SYNCHRONOUS; no job id)
//   firewall_rule(host, trunk_ip, action="allow")    -> { ok, host, trunk_ip, action }   action in allow|deny
//   mint_listener_token(site, instance, listener_user=None, supplied_key_secret=None) -> "key:secret"
//   decommission_pbx(host, instance)                 -> { ok, host, instance, recordings }
//
// IMPLEMENTED by the infra-telephony backend (Plan 3, added to infra_telephony.py
// with these EXACT names; all gated to Telephony Ops / System Manager + audited):
//   get_pbx_tree()                                   -> { hosts:[Host], summary, generated }  (15s server-side cache)
//   host_action(host, action)                        action in restart|stop|reregister  (firewall_test maps to firewall_rule)
//   get_listener_log(host, tail=200)                 -> [{ ts, level, msg }]
//   rotate_secret(host, secret_id)                   -> { ok, detail }  (secret_id in ami_password|api_token; secret never returned)
//   list_provision_targets(site_url=null)            -> { sites:[{site,instances:[{instance,has_auth,auth_age}]}], hosts:[{name,label,has_headroom}] }
//   validate_instance_auth(site_url, instance, api_token=null) -> { has_auth, detail }
//   test_host_connection(host_name, ssh_host, ssh_user, ssh_port) -> { ok, docker_ok, detail }
//   provision_status(job_id)                         -> { state, steps:[{key,label,state}], failure }  (terminal 'done' today; telephony_provision is synchronous)

// Polled read of the whole PBX tree (server-side 15s cache).
export function usePbxTree() {
	return createResource({ url: 'press.api.infra_telephony.get_pbx_tree', auto: true });
}

// Promise wrapper for a one-shot whitelisted call (mirrors infra-api.js / utils/backupApi.js).
function call(url, params) {
	return new Promise((resolve, reject) => {
		const r = createResource({ url, onSuccess: resolve, onError: reject });
		r.submit(params);
	});
}

// Secret-free per-host read (IMPLEMENTED).
export const describeHost = (host) => call('press.api.infra_telephony.telephony_describe', { host });

// firewall_test maps to the implemented firewall_rule; restart/stop/reregister are Plan-3 host_action.
export function hostAction(host, action) {
	if (action === 'firewall_test') {
		return call('press.api.infra_telephony.firewall_rule', { host, trunk_ip: '0.0.0.0', action: 'allow' });
	}
	return call('press.api.infra_telephony.host_action', { host, action });
}
export const firewallRule = (host, trunk_ip, action = 'allow') =>
	call('press.api.infra_telephony.firewall_rule', { host, trunk_ip, action });

// Plan-3 endpoints the page consumes (now implemented in infra_telephony.py).
export const listenerLog       = (host, tail = 200)        => call('press.api.infra_telephony.get_listener_log', { host, tail });
export const rotateSecret      = (host, secret_id)         => call('press.api.infra_telephony.rotate_secret', { host, secret_id });
export const provisionTargets  = ()                        => call('press.api.infra_telephony.list_provision_targets', {});
export const validateAuth      = (site, instance)          => call('press.api.infra_telephony.validate_instance_auth', { site_url: site, instance });
export const testHostConnection = (p)                      => call('press.api.infra_telephony.test_host_connection', p);
export const provisionStatus   = (job_id)                  => call('press.api.infra_telephony.provision_status', { job_id });

// IMPLEMENTED: synchronous provision. The wizard collects deploy/site/instance/host;
// telephony_provision takes (host, site_url, oc_instance, api_token). For deploy="fc"
// the operator-supplied key:secret is passed as api_token; for "self" the server mints it.
export function provisionPbx(p) {
	const site_url = p.deploy === 'fc' ? p.fc_site_url : (p.site ? `https://${p.site}` : '');
	return call('press.api.infra_telephony.telephony_provision', {
		host: p.host === 'new' ? p.host_name : p.host,
		site_url,
		oc_instance: p.instance,
		api_token: p.deploy === 'fc' ? p.fc_api_token : null,
	});
}

// IMPLEMENTED: decommission needs the instance (host:instance is the PBX key).
export const decommissionPbx = (host, instance) =>
	call('press.api.infra_telephony.decommission_pbx', { host, instance });
