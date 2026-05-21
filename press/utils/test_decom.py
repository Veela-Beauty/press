# Copyright (c) 2026, Frappe and contributors
# License: see license.txt
"""Tests for press.utils.decom — the single source of truth for
'is this resource decommissioned?' checks used by Press scheduled crons.

Mocks frappe.db.get_value because we don't need real fixtures here; the
helpers are thin wrappers + a fail-open contract that's easier to test
behaviourally than via real Server/Database Server fixtures.
"""
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.utils.decom import (
	is_bench_on_decommissioned_server,
	is_database_server_in_decommissioned_cluster,
	is_server_decommissioned,
	is_site_on_decommissioned_server,
)


class TestIsServerDecommissioned(FrappeTestCase):
	def test_returns_true_for_decommissioned_server(self):
		with patch("press.utils.decom.frappe.db.get_value", return_value=1):
			self.assertTrue(is_server_decommissioned("f-0001.fc.dev"))

	def test_returns_false_for_active_server(self):
		with patch("press.utils.decom.frappe.db.get_value", return_value=0):
			self.assertFalse(is_server_decommissioned("press-f1.example.com"))

	def test_returns_false_for_missing_server_name(self):
		# Empty / None server name — fail-open, no DB call needed
		self.assertFalse(is_server_decommissioned(""))
		self.assertFalse(is_server_decommissioned(None))

	def test_fails_open_on_lookup_error(self):
		"""If the DB lookup itself errors, helper returns False so the cron
		doesn't accidentally start skipping legitimate work."""
		with patch("press.utils.decom.frappe.db.get_value", side_effect=Exception("db down")):
			self.assertFalse(is_server_decommissioned("any.example.com"))


class TestIsDatabaseServerInDecommissionedCluster(FrappeTestCase):
	def test_returns_true_when_linked_app_server_is_decommissioned(self):
		# Database Server m2927 → app Server f-0001 (is_decommissioned=1)
		with patch("press.utils.decom.frappe.db.get_value", return_value="f-0001.fc.dev"):
			self.assertTrue(is_database_server_in_decommissioned_cluster("m2927.fc.dev"))

	def test_returns_false_when_no_decommissioned_app_server_links(self):
		with patch("press.utils.decom.frappe.db.get_value", return_value=None):
			self.assertFalse(is_database_server_in_decommissioned_cluster("m-prod.example.com"))


class TestIsSiteOnDecommissionedServer(FrappeTestCase):
	def test_site_on_decommissioned_app_server(self):
		"""tabSite.server points at f-0001 (decommissioned)."""
		def fake_get_value(doctype, name, fieldname=None, as_dict=False):
			if doctype == "Site" and as_dict:
				return frappe._dict({"server": "f-0001.fc.dev", "database_server": "m2927.fc.dev"})
			if doctype == "Server" and fieldname == "is_decommissioned":
				return 1 if name == "f-0001.fc.dev" else 0
			return None

		with patch("press.utils.decom.frappe.db.get_value", side_effect=fake_get_value):
			self.assertTrue(is_site_on_decommissioned_server("test-site-00001.fc.dev"))

	def test_site_with_active_links(self):
		def fake_get_value(doctype, name, fieldname=None, as_dict=False):
			if doctype == "Site" and as_dict:
				return frappe._dict({"server": "press-f1.example.com", "database_server": "m-prod.example.com"})
			return 0

		with patch("press.utils.decom.frappe.db.get_value", side_effect=fake_get_value):
			self.assertFalse(is_site_on_decommissioned_server("prod-site.example.com"))


class TestIsBenchOnDecommissionedServer(FrappeTestCase):
	def test_bench_on_decommissioned_server(self):
		def fake_get_value(doctype, name, fieldname=None, as_dict=False):
			if doctype == "Bench" and as_dict:
				return frappe._dict({"server": "f-0001.fc.dev", "database_server": "m2927.fc.dev"})
			if doctype == "Server" and fieldname == "is_decommissioned":
				return 1
			return None

		with patch("press.utils.decom.frappe.db.get_value", side_effect=fake_get_value):
			self.assertTrue(is_bench_on_decommissioned_server("bench-0024-000001-f-0001"))

	def test_missing_bench_returns_false(self):
		with patch("press.utils.decom.frappe.db.get_value", return_value=None):
			self.assertFalse(is_bench_on_decommissioned_server("nonexistent-bench"))
