/**
 * Thin API layer for the Tessera License Manager admin section.
 *
 * Mirrors the AdminPanel pattern: every helper uses frappe-ui's `call()` to
 * POST to /api/method/tessera_server.<module>.<fn> and returns the `message`
 * payload. The whitelisted methods are System-Manager-gated server-side, so
 * the dashboard calls them directly (the desk user is already authenticated).
 */
import { call } from 'frappe-ui';

const READER = 'tessera_server.dashboard_api';
const LICENSING = 'tessera_server.licensing';

// --- readers (dashboard_api.py) ---------------------------------------------
export const overview = () => call(`${READER}.overview`);
export const listLicenses = () => call(`${READER}.list_licenses`);
export const listHeartbeat = () => call(`${READER}.list_heartbeat`);
export const getLicense = (name) => call(`${READER}.get_license`, { name });

// --- mutations (licensing.py) -----------------------------------------------
export const issueLicense = (payload) => call(`${LICENSING}.issue_license`, payload);
export const renewLicense = (key, expires_on) =>
	call(`${LICENSING}.renew`, { key, expires_on });
export const revokeLicense = (key) => call(`${LICENSING}.revoke`, { key });
export const generateOfflineFile = (key) =>
	call(`${LICENSING}.generate_offline_file`, { key });
export const addSeat = (key, email) => call(`${LICENSING}.add_seat`, { key, email });
export const removeSeat = (key, email) => call(`${LICENSING}.remove_seat`, { key, email });

// --- presentation helpers ---------------------------------------------------

// Map a master-license status to a frappe-ui Badge theme + label.
export function statusTheme(status) {
	switch (status) {
		case 'Active':
			return { theme: 'green', label: 'Active' };
		case 'Suspended':
			return { theme: 'orange', label: 'Grace' };
		case 'Expired':
			return { theme: 'gray', label: 'Expired' };
		case 'Revoked':
			return { theme: 'red', label: 'Revoked' };
		default:
			return { theme: 'gray', label: status || 'Draft' };
	}
}

// "2027-03-01 00:00:00" -> "01 Mar 2027"; passthrough on bad input.
export function fmtDate(value) {
	if (!value) return '-';
	const d = new Date(String(value).replace(' ', 'T'));
	if (Number.isNaN(d.getTime())) return String(value);
	const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
	const dd = String(d.getDate()).padStart(2, '0');
	return `${dd} ${months[d.getMonth()]} ${d.getFullYear()}`;
}

// Group flat license rows by site_url, site-wide (blank company) row first.
export function groupBySite(rows) {
	const map = new Map();
	for (const r of rows) {
		const key = r.site_url || '(no site)';
		if (!map.has(key)) map.set(key, []);
		map.get(key).push(r);
	}
	const out = [];
	for (const [site, members] of map) {
		members.sort((a, b) => (a.company ? 1 : 0) - (b.company ? 1 : 0));
		out.push({ site, members });
	}
	return out;
}
