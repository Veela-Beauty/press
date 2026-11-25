"""Keep an MCP call inside what the token's user may open on the dashboard.

teams.py and call_guard.py stop a token at its team's edge. A member whose Press Role lists only some benches and
sites (DevOps L1, Viewer) must also stop at that list, as the dashboard does, or a token he mints reaches the whole
team. So every Site, Release Group and Server a call names or reaches goes through the dashboard's own
role_guard.check. Both functions run as the token's user, with the token's team pinned.
"""

from __future__ import annotations

from typing import Any

import frappe

from press.guards import role_guard
from press.guards.role_guard.document import documents, has_user_permission
from press.mcp_server.scope.call_guard import _CANDIDATE_ARGS, _RG_ARGS, _benches_of_call, _sites_of_call
from press.mcp_server.scope.sites import chosen_sites
from press.mcp_server.scope.targets import _candidate_to_release_group, _extract_target
from press.mcp_server.scope.teams import not_visible

# A dashboard login minted for the team's test user sees the whole team.
_WHOLE_TEAM_TOOLS = frozenset({"mint_dashboard_login_url"})
_LIST_TOOLS = {"list_sites": "Site", "list_release_groups": "Release Group"}


def is_limited() -> bool:
	"""True when the session user sees only what his roles list (not the owner, an admin or a System Manager)."""
	return role_guard.is_restricted() and not role_guard.skip_roles()


def assert_call_in_roles(tool: str, args: dict) -> None:
	if not is_limited():
		return
	if tool in _WHOLE_TEAM_TOOLS:
		raise frappe.PermissionError(
			f"{tool} reaches the whole team; your role covers only the benches and sites it lists"
		)
	for doctype, names in _resources_of_call(tool, args).items():
		for name in sorted(names):
			if not role_guard.check(doctype, name):
				raise frappe.PermissionError(not_visible(doctype, name))


def filter_to_roles(tool: str, response: Any) -> Any:
	"""Drop rows a limited user may not see from the list tools that read the whole team."""
	if not is_limited():
		return response
	if tool in _LIST_TOOLS and isinstance(response, list):
		allowed = _visible(_LIST_TOOLS[tool])
		return response if allowed is None else [r for r in response if _row_name(r) in allowed]
	if tool == "agent_job_list" and isinstance(response, list):
		sites, groups = _visible("Site"), _visible("Release Group")
		benches = {
			r["bench"] for r in response if isinstance(r, dict) and r.get("bench") and not r.get("site")
		}
		group_of = (
			dict(frappe.get_all("Bench", {"name": ("in", list(benches))}, ["name", "group"], as_list=True))
			if benches
			else {}
		)
		return [r for r in response if isinstance(r, dict) and _job_visible(r, sites, groups, group_of)]
	return response


def _resources_of_call(tool: str, args: dict) -> dict[str, set]:
	sites = set(_sites_of_call(tool, args))
	if tool == "bench_deploy_and_update" and args.get("name"):
		sites.update(s.name for s in chosen_sites(args["name"], args.get("sites")))
	groups = {args[arg] for arg in _RG_ARGS if args.get(arg)}
	groups.update(_candidate_to_release_group(args[arg]) for arg in _CANDIDATE_ARGS if args.get(arg))
	groups.update(frappe.db.get_value("Bench", bench, "group") for bench in _benches_of_call(args))
	doctype, name = _extract_target(tool, args)
	if doctype == "Release Group" and name:
		groups.add(name)
	servers = {args["server"]} if args.get("server") else set()
	if args.get("job_name"):
		job = (
			frappe.db.get_value("Agent Job", args["job_name"], ["site", "bench", "server"], as_dict=True)
			or {}
		)
		if job.get("bench"):
			groups.add(frappe.db.get_value("Bench", job["bench"], "group"))
		elif job.get("server") and not job.get("site"):
			servers.add(job["server"])
	return {"Site": sites - {None}, "Release Group": groups - {None}, "Server": servers - {None}}


def _visible(doctype: str) -> set | None:
	"""Names the user may open, or None when a role grants all of that doctype."""
	if has_user_permission(doctype):
		return None
	return set(documents(role_guard.base_query(), doctype))


def _row_name(row: Any) -> Any:
	return row.get("name") if isinstance(row, dict) else row


def _job_visible(row: dict, sites: set | None, groups: set | None, group_of: dict) -> bool:
	if row.get("site"):
		return sites is None or row["site"] in sites
	if row.get("bench"):
		return groups is None or group_of.get(row["bench"]) in groups
	return False
