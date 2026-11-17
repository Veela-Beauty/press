import { describe, it, expect } from 'vitest';
import * as d from './policies-derive';

const form = (over = {}) => ({
	...d.emptyPolicy(),
	policy_name: 'Standard',
	model_light: 'fast',
	model_normal: 'deepseek-chat',
	model_hard: 'deepseek-reasoner',
	rules_release: 'skills-2026-11-16',
	...over,
});

describe('emptyPolicy and fromServer', () => {
	it('starts with the approved defaults', () => {
		const f = d.emptyPolicy();
		expect(f.permission_mode).toBe('Ask before acting');
		expect(f.route).toBe('Through our gateway');
		expect(f.policy_name).toBe('');
		expect(f.rules_release).toBe('');
	});
	it('copies known fields and ignores null and unknown keys', () => {
		const f = d.fromServer({ policy_name: 'Senior', route: 'Own Claude Max, direct', model_hard: null, people_using: 3 });
		expect(f.policy_name).toBe('Senior');
		expect(f.route).toBe('Own Claude Max, direct');
		expect(f.model_hard).toBe('');
		expect(f.people_using).toBeUndefined();
	});
});

describe('isOwnMax', () => {
	it('is true only for the Own Claude Max route', () => {
		expect(d.isOwnMax(form({ route: 'Own Claude Max, direct' }))).toBe(true);
		expect(d.isOwnMax(form())).toBe(false);
	});
});

describe('modelOptions', () => {
	it('lists the served names', () => {
		const o = d.modelOptions([{ name: 'fast', accounts: 1 }, { name: 'deepseek-chat', accounts: 2 }], 'fast');
		expect(o).toEqual([{ label: 'fast', value: 'fast' }, { label: 'deepseek-chat', value: 'deepseek-chat' }]);
	});
	it('keeps a current name that is no longer served so the page can show it', () => {
		const o = d.modelOptions([{ name: 'fast', accounts: 1 }], 'old-model');
		expect(o[1]).toEqual({ label: 'old-model (not served now)', value: 'old-model' });
	});
});

describe('releaseOptions and defaultRelease', () => {
	const rel = [{ tag: 'skills-2026-11-16', date: '2026-11-16', latest: true }, { tag: 'skills-2026-11-02', date: '2026-11-02', latest: false }];
	it('labels tags the way the prototype shows them', () => {
		expect(d.releaseOptions(rel, 'skills-2026-11-16')).toEqual([
			{ label: 'skills 2026-11-16 (latest)', value: 'skills-2026-11-16' },
			{ label: 'skills 2026-11-02', value: 'skills-2026-11-02' },
		]);
	});
	it('keeps a current tag that the list no longer holds', () => {
		expect(d.releaseOptions(rel, 'skills-2026-10-01')[2]).toEqual({ label: 'skills 2026-10-01', value: 'skills-2026-10-01' });
	});
	it('defaults to the latest tag', () => {
		expect(d.defaultRelease(rel)).toBe('skills-2026-11-16');
	});
	it('defaults to empty with no releases', () => {
		expect(d.defaultRelease([])).toBe('');
	});
});

describe('validatePolicy', () => {
	it('requires a name for a new policy', () => {
		expect(d.validatePolicy(form({ policy_name: '  ' }), true)).toBe('Give the policy a name.');
	});
	it('refuses a name over 140 characters', () => {
		expect(d.validatePolicy(form({ policy_name: 'x'.repeat(141) }), true)).toBe('The policy name is too long.');
	});
	it('requires a release', () => {
		expect(d.validatePolicy(form({ rules_release: '' }), false)).toBe('Pick a rules and skills release.');
	});
	it('requires three models on the gateway route', () => {
		expect(d.validatePolicy(form({ model_hard: '' }), false)).toBe('Pick a Light, Normal and Hard model.');
	});
	it('needs no models on the Own Max route', () => {
		const f = form({ route: 'Own Claude Max, direct', model_light: '', model_normal: '', model_hard: '' });
		expect(d.validatePolicy(f, false)).toBe('');
	});
	it('does not ask for a name when editing', () => {
		expect(d.validatePolicy(form({ policy_name: '' }), false)).toBe('');
	});
	it('accepts a complete policy', () => {
		expect(d.validatePolicy(form(), true)).toBe('');
	});
});

describe('savePayload', () => {
	it('builds the save_policy arguments for a new gateway policy', () => {
		const p = d.savePayload(form({ policy_name: ' Standard ', allowed_actions: 'Read\n\n  Bash(git status)  \n', blocked_actions: '' }), true);
		expect(p).toEqual({
			policy_name: 'Standard',
			permission_mode: 'Ask before acting',
			route: 'Through our gateway',
			model_light: 'fast',
			model_normal: 'deepseek-chat',
			model_hard: 'deepseek-reasoner',
			allowed_actions: 'Read\nBash(git status)',
			blocked_actions: '',
			rules_release: 'skills-2026-11-16',
			is_new: 1,
		});
	});
	it('sends null models on the Own Max route and is_new 0 when editing', () => {
		const p = d.savePayload(form({ route: 'Own Claude Max, direct' }), false);
		expect(p.model_light).toBeNull();
		expect(p.model_normal).toBeNull();
		expect(p.model_hard).toBeNull();
		expect(p.is_new).toBe(0);
	});
});

describe('labels', () => {
	it('shows the Hard model, or a note for Own Max', () => {
		expect(d.hardModelLabel({ route: 'Through our gateway', model_hard: 'deepseek-reasoner' })).toBe('deepseek-reasoner');
		expect(d.hardModelLabel({ route: 'Own Claude Max, direct', model_hard: '' })).toBe("from the person's Max");
	});
	it('words the save message by the number of seats', () => {
		expect(d.savedMessage({ seats_queued: 0 })).toBe('Policy saved.');
		expect(d.savedMessage({ seats_queued: 1 })).toBe('Policy saved. 1 seat updates within a minute.');
		expect(d.savedMessage({ seats_queued: 14 })).toBe('Policy saved. 14 seats update within a minute.');
	});
});

describe('seat policy helpers', () => {
	const sites = [{ site: 'basher.example-co.sanadeoi.mvpstorm.com', label: 'Basher', default_policy: 'Standard' }, { site: 'other.example.com', label: 'Other', default_policy: null }];
	it('shows the seat policy first', () => {
		expect(d.seatPolicyLabel({ policy: 'Senior', subscription: 'basher.example-co.sanadeoi.mvpstorm.com' }, sites)).toBe('Senior');
	});
	it('falls back to the site default and says so', () => {
		expect(d.seatPolicyLabel({ policy: null, subscription: 'basher.example-co.sanadeoi.mvpstorm.com' }, sites)).toBe('Standard (site default)');
	});
	it('shows none when nothing applies', () => {
		expect(d.seatPolicyLabel({ policy: null, subscription: 'other.example.com' }, sites)).toBe('none');
		expect(d.seatPolicyLabel({ subscription: 'unknown.example.com' }, [])).toBe('none');
	});
	it('builds select options with a sentinel for no policy', () => {
		expect(d.choiceOptions([{ name: 'Standard' }, { name: 'Senior (no prompts)' }], 'None')).toEqual([
			{ label: 'None', value: '__none__' },
			{ label: 'Standard', value: 'Standard' },
			{ label: 'Senior (no prompts)', value: 'Senior (no prompts)' },
		]);
	});
	it('converts between the sentinel and the empty policy', () => {
		expect(d.toChoice('')).toBe('__none__');
		expect(d.toChoice(null)).toBe('__none__');
		expect(d.toChoice('Standard')).toBe('Standard');
		expect(d.fromChoice('__none__')).toBe('');
		expect(d.fromChoice('Standard')).toBe('Standard');
	});
});

describe('manageSeatArgs', () => {
	const m = { name: 'AGSEAT-00012', tier_access: 'fast', monthly_budget_usd: 20, policy: '__none__', policy_initial: '__none__' };
	it('leaves the policy out when it did not change', () => {
		expect(d.manageSeatArgs(m, 'update')).toEqual({ seat: 'AGSEAT-00012', action: 'update', tier_access: 'fast', monthly_budget_usd: 20 });
	});
	it('sends the new policy, and an empty string to clear it', () => {
		expect(d.manageSeatArgs({ ...m, policy: 'Standard' }, 'update').policy).toBe('Standard');
		expect(d.manageSeatArgs({ ...m, policy: '__none__', policy_initial: 'Standard' }, 'update').policy).toBe('');
	});
	it('never sends a policy with revoke', () => {
		expect(d.manageSeatArgs({ ...m, policy: 'Standard' }, 'revoke').policy).toBeUndefined();
	});
});
