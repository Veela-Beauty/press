# Copyright (c) 2026, Frappe and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.press.doctype.ssh_certificate import ssh_certificate
from press.press.doctype.ssh_certificate.ssh_certificate import (
	SSHCertificate,
	has_development_bench,
	user_certificate_validity,
)

MODULE = "press.press.doctype.ssh_certificate.ssh_certificate"


def cert(validity, certificate_type="User", group="bench-0080"):
	return SimpleNamespace(certificate_type=certificate_type, validity=validity, group=group)


class TestDevBenchValidity(FrappeTestCase):
	def test_dev_bench_lookup_asks_for_an_active_development_bench(self):
		with patch("frappe.db.exists", return_value="bench-0080-000001") as exists:
			self.assertTrue(has_development_bench("bench-0080"))
		exists.assert_called_once_with(
			"Bench", {"group": "bench-0080", "status": "Active", "is_development_bench": 1}
		)

	def test_no_group_is_not_a_dev_bench_and_reads_nothing(self):
		with patch("frappe.db.exists") as exists:
			self.assertFalse(has_development_bench(None))
		exists.assert_not_called()

	def test_new_certificate_is_30_days_on_a_dev_bench_6_hours_elsewhere(self):
		with patch(f"{MODULE}.has_development_bench", return_value=True):
			self.assertEqual(user_certificate_validity("bench-0080"), "30d")
		with patch(f"{MODULE}.has_development_bench", return_value=False):
			self.assertEqual(user_certificate_validity("bench-0075"), "6h")

	def test_30_days_accepted_on_a_dev_bench(self):
		with patch(f"{MODULE}.has_development_bench", return_value=True):
			SSHCertificate.validate_validity(cert("30d"))
			SSHCertificate.validate_validity(cert("6h"))

	def test_30_days_refused_on_any_other_bench(self):
		with patch(f"{MODULE}.has_development_bench", return_value=False):
			SSHCertificate.validate_validity(cert("6h", group="bench-0075"))
			with self.assertRaises(frappe.ValidationError):
				SSHCertificate.validate_validity(cert("30d", group="bench-0075"))

	def test_unknown_validity_refused_even_on_a_dev_bench(self):
		with (
			patch(f"{MODULE}.has_development_bench", return_value=True),
			self.assertRaises(frappe.ValidationError),
		):
			SSHCertificate.validate_validity(cert("1d"))

	def test_server_certificates_are_not_checked(self):
		with patch(f"{MODULE}.has_development_bench") as dev:
			SSHCertificate.validate_validity(cert("30d", certificate_type="Server"))
		dev.assert_not_called()

	def test_release_group_uses_the_rule(self):
		from press.press.doctype.release_group import release_group

		self.assertIs(release_group.user_certificate_validity, ssh_certificate.user_certificate_validity)
