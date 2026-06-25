import { describe, it, expect } from 'vitest';
import * as d from './tele-derive';

const up = {
  name: 'press-ctrl', ip: '89.167.116.92', status: 'up', container: 'running',
  listener: 'connected', active_calls: 1, cpu_pct: 14, uptime: '4d 6h',
  instances: [
    { instance: 'dmg-voip', site: 'dmg-erp', trunk: 'Bevatel', did: '+966115154690', reg: 'reg' },
    { instance: 'ss-voip', site: 'selfstorage-stg', trunk: 'Unifonic', did: '+966112340707', reg: 'reg' },
  ],
};
const warn = {
  name: 'alfanar-pbx', ip: '95.217.40.10', status: 'warn', container: 'running',
  listener: 'connected', active_calls: 0, cpu_pct: 6, uptime: '2d 1h',
  instances: [{ instance: 'alfanar-voip', site: 'alfanar-erp', trunk: 'STC Business', did: '+966119901200', reg: 'unreg' }],
};
const down = { name: 'dead-pbx', ip: '1.2.3.4', status: 'down', container: 'stopped', listener: 'disconnected', active_calls: 0, cpu_pct: 0, uptime: '—', instances: [] };
const unk = { name: 'gone-pbx', ip: '5.6.7.8', status: 'unknown', container: 'missing', listener: 'unknown', active_calls: 0, cpu_pct: null, uptime: '—', instances: [] };

describe('hostDot', () => {
  it('up -> up', () => expect(d.hostDot(up)).toBe('up'));
  it('warn -> warn', () => expect(d.hostDot(warn)).toBe('warn'));
  it('down -> down', () => expect(d.hostDot(down)).toBe('down'));
  it('unknown -> unk', () => expect(d.hostDot(unk)).toBe('unk'));
});

describe('regCounts', () => {
  it('counts registered vs unregistered trunks across a host', () => {
    expect(d.regCounts(up)).toEqual({ registered: 2, total: 2, unreg: 0 });
    expect(d.regCounts(warn)).toEqual({ registered: 0, total: 1, unreg: 1 });
  });
});

describe('hostHasIssues', () => {
  it('any unreg trunk, listener not connected, or non-up status is an issue', () => {
    expect(d.hostHasIssues(up)).toBe(false);
    expect(d.hostHasIssues(warn)).toBe(true);   // unreg trunk
    expect(d.hostHasIssues(down)).toBe(true);    // status down + listener disconnected
  });
});

describe('listenerInfo', () => {
  it('maps connected/disconnected/unknown to {text,dot}', () => {
    expect(d.listenerInfo(up)).toEqual({ text: 'connected', dot: 'up' });
    expect(d.listenerInfo(down)).toEqual({ text: 'disconnected', dot: 'down' });
    expect(d.listenerInfo(unk)).toEqual({ text: 'unknown', dot: 'unk' });
  });
});

describe('summaryCards', () => {
  it('rolls up hosts / trunks / registered / down / active calls / listeners', () => {
    const s = d.summary([up, warn, down]);
    expect(s).toMatchObject({ hosts: 3, trunks: 3, registered: 2, trunkDown: 1, activeCalls: 1, listenersUp: 2 });
  });
});

describe('attention', () => {
  it('lists unregistered trunks and disconnected listeners, host-down once', () => {
    const a = d.attention([up, warn, down]);
    expect(a.find((x) => x.kind === 'unreg' && x.host === 'alfanar-pbx')).toBeTruthy();
    expect(a.find((x) => x.kind === 'host_down' && x.host === 'dead-pbx')).toBeTruthy();
    expect(a.length).toBe(2); // up has no issues
  });
});

describe('filterHosts', () => {
  it('All / Registered / Issues + search by name', () => {
    const all = [up, warn, down];
    expect(d.filterHosts(all, 'all', '').map((h) => h.name)).toEqual(['press-ctrl', 'alfanar-pbx', 'dead-pbx']);
    expect(d.filterHosts(all, 'registered', '').map((h) => h.name)).toEqual(['press-ctrl']);
    expect(d.filterHosts(all, 'issues', '').map((h) => h.name)).toEqual(['alfanar-pbx', 'dead-pbx']);
    expect(d.filterHosts(all, 'all', 'alf').map((h) => h.name)).toEqual(['alfanar-pbx']);
  });
});

describe('rollbackable', () => {
  it('a failed provision step exposes rollback only when a non-pending step ran', () => {
    expect(d.rollbackable({ state: 'failed', steps: [{ state: 'done' }, { state: 'failed' }] })).toBe(true);
    expect(d.rollbackable({ state: 'running', steps: [{ state: 'running' }] })).toBe(false);
    expect(d.rollbackable({ state: 'done', steps: [{ state: 'done' }] })).toBe(false);
  });
});
