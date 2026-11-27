import { createResource } from 'frappe-ui';

// Backend: press/api/messaging.py (owner only).
const base = 'press.api.messaging.';

export function call(method, params) {
	return new Promise((resolve, reject) => {
		const r = createResource({ url: base + method, onSuccess: resolve, onError: reject });
		r.submit(params);
	});
}

export const thisMonth = () => new Date().toISOString().slice(0, 7);
export const money = (v) =>
	Number(v || 0).toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const errorText = (e) => e?.messages?.join(', ') || e?.message || 'Something went wrong';

// "SA" reads "Saudi Arabia"; the catch-all row reads "Any other country".
const names = new Intl.DisplayNames(['en'], { type: 'region' });
export const countryName = (code) => {
	if (code === 'default') return 'Any other country';
	try {
		return names.of(code) || code;
	} catch {
		return code;
	}
};
