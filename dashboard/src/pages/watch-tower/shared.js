// Watch Tower pages (prototype ACM-SP-03): colours, badges and time helpers shared by Overview and Client.
// Colours checked with the dataviz validate_palette.js (light): clients = slots 1-3 + violet for Other; severity is
// ordered red > amber > violet > blue. Both sets PASS.
export const CLIENT_COLORS = ['#2a78d6', '#eb6834', '#1baf7a'];
export const OTHER_COLOR = '#4a3aa7';
export const SEVERITY_COLORS = { Critical: '#d03b3b', High: '#eda100', Medium: '#4a3aa7', Low: '#2a78d6' };
export const REST_COLOR = '#c2c6cb'; // the remainder part of a mini bar, not a series
export const STATUS_CLASS = { Connected: 'b-green', Silent: 'b-amber', Revoked: 'b-red', Paused: 'b-red', New: 'b-gray' };
export const ENV_CLASS = { Production: 'b-blue', Staging: 'b-gray', Dev: 'b-gray', 'Not set': 'b-gray' };
export const SEVERITY_CLASS = { Critical: 'b-red', High: 'b-amber', Medium: 'b-gray', Low: 'b-gray' };
// users against the User Cap (prototype ACM-SP-06): a word always goes with the colour
export const CAP_CLASS = { 'Near cap': 'near', 'Over cap': 'over' };
export const seats = (users) => (users.cap ? `${users.enabled} / ${users.cap}` : `${users.enabled}`);

export const clientColor = (index) => (index < CLIENT_COLORS.length ? CLIENT_COLORS[index] : OTHER_COLOR);

// times come from the hub's own clock (as_of is from the same server), so the browser's time zone never skews them;
// microseconds are cut because not every browser parses them
const at = (value) => Date.parse(String(value).slice(0, 19).replace(' ', 'T'));
export function ago(asOf, when) {
	if (!when) return 'never';
	const minutes = Math.round((at(asOf) - at(when)) / 60000);
	if (minutes < 1) return 'just now';
	if (minutes < 60) return `${minutes} min ago`;
	if (minutes < 1440) return `${Math.round(minutes / 60)} h ago`;
	return `${Math.round(minutes / 1440)} d ago`;
}

export const shortDay = (day) => `${day.slice(8, 10)}/${day.slice(5, 7)}`;
// "23/11 14:05" from the client's "2026-11-23 14:05:12" (a check's since)
export const shortTime = (when) => `${shortDay(String(when))} ${String(when).slice(11, 16)}`;
// a client's checks (prototype ACM-SP-07): the failing ones, and the row's line for them
export const failingChecks = (site) => (site.checks || []).filter((c) => !c.ok);
export const failingText = (site) => {
	const names = site.failing_checks || [];
	return names.length === 1 ? `${names[0]} failing` : `${names.length} checks failing`;
};

// "24 h ago: 3" coloured by direction: more open findings is worse
export function versus(now, before, label, lowerIsBetter = true) {
	if (before === null || before === undefined) return { text: '', tone: '' };
	const tone = now === before ? '' : (now < before) === lowerIsBetter ? 'down' : 'up';
	return { text: `${label}: ${before}`, tone };
}
