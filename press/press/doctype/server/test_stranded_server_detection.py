# Copyright (c) 2026, Frappe and Contributors
# See license.txt
"""Regression tests for stranded-server detection (2026-09-08, u5-default)."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from press.press.doctype.server.stranded_server_detection import detect_stranded_servers
from press.press.doctype.site.test_site import create_test_bench


class TestStrandedServerDetection(FrappeTestCase):
	def test_reports_non_active_server_that_still_owns_an_active_bench(self):
		"""The silent exclusion that froze u5-default for 8 days must be visible.

		poll_pending_jobs_server() and schedule_updates() both skip any server
		whose status is not "Active", without logging anything.
		"""
		bench = create_test_bench()
		frappe.db.set_value("Server", bench.server, "status", "Pending")

		stranded = detect_stranded_servers()["stranded"]

		entry = next((s for s in stranded if s["server"] == bench.server), None)
		self.assertIsNotNone(entry, "a Pending server owning an Active bench was not reported")
		self.assertEqual(entry["status"], "Pending")
		self.assertGreaterEqual(entry["active_benches"], 1)

	def test_ignores_active_server(self):
		"""A healthy server is not noise in the report."""
		bench = create_test_bench()
		frappe.db.set_value("Server", bench.server, "status", "Active")

		stranded = detect_stranded_servers()["stranded"]

		self.assertNotIn(bench.server, [s["server"] for s in stranded])
