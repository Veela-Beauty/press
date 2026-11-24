from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

import frappe

from press.press.doctype.site.stale_creation_failed import MIGRATE_JOBS, clear_stale_creation_failed

FLAGGED = frappe._dict(name="healed.example.com", creation_failed=datetime(2026, 11, 17, 15, 37))
MODULE = "press.press.doctype.site.stale_creation_failed.frappe"


@patch(f"{MODULE}.db.commit")
@patch(f"{MODULE}.db.sql")
@patch(f"{MODULE}.db.exists")
@patch(f"{MODULE}.get_all")
class TestClearStaleCreationFailed(TestCase):
	def test_clears_after_a_green_migrate(self, get_all, exists, sql, commit):
		get_all.return_value = [FLAGGED]
		exists.return_value = "job-1"
		clear_stale_creation_failed()
		sql.assert_called_once()
		query, values = sql.call_args.args
		self.assertIn("status = 'Active' and creation_failed = %s", " ".join(query.split()))
		self.assertEqual(values, ("healed.example.com", FLAGGED.creation_failed))
		commit.assert_called_once()

	def test_keeps_the_flag_without_a_green_migrate_after_it(self, get_all, exists, sql, commit):
		get_all.return_value = [FLAGGED]
		exists.return_value = None
		clear_stale_creation_failed()
		sql.assert_not_called()
		commit.assert_not_called()

	def test_looks_only_at_active_flagged_sites_and_migrates_after_the_flag(
		self, get_all, exists, sql, commit
	):
		get_all.return_value = [FLAGGED]
		exists.return_value = None
		clear_stale_creation_failed()
		self.assertEqual(
			get_all.call_args.kwargs["filters"], {"status": "Active", "creation_failed": ("is", "set")}
		)
		self.assertEqual(
			exists.call_args.args,
			(
				"Agent Job",
				{
					"site": "healed.example.com",
					"job_type": ("in", MIGRATE_JOBS),
					"status": "Success",
					"creation": (">", FLAGGED.creation_failed),
				},
			),
		)

	def test_nothing_flagged_writes_nothing(self, get_all, exists, sql, commit):
		get_all.return_value = []
		clear_stale_creation_failed()
		exists.assert_not_called()
		sql.assert_not_called()
