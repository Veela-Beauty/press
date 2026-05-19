# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.press.doctype.site.site_clone import (
	check_bench_space,
	clone_site,
	get_clone_options,
	list_compatible_benches,
)
from press.press.doctype.site.test_site import create_test_site
from press.press.doctype.site_backup.test_site_backup import create_test_site_backup


class TestSiteClone(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		# Block real agent calls when create_test_site_backup creates non-Pending backups
		from press.press.doctype.site_backup.site_backup import SiteBackup

		self._backup_after_insert_patcher = patch.object(SiteBackup, "after_insert")
		self._backup_after_insert_patcher.start()
		self.addCleanup(self._backup_after_insert_patcher.stop)
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

	def test_list_compatible_benches_includes_same_app_set(self):
		# The bench created with the source site shares its app set,
		# so list_compatible_benches must include it.
		result = list_compatible_benches(self.source_site.name)
		names = {row["value"] for row in result}
		self.assertIn(self.target_bench, names)

	def test_list_compatible_benches_excludes_missing_apps(self):
		# A bench that is missing one of the source site's apps must be excluded.
		# We simulate this by inserting a stub Bench row with an empty apps list.
		stub_name = "Test Empty Apps Bench"
		bench_doc = frappe.get_doc("Bench", self.target_bench)
		frappe.get_doc(
			{
				"doctype": "Bench",
				"name": stub_name,
				"status": "Active",
				"background_workers": 1,
				"gunicorn_workers": 2,
				"group": bench_doc.group,
				"apps": [],  # zero apps → incompatible with any non-empty site
				"candidate": bench_doc.candidate,
				"build": bench_doc.build,
				"server": bench_doc.server,
				"docker_image": bench_doc.docker_image,
			}
		).insert(ignore_if_duplicate=True, ignore_permissions=True)
		self.addCleanup(
			lambda: frappe.delete_doc("Bench", stub_name, force=True, ignore_permissions=True)
		)

		result = list_compatible_benches(self.source_site.name)
		names = {row["value"] for row in result}
		self.assertNotIn(stub_name, names)

	def test_get_clone_options_returns_expected_shape(self):
		result = get_clone_options(self.source_site.name)
		self.assertIn("compatible_benches", result)
		self.assertIn("plans", result)
		self.assertIn("source_plan", result)
		self.assertIn("source_disk_usage", result)
		# compatible_benches should at least contain the source's own bench
		names = {b["value"] for b in result["compatible_benches"]}
		self.assertIn(self.target_bench, names)
		# plans is a list (may be empty in test fixture)
		self.assertIsInstance(result["plans"], list)
		# source_disk_usage is an int (0 if untracked)
		self.assertIsInstance(result["source_disk_usage"], int)

	def test_check_bench_space_returns_sufficiency_flag(self):
		# Required = 0 → always sufficient regardless of free space
		result = check_bench_space(self.target_bench, required_bytes=0)
		self.assertEqual(result["server"], frappe.db.get_value("Bench", self.target_bench, "server"))
		self.assertTrue(result["sufficient"])
		self.assertIn("free_bytes", result)
		self.assertIn("is_public_server", result)

	def test_clone_fresh_backup_triggers_backup_then_raises(self):
		# fresh_backup mode is async-by-design: it triggers the backup
		# then asks the caller to retry with latest_backup once ready.
		from press.press.doctype.site.site import Site

		with patch.object(Site, "backup") as mock_backup:
			with self.assertRaises(frappe.ValidationError) as ctx:
				clone_site(
					site=self.source_site.name,
					target_bench=self.target_bench,
					new_subdomain="copy-fresh",
					mode="fresh_backup",
				)
			self.assertIn("queued", str(ctx.exception).lower())
			mock_backup.assert_called_once_with(with_files=True, offsite=True)

	def test_clone_fresh_backup_persists_site_backup_row(self):
		# REGRESSION: clone_site fresh_backup mode does source.backup(...).insert()
		# then frappe.throw(...). Without an explicit commit between the two, the
		# throw rolls back the transaction and the Site Backup row vanishes,
		# leaving the user with a "queued" message but no actual backup queued.
		# The fix in site_clone.py inserts an explicit frappe.db.commit() before
		# the throw — this test locks that behavior in.
		existing = frappe.db.count(
			"Site Backup", filters={"site": self.source_site.name, "offsite": 1}
		)

		with self.assertRaises(frappe.ValidationError) as ctx:
			clone_site(
				site=self.source_site.name,
				target_bench=self.target_bench,
				new_subdomain="copy-fresh-persist",
				mode="fresh_backup",
			)
		self.assertIn("queued", str(ctx.exception).lower())

		# After the throw rolled back the request transaction, the explicit
		# commit above the throw should have persisted exactly one new
		# offsite Site Backup row for this site.
		after = frappe.db.count(
			"Site Backup", filters={"site": self.source_site.name, "offsite": 1}
		)
		self.assertEqual(after, existing + 1, "fresh_backup did not persist a Site Backup row")
