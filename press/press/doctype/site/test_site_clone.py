# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.press.doctype.site.site_clone import clone_site
from press.press.doctype.site.test_site import create_test_site
from press.press.doctype.site_backup.test_site_backup import create_test_site_backup


class TestSiteClone(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.source_site = create_test_site()
		self.target_bench = frappe.db.get_value(
			"Bench",
			{"group": self.source_site.group, "status": "Active"},
			"name",
		)

	def test_clone_empty_passes_no_remote_files(self):
		with patch("press.press.doctype.site.site_clone._call_press_new") as m:
			m.return_value = "new-site"
			clone_site(
				site=self.source_site.name,
				target_bench=self.target_bench,
				new_subdomain="copy-empty",
				mode="empty",
			)

			args, _ = m.call_args
			site_payload = args[0]
			self.assertNotIn("files", site_payload)
			self.assertEqual(site_payload["bench"], self.target_bench)

	def test_clone_latest_backup_passes_remote_files(self):
		# create_test_site_backup populates remote_public_file, remote_private_file,
		# remote_database_file via create_test_remote_file.
		# It does NOT populate remote_config_file — set it manually below.
		backup = create_test_site_backup(site=self.source_site.name)
		backup.remote_config_file = backup.remote_database_file  # any non-empty value
		backup.save(ignore_permissions=True)

		with patch("press.press.doctype.site.site_clone._call_press_new") as m:
			m.return_value = "new-site"
			clone_site(
				site=self.source_site.name,
				target_bench=self.target_bench,
				new_subdomain="copy-latest",
				mode="latest_backup",
			)

			args, _ = m.call_args
			site_payload = args[0]
			files = site_payload.get("files")
			self.assertIsNotNone(files)
			self.assertEqual(files["database"], backup.remote_database_file)
			self.assertEqual(files["public"], backup.remote_public_file)
			self.assertEqual(files["private"], backup.remote_private_file)
			self.assertEqual(files["config"], backup.remote_config_file)

	def test_clone_latest_backup_with_no_backup_raises(self):
		# Use a fresh site that has no backups.
		fresh_site = create_test_site(subdomain="no-backup-site")
		with self.assertRaises(frappe.ValidationError):
			clone_site(
				site=fresh_site.name,
				target_bench=self.target_bench,
				new_subdomain="copy-no-backup",
				mode="latest_backup",
			)

	def test_clone_invalid_mode_raises(self):
		with self.assertRaises(frappe.ValidationError):
			clone_site(
				site=self.source_site.name,
				target_bench=self.target_bench,
				new_subdomain="copy-bad-mode",
				mode="teleport",
			)

	def test_clone_subdomain_collision_raises(self):
		create_test_site(subdomain="taken-sub")
		with self.assertRaises(frappe.ValidationError):
			clone_site(
				site=self.source_site.name,
				target_bench=self.target_bench,
				new_subdomain="taken-sub",
				mode="empty",
			)
