"""The sites a bench_deploy_and_update acts on, in one place: the tool updates them and call_guard checks them.

It lives in scope/ so the guard does not import the tool it guards (0.7.52; 0.7.49 had it in deploy_update.py).
"""

from __future__ import annotations

import json

import frappe


def chosen_sites(name: str, sites) -> list:
	"""The named Active sites of Release Group `name`, or, when `sites` is left out, the calling team's Active sites
	on it ([] means none). A shared group can hold other teams' sites; left out, they are not picked (0.7.52), so the
	guard has nothing to refuse. Named sites stay as given: the guard refuses one of another team."""
	sites = _as_names(sites)
	filters = {"group": name, "status": "Active"}
	if sites is None:
		filters["team"] = _calling_team()
	on_group = {
		s.name: s for s in frappe.get_all("Site", filters=filters, fields=["name", "server", "bench"])
	}
	if sites is None:
		return list(on_group.values())
	missing = [s for s in sites if s not in on_group]
	if missing:
		frappe.throw(f"not Active sites on {name}: {', '.join(missing)}", frappe.ValidationError)
	return [on_group[s] for s in sites]


def _as_names(sites) -> list[str] | None:
	if isinstance(sites, str):
		try:
			sites = json.loads(sites) if sites.lstrip().startswith("[") else ([sites] if sites else None)
		except ValueError:
			frappe.throw("sites must be a list of site names", frappe.ValidationError)
	if sites is not None and (not isinstance(sites, list) or not all(isinstance(s, str) for s in sites)):
		frappe.throw("sites must be a list of site names", frappe.ValidationError)
	return sites


def _calling_team() -> str | None:
	"""The MCP token's team (auth pins it for the call); outside MCP, the dashboard's current team."""
	team = getattr(frappe.local, "mcp_token_team", None)
	if team:
		return team
	from press.utils import get_current_team

	return get_current_team()
