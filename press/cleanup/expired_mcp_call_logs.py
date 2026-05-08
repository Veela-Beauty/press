# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Cleanup MCP Call Log rows older than 30 days, preserving hash-chain integrity.

The hash chain stores `prev_hash` on each row. If we delete a middle row, the
chain becomes inconsistent for any subsequent verification. To stay
tamper-evident, we keep the LATEST row in every cleanup batch, copying its
`prev_hash` forward as a "checkpoint" so future verifications can resume from
there. This effectively trims old rows but keeps a verifiable thread.

Strategy:
	1. Find all rows older than the cutoff.
	2. If 0 stale rows → no-op.
	3. Otherwise, find the LATEST stale row by creation; mark it as a checkpoint
	   row by setting its `tool` to "_checkpoint_" (still queryable, still
	   carries the prev_hash forward).
	4. Delete all OTHER stale rows.
"""
from __future__ import annotations

import frappe
from frappe.utils import add_to_date, now_datetime

RETENTION_DAYS = 30


def cleanup_old_mcp_call_logs() -> dict[str, int]:
	"""Delete Press MCP Call Log rows older than RETENTION_DAYS, keeping the
	latest stale row as a hash-chain checkpoint.

	Returns:
		{deleted, kept_as_checkpoint, retained_total}
	"""
	cutoff = add_to_date(now_datetime(), days=-RETENTION_DAYS)
	stale = frappe.get_all(
		"Press MCP Call Log",
		filters={"creation": ("<", cutoff)},
		fields=["name", "creation"],
		order_by="creation desc",
	)
	if not stale:
		return {"deleted": 0, "kept_as_checkpoint": 0, "retained_total": frappe.db.count("Press MCP Call Log")}

	# Latest stale row → checkpoint; older rows → delete
	checkpoint_name = stale[0].name
	to_delete = [r.name for r in stale[1:]]

	if to_delete:
		frappe.db.delete("Press MCP Call Log", {"name": ("in", to_delete)})

	# Mark the survivor as a checkpoint so verify_chain knows to skip its
	# prev_hash continuity check (we just deleted its predecessors).
	frappe.db.set_value(
		"Press MCP Call Log",
		checkpoint_name,
		{"tool": "_checkpoint_", "error_message": f"Cleanup checkpoint at {now_datetime().isoformat()}"},
	)

	return {
		"deleted": len(to_delete),
		"kept_as_checkpoint": 1,
		"retained_total": frappe.db.count("Press MCP Call Log"),
	}
