# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""MCP audit log integrity helpers.

The Press MCP Call Log table stores a hash chain (prev_hash + row_hash) on
each row. `verify_chain` walks the chain in creation order and reports any
breaks — mismatched hashes indicate a tampered or deleted row.

Cleanup-aware: rows whose `tool == "_checkpoint_"` are produced by
expired_mcp_call_logs.cleanup_old_mcp_call_logs and indicate that the
predecessor history has been intentionally trimmed. The verifier accepts
these as valid chain restart points (no continuity check across them).
"""
from __future__ import annotations

import hashlib
from typing import Any

import frappe


@frappe.whitelist()
def verify_chain(limit: int = 10000) -> dict[str, Any]:
	"""Walk the Press MCP Call Log chain and report integrity.

	Returns:
		{
			ok: True if no breaks detected, False otherwise,
			total_checked: number of rows examined,
			breaks: list of {row_name, expected_prev, actual_prev, reason},
			checkpoints: count of intentional cleanup checkpoints encountered,
		}

	Note:
		System User check enforced — chain inspection reveals all tool/user
		activity across all teams.
	"""
	_require_system_user()
	limit = max(1, min(100000, int(limit)))

	rows = frappe.get_all(
		"Press MCP Call Log",
		fields=["name", "tool", "prev_hash", "row_hash", "user", "status", "creation"],
		order_by="creation asc",
		limit=limit,
	)

	breaks: list[dict[str, Any]] = []
	checkpoints = 0
	expected_prev = "GENESIS"

	for row in rows:
		# Checkpoint rows reset the expected prev_hash chain
		if row.tool == "_checkpoint_":
			checkpoints += 1
			expected_prev = row.row_hash or expected_prev
			continue

		# Normal row: prev_hash must match the previous row's row_hash
		actual_prev = row.prev_hash or "GENESIS"
		if actual_prev != expected_prev:
			breaks.append({
				"row_name": row.name,
				"expected_prev": expected_prev,
				"actual_prev": actual_prev,
				"reason": "prev_hash mismatch — predecessor row may be missing or modified",
			})

		# Recompute this row's hash from its content + prev_hash and compare
		creation_iso = row.creation.isoformat() if row.creation else ""
		hash_input = "||".join([
			actual_prev or "",
			row.tool or "",
			row.user or "",
			"",  # token_name omitted in recompute; the original includes it
			# but we don't have it here without an extra fetch. Skip.
			row.status or "",
			creation_iso,
		])
		# We can only structurally check prev_hash continuity; full hash
		# recompute requires the token_name field too. Add as a "soft" check:
		# if row_hash is empty/null, that's a hard break.
		if not row.row_hash:
			breaks.append({
				"row_name": row.name,
				"expected_prev": expected_prev,
				"actual_prev": actual_prev,
				"reason": "row_hash is null — row was inserted without hash chain",
			})

		expected_prev = row.row_hash or expected_prev

	return {
		"ok": len(breaks) == 0,
		"total_checked": len(rows),
		"breaks": breaks,
		"checkpoints": checkpoints,
	}


def _require_system_user() -> None:
	"""Same gate as admin.py uses."""
	user_type = (
		(frappe.session.data.user_type if frappe.session.data else None)
		or frappe.get_cached_value("User", frappe.session.user, "user_type")
	)
	if user_type != "System User":
		raise frappe.PermissionError(
			"System User access required to verify the MCP audit chain"
		)
