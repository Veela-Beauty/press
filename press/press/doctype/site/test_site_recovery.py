"""Tests for ghost-pending site recovery (recover_ghost_pending_sites).

Lives in its own file (not test_site.py) because test_site.py pulls in a
chain of test fixtures that require the moto AWS mocking library — not
always installed. Recovery logic is pure SQL + db.set_value, no AWS.
"""

from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from press.press.doctype.site.site import recover_ghost_pending_sites


class TestRecoverGhostPendingSites(FrappeTestCase):
	@patch("press.press.doctype.site.site.frappe.db.commit")
	@patch("press.press.doctype.site.site.frappe.db.set_value")
	@patch("press.press.doctype.site.site.frappe.db.sql")
	def test_recovers_eligible_site(self, mock_sql, mock_set, _commit):
		"""A single ghost-pending site is flipped Pending -> Active."""
		mock_sql.return_value = [{"name": "ghost-site.example.com"}]
		recover_ghost_pending_sites()
		mock_set.assert_called_once_with(
			"Site", "ghost-site.example.com", "status", "Active"
		)

	@patch("press.press.doctype.site.site.frappe.db.commit")
	@patch("press.press.doctype.site.site.frappe.db.set_value")
	@patch("press.press.doctype.site.site.frappe.db.sql")
	def test_no_op_when_no_candidates(self, mock_sql, mock_set, _commit):
		"""No ghost-pending sites detected → no writes."""
		mock_sql.return_value = []
		recover_ghost_pending_sites()
		mock_set.assert_not_called()

	@patch("press.press.doctype.site.site.frappe.db.commit")
	@patch("press.press.doctype.site.site.frappe.logger")
	@patch(
		"press.press.doctype.site.site.frappe.db.set_value",
		side_effect=Exception("boom"),
	)
	@patch("press.press.doctype.site.site.frappe.db.sql")
	def test_continues_on_individual_failure(
		self, mock_sql, mock_set, mock_logger, _commit
	):
		"""If one site recovery fails, others are still attempted."""
		mock_sql.return_value = [
			{"name": "ghost-1.example.com"},
			{"name": "ghost-2.example.com"},
		]
		recover_ghost_pending_sites()
		# Both attempted despite the first one raising
		self.assertEqual(mock_set.call_count, 2)
		# Error path was logged
		self.assertTrue(mock_logger.return_value.error.called)
