import { describe, it, expect } from 'vitest';
import * as d from './infra-derive';

const pressNode = { name: 'press-f1', benches: [{ name: 'b1', health: 'down', services_down: 1, services_up: 5 }], host: { ssh: { ok: true }, memory: { used_pct: 50 } }, health: 'down' };
const dockerNode = { name: 'acc-1', kind: 'managed', server_type: 'docker', units: [{ name: 'x', kind: 'container', state: 'stop', _id: 'a'.repeat(64) }, { name: 'y', kind: 'container', state: 'run', _id: 'b'.repeat(64) }], metrics: { cpu: 95, mem: 40, disk: 30, req: 0 }, overload: 'crit', health: 'down' };
const plainNode = { name: 'box-1', kind: 'managed', server_type: 'plain', units: [{ name: 'sshd.service', kind: 'systemd', state: 'active' }], metrics: { cpu: 10, mem: 20, disk: 88, req: 0 }, overload: 'high', health: 'up' };

describe('partition', () => {
  it('splits servers vs managed by kind', () => {
    const { servers, infra } = d.partition([pressNode, dockerNode, plainNode]);
    expect(servers.map(s => s.name)).toEqual(['press-f1']);
    expect(infra.map(s => s.name)).toEqual(['acc-1', 'box-1']);
  });
});
describe('nodeDot', () => {
  it('down node -> down', () => expect(d.nodeDot(dockerNode)).toBe('down'));
  it('unreachable -> warn', () => expect(d.nodeDot({ ...plainNode, health: 'unknown' })).toBe('warn'));
  it('healthy -> up', () => expect(d.nodeDot({ ...plainNode, health: 'up', overload: null, metrics: { cpu: 5, mem: 5, disk: 5, req: 0 } })).toBe('up'));
});
describe('loadState', () => {
  it('crit at >=90', () => expect(d.loadState(dockerNode)).toEqual({ lvl: 'crit', which: 'CPU', val: 95 }));
  it('high at 80-89', () => expect(d.loadState(plainNode)).toEqual({ lvl: 'high', which: 'Disk', val: 88 }));
  it('null below 80 / press node (no metrics)', () => expect(d.loadState(pressNode)).toBeNull());
});
describe('unit helpers', () => {
  it('isDown covers stop/exit2/down', () => { expect(d.isDown('stop')).toBe(true); expect(d.isDown('exit2')).toBe(true); expect(d.isDown('down')).toBe(true); expect(d.isDown('run')).toBe(false); });
  it('uDot maps run/heal/active->up, exit0->unk, else down', () => { expect(d.uDot('run')).toBe('up'); expect(d.uDot('active')).toBe('up'); expect(d.uDot('exit0')).toBe('unk'); expect(d.uDot('stop')).toBe('down'); });
  it('stateLabel + theme', () => { expect(d.stateLabel('exit2')).toBe('exited (non-zero)'); expect(d.stateTheme('run')).toBe('green'); expect(d.stateTheme('stop')).toBe('red'); expect(d.stateTheme('exit0')).toBe('gray'); });
  it('controllable only for docker units with _id', () => { expect(d.controllable({ kind: 'container', _id: 'a'.repeat(64) })).toBe(true); expect(d.controllable({ kind: 'systemd' })).toBe(false); });
});
describe('triage', () => {
  it('issues() walks managed nodes for down units', () => {
    expect(d.issues([dockerNode, plainNode])).toEqual([{ server: 'acc-1', unit: 'x', state: 'stop' }]);
  });
  it('overloaded() returns crit nodes', () => expect(d.overloaded([dockerNode, plainNode]).map(s => s.name)).toEqual(['acc-1']));
  it('summary counts', () => {
    expect(d.summary([dockerNode, plainNode])).toMatchObject({ hosts: 2, unitsDown: 1, overloaded: 1, unreachable: 0 });
  });
});
