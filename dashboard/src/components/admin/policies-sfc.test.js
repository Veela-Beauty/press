import { readFileSync } from 'fs';
import { resolve } from 'path';
import { describe, it, expect } from 'vitest';
import { parse, compileTemplate } from '@vue/compiler-sfc';

// Run from the dashboard folder (yarn vitest run): paths are relative to dashboard/src.
const read = (rel) => readFileSync(resolve(process.cwd(), 'src', rel), 'utf8');
const compile = (rel) => {
	const src = read(rel);
	const { descriptor, errors } = parse(src, { filename: rel });
	const tpl = compileTemplate({ source: descriptor.template.content, filename: rel, id: rel });
	return { src, descriptor, parseErrors: errors, templateErrors: tpl.errors };
};

describe('AiPolicyForm.vue', () => {
	it('parses and its template compiles', () => {
		const r = compile('components/admin/AiPolicyForm.vue');
		expect(r.parseErrors).toEqual([]);
		expect(r.templateErrors).toEqual([]);
		expect(r.descriptor.script).toBeTruthy();
	});
	it('calls the documented control center methods and no long dash', () => {
		const { src } = compile('components/admin/AiPolicyForm.vue');
		['list_serving_models', 'list_releases', 'get_policy', 'save_policy'].forEach((m) => expect(src).toContain(m));
		expect(src).not.toMatch(/[\u2013\u2014]/);
	});
	it('words the blocked actions as guard rails, not as unbreakable rules', () => {
		const { src } = compile('components/admin/AiPolicyForm.vue');
		expect(src).toContain('Always enforced against standard users and user-level processes, also with bypass on. A local administrator can still change them.');
		expect(src).not.toContain('cannot override');
	});
});

describe('AiPolicies.vue', () => {
	it('parses and its template compiles', () => {
		const r = compile('components/admin/AiPolicies.vue');
		expect(r.parseErrors).toEqual([]);
		expect(r.templateErrors).toEqual([]);
		expect(r.descriptor.script).toBeTruthy();
	});
	it('loads list_policies, shows the New policy button and mounts the form', () => {
		const { src } = compile('components/admin/AiPolicies.vue');
		expect(src).toContain('list_policies');
		expect(src).toContain('>New policy</Button>');
		expect(src).toContain('<AiPolicyForm');
		expect(src).toContain('loading: true');
		expect(src).not.toMatch(/[\u2013\u2014]/);
	});
});

describe('AdminPanel.vue', () => {
	it('parses and its template compiles', () => {
		const r = compile('pages/AdminPanel.vue');
		expect(r.parseErrors).toEqual([]);
		expect(r.templateErrors).toEqual([]);
	});
	it('registers the Policies tab after Providers and labels the group Sanad AI', () => {
		const src = read('pages/AdminPanel.vue');
		expect(src).toContain("import AiPolicies from '../components/admin/AiPolicies.vue';");
		expect(src).toMatch(/AiProviders, AiPolicies, AiSubscriptions/);
		expect(src).toMatch(/\{ id: 'providers'[^\n]*\n\t*\{ id: 'policies', label: 'Policies'/);
		expect(src).toContain("<template v-if=\"activeMainTab === 'policies'\">");
		expect(src).toMatch(/const ai = \[[^\]]*'policies'[^\]]*\]/);
	});
});

describe('NavigationItems.vue', () => {
	it('the Sanad AI sidebar lists Policies and highlights the group on it', () => {
		const src = read('components/NavigationItems.vue');
		expect(src).toContain("route: '/admin/policies'");
		expect(src).toMatch(/\['analytics'[^\]]*'policies'[^\]]*\]\.includes\(adminTab\)/);
	});
});
