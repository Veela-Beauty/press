import { describe, it, expect } from 'vitest';
import * as d from './code-server-derive';

describe('cardState', () => {
	it('running -> open link', () => expect(d.cardState({ exists: true, status: 'Running' })).toBe('running'));
	it('no code server -> launch', () => expect(d.cardState({ exists: false, status: null })).toBe('launch'));
	it('pending -> starting', () => expect(d.cardState({ exists: true, status: 'Pending' })).toBe('starting'));
	it('broken -> failed with restart', () => expect(d.cardState({ exists: true, status: 'Broken' })).toBe('failed'));
	it('stopped -> stopped with restart', () => expect(d.cardState({ exists: true, status: 'Stopped' })).toBe('stopped'));
	it('pending without a record -> nothing yet', () => expect(d.cardState({ exists: false, status: 'Pending' })).toBe('none'));
	it('empty result -> launch', () => expect(d.cardState()).toBe('launch'));
});

describe('shouldPoll', () => {
	it('polls while pending', () => expect(d.shouldPoll({ status: 'Pending' }, 0)).toBe(true));
	it('stops after MAX_POLLS', () => expect(d.shouldPoll({ status: 'Pending' }, d.MAX_POLLS)).toBe(false));
	it('stops once running', () => expect(d.shouldPoll({ status: 'Running' }, 0)).toBe(false));
	it('stops once failed', () => expect(d.shouldPoll({ status: 'Broken' }, 0)).toBe(false));
});
