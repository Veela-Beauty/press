import { call } from 'frappe-ui';

// frappe-ui's call() sends no X-Press-Team header, so the server would fall back to
// the user's oldest team. Send the team the dashboard is showing, as main.js does.
export default function teamCall(method, args) {
	const team = localStorage.getItem('current_team') || window.default_team;
	return call(method, args, team ? { headers: { 'X-Press-Team': team } } : {});
}
