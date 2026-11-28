# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Edit a token's tools and read its history (PRS-SP-22).

Edit tools keeps the same token (nothing to copy again). Only the token's own user edits it; adding a tool needs a
Confirm it's you (press.mcp_server.token_confirm), removing only does not. A high-risk tool on a token without risky
tools turns them on, approved for a System User and pending otherwise, as at issue (press.mcp_server.auth).

Every change is one Press MCP Admin Action row (Issue, Reissue, Edit Tools, Copy Token, besides the admin's Revoke):
who, which token, what, and how they confirmed. The token's history reads those rows.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe.utils import get_fullname, now_datetime

from press.mcp_server import token_confirm
from press.mcp_server._util import safe_parse_list
from press.mcp_server.auth import _user_is_system
from press.mcp_server.tools import TOOLS

HISTORY_ROWS = 10


def log_token_action(
	action_type: str, token: str, what: str, how: str = "", context: dict | None = None
) -> None:
	frappe.get_doc(
		{
			"doctype": "Press MCP Admin Action",
			"action_type": action_type,
			"actor": frappe.session.user,
			"target_token": token,
			"reason": what,
			"context_json": json.dumps({**(context or {}), "how": how}),
		}
	).insert(ignore_permissions=True)


def _own_live_token(token_id: str):
	doc = frappe.db.get_value(
		"Press MCP Token",
		token_id,
		["name", "user", "label", "scope", "revoked", "expires_at", "risky_tools_enabled"],
		as_dict=True,
	)
	if not doc or doc.user != frappe.session.user:
		frappe.throw("Only the token's own user can change its tools.", frappe.PermissionError)
	if doc.revoked or (doc.expires_at and doc.expires_at < now_datetime()):
		frappe.throw("This token is revoked or expired: issue a new one instead.")
	return doc


def _label(tool: str) -> str:
	return TOOLS[tool].get("label") or tool


@frappe.whitelist(methods=["POST"])
def update_token_tools(token_id: str, scope: list | str) -> dict[str, Any]:
	"""Give a token a new list of tools. Same token; adding a tool needs a recent Confirm it's you."""
	doc = _own_live_token(token_id)
	new = list(dict.fromkeys(safe_parse_list(scope)))
	unknown = [t for t in new if t not in TOOLS]
	if unknown:
		frappe.throw(f"Unknown tools: {', '.join(unknown)}")
	if not new:
		frappe.throw("Choose at least one tool: an empty list would let the token call every tool.")
	old = safe_parse_list(doc.scope) or list(TOOLS)
	added = [t for t in new if t not in old]
	removed = [t for t in old if t not in new]
	if not added and not removed:
		return {"name": token_id, "added": [], "removed": [], "scope": new}

	how = token_confirm.confirmed_how() if added else "no confirm (only removed)"
	values = {"scope": json.dumps(new)}
	if not doc.risky_tools_enabled and any(TOOLS[t].get("risk") == "high" for t in added):
		values["risky_tools_enabled"] = 1
		values["approval_status"] = "approved" if _user_is_system(doc.user) else "pending"
	frappe.db.set_value("Press MCP Token", token_id, values)

	what = "; ".join(
		part
		for part in (
			"added " + ", ".join(_label(t) for t in added) if added else "",
			"removed " + ", ".join(_label(t) for t in removed) if removed else "",
		)
		if part
	)
	log_token_action("Edit Tools", token_id, what, how, {"added": added, "removed": removed})
	frappe.db.commit()
	return {
		"name": token_id,
		"added": added,
		"removed": removed,
		"scope": new,
		"risky_tools_enabled": bool(values.get("risky_tools_enabled", doc.risky_tools_enabled)),
		"approval_status": values.get("approval_status"),
	}


@frappe.whitelist()
def token_history(token_id: str) -> list[dict[str, str]]:
	"""The newest HISTORY_ROWS changes of one token: when, who, what, how they confirmed."""
	owner = frappe.db.get_value("Press MCP Token", token_id, "user")
	is_system = frappe.session.data.user_type == "System User"
	if not owner or (owner != frappe.session.user and not is_system):
		frappe.throw("Only the token's own user can see its history.", frappe.PermissionError)
	rows = frappe.get_all(
		"Press MCP Admin Action",
		filters={"target_token": token_id},
		fields=["actor", "action_type", "reason", "context_json", "creation"],
		order_by="creation desc",
		limit=HISTORY_ROWS,
	)
	names = {r.actor: get_fullname(r.actor) for r in rows if r.actor}
	return [
		{
			"when": str(r.creation),
			"who": names.get(r.actor, r.actor or ""),
			"what": r.reason or r.action_type,
			"how": (json.loads(r.context_json or "{}") or {}).get("how", ""),
		}
		for r in rows
	]
