import { describe, it, expect } from 'vitest';
import { STAGES, isHeading, stageCount, indent, taskDay, MONTHS } from './integrations';

// rows as accuhub_link 0.6.0 sends them through the hub (prototype ACH-SP-06), and one from an older link
const heading = { task: 'TASK-2', subject: 'SlfStg2 : Self Storage', in_stage: false, is_group: true, depth: 0 };
const group = { task: 'TASK-3', subject: 'SlfStg2 : Website Integration Phase 1', in_stage: true, is_group: true, depth: 1 };
const task = { task: 'TASK-4', subject: '1. Price and Discount', in_stage: true, depth: 2, created_on: '2026-11-23 13:26:01' };
const older = { task: 'TASK-5', subject: 'From a link before 0.6.0' };

describe('the tree', () => {
	it('a group not in the stage is a heading; an older row is a task', () => {
		expect([heading, group, task, older].map(isHeading)).toEqual([true, false, false, false]);
	});
	it('counts only the stage tasks, not the headings', () => expect(stageCount([heading, group, task, older])).toBe(3));
	it('indents 20 px a level, at most 6 levels, none for an older row', () => {
		expect([heading, group, task, older, { depth: 40 }].map(indent)).toEqual(['0px', '20px', '40px', '0px', '120px']);
	});
});

describe('taskDay', () => {
	it('day and month, the year only when it is not this one', () => {
		expect(taskDay('2026-11-23 13:26:01', 2026)).toBe('23 Nov');
		expect(taskDay('2025-02-05 08:00:00', 2026)).toBe('5 Feb 2025');
	});
	it('nothing for no date', () => {
		expect(taskDay('', 2026)).toBe('');
		expect(taskDay(undefined, 2026)).toBe('');
	});
});

describe('shared lists', () => {
	it('stages and months keep their order', () => {
		expect(STAGES.map((s) => s.key)).toEqual(['backlog', 'optiflow', 'accurate', 'closed']);
		expect(MONTHS[10]).toBe('Nov');
	});
});
