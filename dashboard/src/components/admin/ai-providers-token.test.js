// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { h } from 'vue';
import { isSubscriptionToken, seatChoices } from './policies-derive';

const calls = (globalThis.__providerCalls = { log: [], handler: null });

vi.mock('frappe-ui', () => ({
	call: (method, args) => { globalThis.__providerCalls.log.push([method, args]); return globalThis.__providerCalls.handler(method, args); },
	Dialog: { props: ['modelValue'], render() { return this.modelValue ? h('div', [this.$slots['body-content']?.(), this.$slots.actions?.()]) : null; } },
	Button: { emits: ['click'], render() { return h('button', { onClick: (e) => this.$emit('click', e) }, this.$slots.default?.()); } },
	FormControl: {
		inheritAttrs: false,
		props: ['label', 'modelValue', 'type', 'options'],
		emits: ['update:modelValue'],
		render() {
			const tag = this.type === 'select' ? 'select' : 'input';
			return h('div', [
				h('label', this.label),
				h(tag, { 'data-label': this.label, value: this.modelValue, onInput: (e) => this.$emit('update:modelValue', e.target.value) },
					(this.options || []).map((o) => h('option', { value: o.value }, o.label))),
			]);
		},
	},
}));
vi.mock('vue-sonner', () => ({ toast: { error: (...a) => globalThis.__toastErr?.(...a), success: () => {} } }));

import AiProviders from './AiProviders.vue';

const catalog = [{ provider_key: 'anthropic', label: 'Anthropic API', auth_class: 'api_key' }];
const seats = [
	{ name: 'AGSEAT-00001', user: 'owner@example.com', subscription: 'basher.example', status: 'active' },
	{ name: 'AGSEAT-00009', user: 'gone@example.com', subscription: 'basher.example', status: 'revoked' },
];
const handler = (method) => {
	if (method.endsWith('get_provider_catalog')) return Promise.resolve(catalog);
	if (method.endsWith('get_governance_overview')) return Promise.resolve({ seats });
	if (method.endsWith('get_accounts_overview')) return Promise.resolve({ groups: [] });
	if (method.endsWith('list_accounts')) return Promise.resolve([]);
	return Promise.resolve({});
};
const field = (w, label) => w.find(`[data-label="${label}"]`);
const open = async () => {
	calls.handler = handler;
	const w = mount(AiProviders, { attachTo: document.body });
	await flushPromises();
	await w.findAll('button').find((b) => b.text() === 'Add account').trigger('click');
	await flushPromises();
	return w;
};

describe('providers-token helpers', () => {
	it('detects a subscription token by prefix only', () => {
		expect(isSubscriptionToken('sk-ant-oat01-abc')).toBe(true);
		expect(isSubscriptionToken('  sk-ant-oat01-abc')).toBe(true);
		expect(isSubscriptionToken('sk-ant-api03-abc')).toBe(false);
		expect(isSubscriptionToken('')).toBe(false);
		expect(isSubscriptionToken(undefined)).toBe(false);
	});
	it('offers live seats as person and site, never a revoked seat', () => {
		expect(seatChoices(seats)).toEqual([{ label: 'owner@example.com (basher.example)', value: 'AGSEAT-00001' }]);
		expect(seatChoices(undefined)).toEqual([]);
	});
});

describe('AiProviders add account: Only for (person)', () => {
	beforeEach(() => { document.body.innerHTML = ''; calls.log.length = 0; });

	it('is hidden for an empty box and for an API key', async () => {
		const w = await open();
		expect(field(w, 'Only for (person)').exists()).toBe(false);
		await field(w, 'API key').setValue('sk-ant-api03-xyz');
		expect(field(w, 'Only for (person)').exists()).toBe(false);
	});

	it('appears for a token with a one-line hint and the live seats', async () => {
		const w = await open();
		await field(w, 'API key').setValue('sk-ant-oat01-xyz');
		await flushPromises();
		expect(field(w, 'Only for (person)').exists()).toBe(true);
		expect(w.text()).toContain('A subscription is for one person only.');
		expect(field(w, 'Only for (person)').findAll('option').map((o) => o.text())).toEqual(['owner@example.com (basher.example)']);
	});

	it('sends only_for_seat with a token, and not at all with an API key', async () => {
		const w = await open();
		await field(w, 'Serve as model').setValue('claude-opus-own');
		await field(w, 'API key').setValue('sk-ant-oat01-xyz');
		await flushPromises();
		await field(w, 'Only for (person)').setValue('AGSEAT-00001');
		await w.findAll('button').find((b) => b.text() === 'Test & connect').trigger('click');
		await flushPromises();
		const sent = calls.log.find(([m]) => m.endsWith('connect_account'))[1];
		expect(sent.only_for_seat).toBe('AGSEAT-00001');
		calls.log.length = 0;
		await w.findAll('button').find((b) => b.text() === 'Add account').trigger('click');
		await flushPromises();
		await field(w, 'Serve as model').setValue('claude-sonnet');
		await field(w, 'API key').setValue('sk-ant-api03-xyz');
		await w.findAll('button').find((b) => b.text() === 'Test & connect').trigger('click');
		await flushPromises();
		expect(calls.log.find(([m]) => m.endsWith('connect_account'))[1].only_for_seat).toBeUndefined();
	});

	it('a token without a person is not sent', async () => {
		const errors = [];
		globalThis.__toastErr = (m) => errors.push(m);
		const w = await open();
		await field(w, 'Serve as model').setValue('claude-opus-own');
		await field(w, 'API key').setValue('sk-ant-oat01-xyz');
		await flushPromises();
		await w.findAll('button').find((b) => b.text() === 'Test & connect').trigger('click');
		await flushPromises();
		expect(calls.log.some(([m]) => m.endsWith('connect_account'))).toBe(false);
		expect(errors.join(' ')).toContain('Only for (person)');
	});
});
