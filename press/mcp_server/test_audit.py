# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import hashlib
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from press.cleanup.expired_mcp_call_logs import cleanup_old_mcp_call_logs
from press.mcp_server.audit import verify_chain


def _make_log(name: str, prev_hash: str, tool: str = "list_release_groups", creation_offset_days: int = 0):
	"""Insert a Press MCP Call Log row with explicit hash chain values."""
	creation = add_to_date(now_datetime(), days=-creation_offset_days)
	row_hash = hashlib.sha256(f"{prev_hash}||{tool}||{name}".encode()).hexdigest()
	doc = frappe.get_doc({
		"doctype": "Press MCP Call Log",
		"tool": tool,
		"user": "Administrator",
		"status": "Success",
		"duration_ms": 1,
		"prev_hash": prev_hash,
		"row_hash": row_hash,
	}).insert(ignore_permissions=True)
	if creation_offset_days:
		frappe.db.set_value("Press MCP Call Log", doc.name, "creation", creation)
	return doc.name, row_hash


class TestAuditChain(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Press MCP Call Log")

	def tearDown(self):
		frappe.db.delete("Press MCP Call Log")

	def test_verify_chain_empty_table_returns_ok(self):
		result = verify_chain()
		self.assertTrue(result["ok"])
		self.assertEqual(result["total_checked"], 0)
		self.assertEqual(result["breaks"], [])

	def test_verify_chain_with_intact_chain_returns_ok(self):
		_, h1 = _make_log("r1", "GENESIS")
		_, h2 = _make_log("r2", h1)
		_, h3 = _make_log("r3", h2)
		result = verify_chain()
		self.assertTrue(result["ok"], f"breaks: {result['breaks']}")
		self.assertEqual(result["total_checked"], 3)

	def test_verify_chain_detects_broken_link(self):
		_, h1 = _make_log("r1", "GENESIS")
		# r2 has wrong prev_hash — pretend tampering
		_make_log("r2_bad", "WRONG_HASH")
		result = verify_chain()
		self.assertFalse(result["ok"])
		self.assertGreaterEqual(len(result["breaks"]), 1)

	def test_verify_chain_accepts_checkpoint_rows(self):
		_, h1 = _make_log("r1", "GENESIS")
		# Mark a row as checkpoint (cleanup output)
		ck_name, ck_hash = _make_log("checkpoint", h1, tool="_checkpoint_")
		# After checkpoint, a new chain starts from ck_hash
		_make_log("r3", ck_hash)
		result = verify_chain()
		self.assertTrue(result["ok"], f"breaks: {result['breaks']}")
		self.assertEqual(result["checkpoints"], 1)

	def test_verify_chain_requires_system_user(self):
		original_ut = frappe.session.data.user_type if frappe.session.data else None
		if frappe.session.data is None:
			frappe.session.data = frappe._dict()
		frappe.session.data.user_type = "Website User"
		try:
			# Also bypass the DB-level fallback
			with patch(
				"press.mcp_server.audit.frappe.get_cached_value",
				return_value="Website User",
			):
				with self.assertRaises(frappe.PermissionError):
					verify_chain()
		finally:
			if original_ut is None:
				frappe.session.data.user_type = "System User"
			else:
				frappe.session.data.user_type = original_ut


class TestCallLogCleanup(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Press MCP Call Log")

	def tearDown(self):
		frappe.db.delete("Press MCP Call Log")

	def test_cleanup_no_op_when_nothing_stale(self):
		_, _ = _make_log("recent", "GENESIS", creation_offset_days=0)
		result = cleanup_old_mcp_call_logs()
		self.assertEqual(result["deleted"], 0)
		self.assertEqual(result["kept_as_checkpoint"], 0)

	def test_cleanup_deletes_old_keeps_checkpoint(self):
		# 5 stale rows (>30 days), 2 fresh
		_make_log("stale1", "GENESIS", creation_offset_days=60)
		_make_log("stale2", "h1", creation_offset_days=55)
		_make_log("stale3", "h2", creation_offset_days=50)
		_make_log("stale4", "h3", creation_offset_days=45)
		_make_log("stale5_latest_stale", "h4", creation_offset_days=35)
		_make_log("fresh1", "h5", creation_offset_days=10)
		_make_log("fresh2", "h6", creation_offset_days=5)

		before = frappe.db.count("Press MCP Call Log")
		self.assertEqual(before, 7)

		result = cleanup_old_mcp_call_logs()
		# 4 deleted (oldest 4), 1 kept as checkpoint, 2 fresh untouched
		self.assertEqual(result["deleted"], 4)
		self.assertEqual(result["kept_as_checkpoint"], 1)
		self.assertEqual(result["retained_total"], 3)

		# The kept stale row should now be a checkpoint
		ck = frappe.db.get_all(
			"Press MCP Call Log",
			filters={"tool": "_checkpoint_"},
			pluck="name",
		)
		self.assertEqual(len(ck), 1)

	def test_cleanup_preserves_chain_after_run(self):
		"""After cleanup, verify_chain should still report ok."""
		# Build a real-ish chain
		_, h1 = _make_log("r1", "GENESIS", creation_offset_days=60)
		_, h2 = _make_log("r2", h1, creation_offset_days=50)
		_, h3 = _make_log("r3", h2, creation_offset_days=40)
		_, h4 = _make_log("r4", h3, creation_offset_days=10)
		_, h5 = _make_log("r5", h4, creation_offset_days=5)

		cleanup_old_mcp_call_logs()
		# r3 should remain as checkpoint with row_hash=h3; r4, r5 retain their prev_hashes
		# After cleanup: row_hash on the checkpoint is preserved; the next row (r4)
		# has prev_hash=h3, so chain verifies.
		result = verify_chain()
		self.assertTrue(result["ok"], f"breaks: {result['breaks']}")
		self.assertGreaterEqual(result["checkpoints"], 1)
