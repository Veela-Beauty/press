// Pure view-model helpers for the infra dashboard. No Vue imports - unit-tested.
const DOWN_STATES = new Set(['stop', 'exit2', 'down']);
const UP_STATES = new Set(['run', 'heal', 'active']);
const STATE_LABEL = { run: 'running', heal: 'healthy', unhealth: 'unhealthy', active: 'active', stop: 'stopped', down: 'down', exit0: 'exited (0)', exit2: 'exited (non-zero)', restart: 'restarting', dead: 'dead', pause: 'paused' };
const STATE_THEME = { run: 'green', heal: 'green', active: 'green', unhealth: 'orange', stop: 'red', down: 'red', exit2: 'red', dead: 'red', restart: 'orange', pause: 'gray', exit0: 'gray' };

export const isManaged = (n) => n.kind === 'managed';
const num = (v) => (typeof v === 'number' ? v : null);
export const cpuPct  = (n) => (isManaged(n) ? num(n.metrics?.cpu)  : num(n.host?.cpu?.used_pct));
export const memPct  = (n) => (isManaged(n) ? num(n.metrics?.mem)  : num(n.host?.memory?.used_pct));
export const diskPct = (n) => (isManaged(n) ? num(n.metrics?.disk) : num(n.host?.disk?.used_pct));
// Only Press servers that are genuinely UNREACHABLE (the probe failed). A reachable server whose
// rollup is 'down' from a single down/unknown bench is a service-level issue, not a server outage,
// so it is not raised as a top-level alarm (it still shows its status in the row).
export const unreachableServers = (nodes = []) =>
  nodes.filter((n) => !isManaged(n) && n.health === 'unknown');
export function partition(nodes = []) {
  return { servers: nodes.filter((n) => !isManaged(n)), infra: nodes.filter(isManaged) };
}
export function nodeDot(n) {
  if (n.health === 'unknown') return 'warn';
  if (n.health === 'down') return 'down';
  const l = loadState(n);
  if (l?.lvl === 'high') return 'warn';
  return 'up';
}
export function loadState(n) {
  const m = n.metrics;
  if (!m) return null;
  const pairs = [['CPU', m.cpu], ['Mem', m.mem], ['Disk', m.disk]];
  let hit = null;
  for (const [which, val] of pairs) {
    if (val >= 90) return { lvl: 'crit', which, val };
    if (val >= 80 && !hit) hit = { lvl: 'high', which, val };
  }
  return hit;
}
export const isDown = (s) => DOWN_STATES.has(s);
export const uDot = (s) => (UP_STATES.has(s) ? 'up' : s === 'exit0' ? 'unk' : 'down');
export const stateLabel = (s) => STATE_LABEL[s] || s;
export const stateTheme = (s) => STATE_THEME[s] || 'gray';
export const controllable = (u) => u.kind === 'container' && !!u._id;
export function issues(infraNodes = []) {
  const out = [];
  for (const n of infraNodes) for (const u of n.units || []) if (isDown(u.state)) out.push({ server: n.name, unit: u.name, state: u.state });
  return out;
}
export const overloaded = (infraNodes = []) => infraNodes.filter((n) => loadState(n)?.lvl === 'crit');
export function summary(infraNodes = []) {
  return {
    hosts: infraNodes.length,
    stacks: infraNodes.reduce((a, n) => a + (n.server_type === 'docker' ? (n.units || []).length : 0), 0),
    unitsDown: issues(infraNodes).length,
    overloaded: overloaded(infraNodes).length,
    unreachable: infraNodes.filter((n) => n.health === 'unknown').length,
  };
}
