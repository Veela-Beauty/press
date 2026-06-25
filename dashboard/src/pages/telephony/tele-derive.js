// Pure view-model helpers for the Telephony dashboard. No Vue imports - unit-tested.
const num = (v) => (typeof v === 'number' ? v : null);

export const cpuPct = (h) => num(h.cpu_pct);

export function hostDot(h) {
  if (h.status === 'unknown') return 'unk';
  if (h.status === 'down') return 'down';
  if (h.status === 'warn') return 'warn';
  return 'up';
}

export function regCounts(h) {
  const total = (h.instances || []).length;
  const registered = (h.instances || []).filter((i) => i.reg === 'reg').length;
  const unreg = (h.instances || []).filter((i) => i.reg === 'unreg').length;
  return { registered, total, unreg };
}

export function listenerInfo(h) {
  if (h.listener === 'connected') return { text: 'connected', dot: 'up' };
  if (h.listener === 'disconnected') return { text: 'disconnected', dot: 'down' };
  return { text: 'unknown', dot: 'unk' };
}

export function hostHasIssues(h) {
  if (h.status === 'down' || h.status === 'warn' || h.status === 'unknown') return true;
  if (h.listener !== 'connected') return true;
  return regCounts(h).unreg > 0;
}

export function summary(hosts = []) {
  let trunks = 0, registered = 0, trunkDown = 0, activeCalls = 0, listenersUp = 0;
  for (const h of hosts) {
    const r = regCounts(h);
    trunks += r.total;
    registered += r.registered;
    trunkDown += r.unreg;
    activeCalls += h.active_calls || 0;
    if (h.listener === 'connected') listenersUp += 1;
  }
  return { hosts: hosts.length, trunks, registered, trunkDown, activeCalls, listenersUp };
}

// Triage feed: one row per unregistered trunk + one per disconnected listener + one per host-down.
export function attention(hosts = []) {
  const out = [];
  for (const h of hosts) {
    if (h.status === 'down' || h.status === 'unknown') {
      out.push({ kind: 'host_down', host: h.name, detail: 'PBX host unreachable' });
      continue; // a down host already implies its trunks are down; do not double-list
    }
    for (const i of h.instances || []) {
      if (i.reg === 'unreg') {
        out.push({ kind: 'unreg', host: h.name, detail: `${i.trunk} (${i.instance}) unregistered - check credentials or provider allowlist` });
      }
    }
    if (h.listener !== 'connected') {
      out.push({ kind: 'listener', host: h.name, detail: 'Listener not connected to AMI' });
    }
  }
  return out;
}

export function filterHosts(hosts = [], seg = 'all', q = '') {
  let rows = hosts;
  if (seg === 'registered') rows = rows.filter((h) => !hostHasIssues(h));
  else if (seg === 'issues') rows = rows.filter(hostHasIssues);
  const lq = q.trim().toLowerCase();
  if (lq) rows = rows.filter((h) => h.name.toLowerCase().includes(lq));
  return rows;
}

// Provision: rollback is offered only when the run failed AND at least one step actually ran
// (so there is something to undo - close firewall / revoke token).
export function rollbackable(status) {
  if (!status || status.state !== 'failed') return false;
  return (status.steps || []).some((s) => s.state === 'done' || s.state === 'failed');
}
