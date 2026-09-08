# Copyright (c) 2026, Frappe and Contributors
# See license.txt
"""Regression tests for the orphaned-bench-status bug (2026-09-08, bench-0014)."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from press.press.doctype.agent_job.stuck_job_recovery import _mark_failure
from press.press.doctype.bench.bench import process_new_bench_job_update
from press.press.doctype.site.test_site import create_test_bench


class TestStuckJobRecoveryCallback(FrappeTestCase):
	def _new_bench_job(self, bench, status="Pending"):
		return frappe.get_doc(
			{
				"doctype": "Agent Job",
				"job_type": "New Bench",
				"status": status,
				"server": bench.server,
				"server_type": "Server",
				"bench": bench.name,
				"job_id": 1,
				"request_path": "benches",
				"request_method": "POST",
				"request_data": "{}",
			}
		).insert(ignore_permissions=True)

	def test_cron_failure_advances_the_linked_bench(self):
		"""A job the cron gives up on must not leave its Bench stuck at Pending.

		The cron used to write Agent Job.status with a bare db.set_value, which
		skips process_job_updates. The Bench then stayed "Pending" forever --
		invisible to archive_broken_benches and to every retry path.
		"""
		bench = create_test_bench()
		bench.db_set("status", "Pending")
		job = self._new_bench_job(bench)

		_mark_failure(job.name, "stuck Pending for >2h, agent verdict='no_activity'")

		self.assertEqual(frappe.db.get_value("Agent Job", job.name, "status"), "Failure")
		self.assertEqual(frappe.db.get_value("Bench", bench.name, "status"), "Broken")

	def test_undelivered_new_bench_job_is_handled(self):
		"""Undelivered is a real Agent Job status; the callback used to KeyError."""
		bench = create_test_bench()
		bench.db_set("status", "Pending")
		job = self._new_bench_job(bench, status="Undelivered")
		job.reload()

		process_new_bench_job_update(job)

		self.assertEqual(frappe.db.get_value("Bench", bench.name, "status"), "Broken")
