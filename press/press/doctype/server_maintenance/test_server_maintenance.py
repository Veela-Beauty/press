# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestServerMaintenance(FrappeTestCase):
	def test_run_registry_gc_records_result(self):
		doc = frappe.get_single("Server Maintenance")
		with patch(
			"press.press.doctype.server_maintenance.server_maintenance._run_maint",
			return_value="registry-gc: freed 35MB, 100 blobs deleted",
		):
			res = doc.run_registry_gc()
		self.assertIn("freed", res)
		self.assertTrue(frappe.db.get_single_value("Server Maintenance", "registry_gc_last_run"))

	def test_backup_retention_apply_passes_flag(self):
		doc = frappe.get_single("Server Maintenance")
		doc.db_set("backup_retention_keep_days", 7)
		from press.press.doctype.server_maintenance import server_maintenance as sm
		with patch.object(sm, "_run_maint", return_value="backup-retention (applied): 5 old backups, 10MB") as m:
			doc.run_backup_retention(apply=1)
		self.assertIn("--apply", [str(a) for a in m.call_args[0]])

	def test_backup_retention_dryrun_no_apply_flag(self):
		doc = frappe.get_single("Server Maintenance")
		from press.press.doctype.server_maintenance import server_maintenance as sm
		with patch.object(sm, "_run_maint", return_value="backup-retention (dryrun): 5 old backups, 10MB") as m:
			doc.run_backup_retention(apply=0)
		self.assertNotIn("--apply", [str(a) for a in m.call_args[0]])

	def test_scheduled_registry_gc_respects_disabled(self):
		doc = frappe.get_single("Server Maintenance")
		doc.db_set("registry_gc_enabled", 0)
		from press.press.doctype.server_maintenance import server_maintenance as sm
		with patch.object(sm, "_run_maint") as m:
			sm.run_scheduled_registry_gc()
			m.assert_not_called()
		doc.db_set("registry_gc_enabled", 1)

	def test_scheduled_backup_retention_respects_disabled(self):
		doc = frappe.get_single("Server Maintenance")
		doc.db_set("backup_retention_enabled", 0)
		from press.press.doctype.server_maintenance import server_maintenance as sm
		with patch.object(sm, "_run_maint") as m:
			sm.run_scheduled_backup_retention()
			m.assert_not_called()
