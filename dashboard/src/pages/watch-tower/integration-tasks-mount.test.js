// @vitest-environment jsdom
// The AccuHub tasks page as a tree (prototype ACH-SP-06), mounted with the hub's answer stubbed.
import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { createRouter, createMemoryHistory } from 'vue-router';

const answer = (globalThis.__wtTasks = { data: null });
vi.mock('frappe-ui', () => ({
	createResource: () => reactive({ data: globalThis.__wtTasks.data, loading: false, error: null, reload() {} }),
}));

// imported after the mocks: this vitest (0.9) does not hoist vi.mock above static imports
const { default: IntegrationTasks } = await import('./IntegrationTasks.vue');

const row = (task, extra) => ({ task, title: 'SlfStg2', project: 'PROJ-0002', url: `https://erp/app/task/${task}`, ...extra });
// a real router: this vitest (0.9) does not apply vi.mock to node_modules imports
const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', name: 'Watch Tower Integration Tasks', component: {} }] });
await router.push('/watch-tower/integrations/erp?stage=backlog');
const page = (rows) => {
	answer.data = { client_name: 'OptiFlow', read_at: '2026-11-25 17:54:00', projects: [], counts: { backlog: 2, optiflow: 0, accurate: 0, closed: 1 }, rows };
	return mount(IntegrationTasks, {
		props: { site: 'erp' },
		global: { plugins: [router], stubs: { Header: true, Breadcrumbs: true, 'lucide-folder': { template: '<i class="folder" />' } } },
	});
};

describe('AccuHub tasks as a tree', () => {
	const w = page([
		row('TASK-2', { subject: 'SlfStg2 : Self Storage', accuhub_state: 'Planned', is_group: true, in_stage: false, depth: 0 }),
		row('TASK-3', { subject: 'SlfStg2 : Website Integration Phase 1', accuhub_state: 'Sent to Developer', is_group: true, in_stage: true, depth: 1, modified: '2026-11-25 13:01:01', created_by: 'Abdulrahman Mohamed', created_on: '2026-11-23 09:00:00' }),
		row('TASK-4', { subject: '1. Price and Discount', accuhub_state: 'Sent to Developer', in_stage: true, depth: 2, modified: '2026-11-24 14:32:21', created_by: 'Abdulrahman Mohamed', created_on: '2026-11-23 13:26:01', assigned_on: '2026-11-25 09:30:00', developer: 'Marco Maher' }),
	]);
	const rows = w.findAll('tbody tr');

	it('has the three new columns before Last change', () => {
		expect(w.findAll('thead th').map((th) => th.text())).toEqual(['Task', 'Project', 'Developer', 'AccuHub state', 'Created by', 'Created on', 'Assigned on', 'Last change']);
	});
	it('a group not in the stage is a grey heading with only its title, project and state', () => {
		expect(rows[0].classes()).toContain('head');
		expect(rows[0].findAll('td').map((td) => td.text())).toEqual(['SlfStg2 : Self Storage', 'SlfStg2', '', 'Planned', '', '', '', '']);
	});
	it('children sit indented under their group, groups carry the folder', () => {
		expect(rows.map((r) => r.find('.cell').attributes('style'))).toEqual(['padding-inline-start: 0px;', 'padding-inline-start: 20px;', 'padding-inline-start: 40px;']);
		expect(w.findAll('i.folder')).toHaveLength(2);
	});
	it('shows who made it, when, and when the developer got it', () => {
		expect(rows[2].findAll('td').map((td) => td.text())).toEqual(['1. Price and Discount', 'SlfStg2', 'Marco Maher', 'Sent to Developer', 'Abdulrahman Mohamed', '23 Nov', '25 Nov', '24 Nov, 14:32']);
		expect(rows[1].findAll('td')[2].text()).toBe('Not assigned');
	});
});

describe('a link older than 0.6.0', () => {
	it('stays a flat list of tasks with the new columns empty', () => {
		const w = page([row('TASK-9', { subject: 'Old row', accuhub_state: 'Sent to Developer', modified: '2026-11-24 14:32:21' })]);
		const tr = w.find('tbody tr');
		expect(tr.classes()).not.toContain('head');
		expect(tr.findAll('td').map((td) => td.text())).toEqual(['Old row', 'SlfStg2', 'Not assigned', 'Sent to Developer', '', '', '', '24 Nov, 14:32']);
	});
});
