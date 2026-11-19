// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { h } from 'vue';

const calls = (globalThis.__policyCalls = { handler: null });

vi.mock('frappe-ui', () => ({
	call: (method, args) => globalThis.__policyCalls.handler(method, args),
	Button: { emits: ['click'], render() { return h('button', { onClick: (e) => this.$emit('click', e) }, this.$slots.default?.()); } },
	FormControl: {
		inheritAttrs: false,
		props: ['label', 'modelValue', 'type', 'options'],
		emits: ['update:modelValue'],
		render() {
			const tag = this.type === 'select' ? 'select' : this.type === 'textarea' ? 'textarea' : 'input';
			return h('div', [
				h('label', this.label),
				h(tag, { ...this.$attrs, 'data-label': this.label, value: this.modelValue, onInput: (e) => this.$emit('update:modelValue', e.target.value) }),
			]);
		},
	},
}));
const toastMock = (globalThis.__toastMock = { error: vi.fn(), success: vi.fn(), warning: vi.fn() });
vi.mock('vue-sonner', () => ({ toast: globalThis.__toastMock }));

import { FormControl } from 'frappe-ui';
import AiPolicyForm from './AiPolicyForm.vue';

const serving = { models: [{ serves_as: 'fast' }] };
const respond = (releases) => (method) => {
	if (method.endsWith('list_serving_models')) return Promise.resolve(serving);
	if (method.endsWith('list_releases')) return releases instanceof Error ? Promise.reject(releases) : Promise.resolve({ releases });
	return Promise.resolve({});
};
const failed = () => Object.assign(new Error('x'), { messages: ['HTTP 417: no skills token configured yet'] });
const open = async (releases) => {
	calls.handler = respond(releases);
	const w = mount(AiPolicyForm, { attachTo: document.body });
	await flushPromises();
	return w;
};
const saveBtn = (w) => w.findAll('button').find((b) => b.text() === 'Save policy');

describe('AiPolicyForm mounted', () => {
	beforeEach(() => { document.body.innerHTML = ''; });

	it('a failed save shows the inline message tied to the name input, focuses it, and clears when filled', async () => {
		const w = await open([{ name: 'skills-1' }]);
		await saveBtn(w).trigger('click');
		await flushPromises();
		const msg = w.find('[role="alert"]');
		expect(msg.exists()).toBe(true);
		expect(msg.text()).toBe('Give the policy a name.');
		const input = w.find('[data-label="Policy name"]');
		expect(input.attributes('aria-invalid')).toBe('true');
		expect(input.attributes('aria-describedby')).toBe(msg.attributes('id'));
		expect(document.activeElement).toBe(input.element);
		await input.setValue('Standard');
		await flushPromises();
		expect(w.text()).not.toContain('Give the policy a name.');
		expect(w.find('[data-label="Policy name"]').attributes('aria-invalid')).toBeUndefined();
		w.unmount();
	});

	it('with the release list failed and no release set: the note and the server cause show, Save stays refused', async () => {
		const w = await open(failed());
		expect(w.text()).toContain('No skills releases available yet. Ask the control center admin to configure the skills release token.');
		expect(w.text()).toContain('HTTP 417: no skills token configured yet');
		await w.find('[data-label="Policy name"]').setValue('Standard');
		await saveBtn(w).trigger('click');
		await flushPromises();
		expect(w.text()).toContain('Pick a rules and skills release.');
		w.unmount();
	});

	it('when editing a policy with a saved release and the list failed: no "none available" note, only the server text', async () => {
		calls.handler = (method) => {
			if (method.endsWith('list_releases')) return Promise.reject(failed());
			if (method.endsWith('get_policy')) return Promise.resolve({ policy_name: 'Std', rules_release: 'skills-1', permission_mode: 'Ask before acting', route: 'Through our gateway', model_light: 'fast', model_normal: 'fast', model_hard: 'fast' });
			return Promise.resolve({ models: [] });
		};
		const w = mount(AiPolicyForm, { props: { name: 'Std' }, attachTo: document.body });
		await flushPromises();
		expect(w.text()).not.toContain('No skills releases available yet');
		expect(w.text()).toContain('HTTP 417: no skills token configured yet');
		w.unmount();
	});

	it('Web page previews shows the saved Sealed and Save sends the new choice', async () => {
		let sent = null;
		calls.handler = (method, args) => {
			if (method.endsWith('list_releases')) return Promise.resolve({ releases: [{ name: 'skills-1' }] });
			if (method.endsWith('get_policy')) return Promise.resolve({ policy_name: 'Std', rules_release: 'skills-1', permission_mode: 'Ask before acting', route: 'Through our gateway', preview_mode: 'Sealed', model_light: 'fast', model_normal: 'fast', model_hard: 'fast' });
			if (method.endsWith('save_policy')) { sent = args; return Promise.resolve({ ok: true, seats_queued: 0 }); }
			return Promise.resolve(serving);
		};
		const w = mount(AiPolicyForm, { props: { name: 'Std' }, attachTo: document.body });
		await flushPromises();
		const control = w.findAllComponents(FormControl).find((c) => c.props('label') === 'Web page previews');
		expect(control.props('type')).toBe('select');
		expect(control.props('options')).toEqual(['Full', 'Sealed']);
		expect(control.props('modelValue')).toBe('Sealed');
		control.vm.$emit('update:modelValue', 'Full');
		await flushPromises();
		await saveBtn(w).trigger('click');
		await flushPromises();
		expect(sent.preview_mode).toBe('Full');
		w.unmount();
	});

	it('a saved policy that lists a one-person model shows the control center warning', async () => {
		toastMock.warning.mockClear();
		calls.handler = (method) => {
			if (method.endsWith('list_releases')) return Promise.resolve({ releases: [{ name: 'skills-1' }] });
			if (method.endsWith('get_policy')) return Promise.resolve({ policy_name: 'Std', rules_release: 'skills-1', permission_mode: 'Ask before acting', route: 'Through our gateway', model_light: 'fast', model_normal: 'fast', model_hard: 'claude-opus-own' });
			if (method.endsWith('save_policy')) return Promise.resolve({ ok: true, seats_queued: 2, warnings: ['Model claude-opus-own is for one person only. 2 seats using this policy will be refused it (403) unless it is that person.'] });
			return Promise.resolve({ models: [{ serves_as: 'fast' }, { serves_as: 'claude-opus-own' }] });
		};
		const w = mount(AiPolicyForm, { props: { name: 'Std' }, attachTo: document.body });
		await flushPromises();
		await saveBtn(w).trigger('click');
		await flushPromises();
		expect(toastMock.warning).toHaveBeenCalledTimes(1);
		expect(toastMock.warning.mock.calls[0][0]).toContain('for one person only');
		w.unmount();
	});

	it('focuses the first invalid field in toast order: name, then release, then models', async () => {
		const w = await open([]);
		await w.find('[data-label="Policy name"]').setValue('Standard');
		await saveBtn(w).trigger('click');
		await flushPromises();
		expect(document.activeElement).toBe(w.find('[data-label="Rules and skills release"]').element);
		expect(w.find('#policy-err-models').classes()).toContain('mt-1');
		w.unmount();
	});
});
