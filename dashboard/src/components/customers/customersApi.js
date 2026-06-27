/**
 * Thin API layer for the Customers section (the AccuHub customer-account hub).
 *
 * Mirrors tesseraApi.js: every helper uses frappe-ui's `call()` to POST to
 * /api/method/tessera_server.customers_api.<fn> and returns the `message`. Those
 * methods are System-Manager gated and proxy server-side to the AccuHub ERPNext
 * site (apps + hosting plan + payment + usage), so the dashboard calls them directly.
 */
import { call } from 'frappe-ui';

const API = 'tessera_server.customers_api';

export const overview = (company) => call(`${API}.overview`, company ? { company } : {});
export const listCompanies = () => call(`${API}.companies`);
export const listCustomers = (company, search) =>
	call(`${API}.customers`, { company: company || undefined, search: search || undefined });
export const getCustomerAccount = (customer, company) =>
	call(`${API}.customer_account`, { customer, company: company || undefined });

// --- presentation helpers ---------------------------------------------------

// Map an app/subscription state to a frappe-ui Badge theme.
export function stateTheme(state) {
	switch (state) {
		case 'Active':
			return 'green';
		case 'Trial':
			return 'blue';
		case 'Suspended':
			return 'orange';
		case 'Cancelled':
			return 'red';
		default:
			return 'gray';
	}
}

// Colour for a usage-meter bar by percent used (>=100 red, >=80 orange, else green).
export function meterColor(pct) {
	if (pct >= 100) return 'bg-red-500';
	if (pct >= 80) return 'bg-yellow-500';
	return 'bg-green-500';
}

// Format money with thousands separators; "-" on empty.
export function fmtMoney(value) {
	const n = Number(value || 0);
	return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
