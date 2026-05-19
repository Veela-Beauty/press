# Copyright (c) 2020, Frappe and Contributors
# See license.txt


import frappe
from frappe.tests.utils import FrappeTestCase

from press.press.doctype.cluster.test_cluster import create_test_cluster


def create_test_press_settings():
	"""Create test press settings doc"""
	create_test_cluster()
	if not frappe.db.exists("TLS Certificate", "*.fc.dev"):
		frappe.get_doc(
			{
				"doctype": "TLS Certificate",
				"name": "*.fc.dev",
				"domain": "fc.dev",
				"wildcard": True,
				"status": "Active",
				"rsa_key_size": 2048,
			}
		).db_insert()

	frappe.get_doc(
		{
			"doctype": "Root Domain",
			"name": "fc.dev",
			"dns_provider": "AWS Route 53",
			"default_cluster": "Default",
			"aws_access_key_id": frappe.mock("password"),
			"aws_secret_access_key": frappe.mock("password"),
		}
	).insert(ignore_if_duplicate=True)

	settings = frappe.get_single("Press Settings")
	settings.domain = "fc.dev"
	settings.bench_configuration = "{}"
	settings.rsa_key_size = 2048
	settings.certbot_directory = ".certbot"
	settings.eff_registration_email = frappe.mock("email")
	settings.max_concurrent_physical_restorations = 2
	settings.minimum_rebuild_memory = 2
	settings.save()
	return settings


class TestPressSettings(FrappeTestCase):
	def test_password_preservation_on_save_without_password_resubmit(self):
		"""REGRESSION: Saving Press Settings via the desk after editing only
		non-password fields used to wipe every Password field whose in-memory
		value came back falsy — Frappe's _save_passwords() called
		remove_encrypted_password() on any empty Password. We've lost
		offsite_backups_secret_access_key this way at least twice in production.

		The before_save() patch on PressSettings adds every falsy Password
		field to self.flags.ignore_save_passwords so _save_passwords skips it
		and the __Auth row is preserved. This test exercises that path.
		"""
		from frappe.utils.password import (
			get_decrypted_password,
			set_encrypted_password,
		)

		create_test_press_settings()
		# Seed a known secret on a Password field
		fieldname = "offsite_backups_secret_access_key"
		set_encrypted_password(
			"Press Settings", "Press Settings", "test-secret-123", fieldname=fieldname
		)
		self.assertEqual(
			get_decrypted_password(
				"Press Settings", "Press Settings", fieldname, raise_exception=False
			),
			"test-secret-123",
		)

		# Re-fetch the Single (passwords are NOT auto-loaded into the doc) and
		# save it. Without the patch this would call _save_passwords ->
		# remove_encrypted_password on every Password field with no in-memory
		# value, including the one we just set.
		settings = frappe.get_single("Press Settings")
		# Force a real change so save() isn't a no-op
		settings.minimum_rebuild_memory = (settings.minimum_rebuild_memory or 2) + 0
		settings.save()

		# The secret must still be decryptable
		self.assertEqual(
			get_decrypted_password(
				"Press Settings", "Press Settings", fieldname, raise_exception=False
			),
			"test-secret-123",
			"Press Settings.save() wiped offsite_backups_secret_access_key — the "
			"before_save() password-preservation guard is not working",
		)
