"""Drop other teams' rows from MCP responses whose handler queries without a team filter.

These handlers use frappe.get_all, which ignores permissions, so their results span
every team. Filtering the response keeps the handlers untouched.
"""

from __future__ import annotations

from typing import Any

import frappe

from press.mcp_server.scope.call_guard import job_team
from press.mcp_server.scope.teams import not_visible


def filter_to_team(tool: str, response: Any, team: str) -> Any:
	if tool == "agent_job_list" and isinstance(response, list):
		return [row for row in response if job_team(row) == team]
	if tool == "list_pending_releases" and isinstance(response, dict):
		releases = [r for r in response.get("releases") or [] if _release_visible(r, team)]
		return {**response, "releases": releases, "count": len(releases)}
	if tool == "register_existing_app" and isinstance(response, dict) and response.get("already_exists"):
		# The duplicate lookup is not team-filtered; never hand back another team's source.
		source = response.get("app_source") or response.get("name")
		if source and frappe.db.get_value("App Source", source, "team") != team:
			raise frappe.PermissionError(not_visible("App Source", source))
	return response


def _release_visible(row: dict, team: str) -> bool:
	source = frappe.db.get_value("App Source", row.get("source"), ["team", "public"], as_dict=True)
	return bool(source) and (source.team == team or bool(source.public))
