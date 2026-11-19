// Pure view logic for the Sanad AI Policies tab and the policy fields on the Seats tab
// (tested in policies-derive.test.js).

export const PERMISSION_MODES = ['Ask before acting', 'Bypass, no prompts'];
export const ROUTES = ['Through our gateway', 'Own Claude Max, direct'];
export const OWN_MAX = 'Own Claude Max, direct';
export const PREVIEW_MODES = ['Full', 'Sealed'];
// frappe-ui Select drops options with an empty value, so "no policy" travels as this value.
export const NONE = '__none__';
export const MODEL_SLOTS = [
	{ key: 'model_light', label: 'Light model', hint: "Claude Code's small, fast model slot" },
	{ key: 'model_normal', label: 'Normal model', hint: "Claude Code's default model slot" },
	{ key: 'model_hard', label: 'Hard model', hint: "Claude Code's strongest model slot" },
];

export const emptyPolicy = () => ({
	policy_name: '',
	permission_mode: PERMISSION_MODES[0],
	route: ROUTES[0],
	preview_mode: PREVIEW_MODES[0],
	model_light: '',
	model_normal: '',
	model_hard: '',
	allowed_actions: '',
	blocked_actions: '',
	rules_release: '',
});

export const fromServer = (p = {}) => {
	const f = emptyPolicy();
	Object.keys(f).forEach((k) => {
		if (p[k] != null) f[k] = p[k];
	});
	return f;
};

export const isOwnMax = (form) => form.route === OWN_MAX;

export const tagLabel = (tag) => String(tag || '').replace(/^skills-/, 'skills ');

export const modelOptions = (models = [], current = '') => {
	const opts = models.map((m) => ({ label: m.name, value: m.name }));
	if (current && !models.some((m) => m.name === current)) {
		opts.push({ label: `${current} (not served now)`, value: current });
	}
	return opts;
};

export const releaseOptions = (releases = [], current = '') => {
	const opts = releases.map((r) => ({ label: tagLabel(r.tag) + (r.latest ? ' (latest)' : ''), value: r.tag }));
	if (current && !releases.some((r) => r.tag === current)) {
		opts.push({ label: tagLabel(current), value: current });
	}
	return opts;
};

export const defaultRelease = (releases = []) => (releases.find((r) => r.latest) || releases[0] || {}).tag || '';

export const policyErrors = (form, isNew) => {
	const e = {};
	const name = (form.policy_name || '').trim();
	if (isNew && !name) e.name = 'Give the policy a name.';
	else if (isNew && name.length > 140) e.name = 'The policy name is too long.';
	if (!form.rules_release) e.release = 'Pick a rules and skills release.';
	if (!isOwnMax(form) && !(form.model_light && form.model_normal && form.model_hard)) {
		e.models = 'Pick a Light, Normal and Hard model.';
	}
	return e;
};

export const validatePolicy = (form, isNew) => {
	const e = policyErrors(form, isNew);
	return e.name || e.release || e.models || '';
};

const cleanLines = (text) =>
	String(text || '')
		.split(/\r?\n/)
		.map((l) => l.trim())
		.filter(Boolean)
		.join('\n');

export const savePayload = (form, isNew) => {
	const own = isOwnMax(form);
	return {
		policy_name: (form.policy_name || '').trim(),
		permission_mode: form.permission_mode,
		route: form.route,
		preview_mode: form.preview_mode,
		model_light: own ? null : form.model_light,
		model_normal: own ? null : form.model_normal,
		model_hard: own ? null : form.model_hard,
		allowed_actions: cleanLines(form.allowed_actions),
		blocked_actions: cleanLines(form.blocked_actions),
		rules_release: form.rules_release,
		is_new: isNew ? 1 : 0,
	};
};

export const hardModelLabel = (p) => (p.route === OWN_MAX ? "from the person's Max" : p.model_hard || '');

export const savedMessage = (result) => {
	const n = Number((result && result.seats_queued) || 0);
	if (!n) return 'Policy saved.';
	return `Policy saved. ${n} ${n === 1 ? 'seat updates' : 'seats update'} within a minute.`;
};

export const siteDefaultFor = (seat, sites = []) =>
	(sites.find((s) => s.site === seat.subscription) || {}).default_policy || '';

export const seatPolicyLabel = (seat, sites = []) => {
	if (seat.policy) return seat.policy;
	const d = siteDefaultFor(seat, sites);
	return d ? `${d} (site default)` : 'none';
};

export const choiceOptions = (policies = [], noneLabel = 'None') => [
	{ label: noneLabel, value: NONE },
	...policies.map((p) => ({ label: p.name, value: p.name })),
];

export const toChoice = (name) => name || NONE;
export const fromChoice = (value) => (value === NONE ? '' : value);

export const manageSeatArgs = (m, action) => {
	const args = { seat: m.name, action, tier_access: m.tier_access, monthly_budget_usd: m.monthly_budget_usd };
	if (action === 'update' && m.policy !== m.policy_initial) args.policy = fromChoice(m.policy);
	return args;
};

// A Claude subscription token (`claude setup-token`) is for one person: the Providers form then asks "Only for (person)".
// The prefix is the one the control center and the gateway use.
export const isSubscriptionToken = (key) => String(key || '').trim().startsWith('sk-ant-oat');

export const seatChoices = (seats = []) =>
	(seats || [])
		.filter((s) => s.status !== 'revoked')
		.map((s) => ({ label: `${s.user} (${s.subscription})`, value: s.name }));
