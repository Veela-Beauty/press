# Copyright (c) 2026, Frappe and Contributors
# See license.txt
"""The site list must not hide a real status behind "Update Available"."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.press.doctype.site.site import Site
from press.press.doctype.site.test_site import create_test_bench, create_test_site


class TestSiteListStatusMasking(FrappeTestCase):
	def _listed_statuses(self, bench_name):
		SiteTable = frappe.qb.DocType("Site")
		query = frappe.qb.from_(SiteTable).select(SiteTable.name)
		with patch(
			"press.press.doctype.site_update.site_update.benches_with_available_update",
			return_value=[bench_name],
		):
			rows = Site.get_list_query(query, filters={})
		return {r.name: r.status for r in rows}

	def test_broken_site_keeps_its_status(self):
		"""charity.sandbox read as "Update Available" for 8 days while Broken."""
		bench = create_test_bench()
		broken = create_test_site("brokenmask", bench=bench.name)
		broken.db_set("status", "Broken")
		healthy = create_test_site("healthymask", bench=bench.name)
		healthy.db_set("status", "Active")

		statuses = self._listed_statuses(bench.name)

		self.assertEqual(statuses[broken.name], "Broken")
		self.assertEqual(statuses[healthy.name], "Update Available")
