# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestTelephonyBundle(FrappeTestCase):
	def test_gen_secret_is_url_safe_and_long(self):
		from press.infra import telephony_bundle as tb

		s = tb.gen_secret(24)
		self.assertGreaterEqual(len(s), 24)
		self.assertTrue(all(c.isalnum() or c in "-_" for c in s))
		self.assertNotEqual(s, tb.gen_secret(24))  # random

	def test_render_env_has_all_provisioner_vars(self):
		from press.infra import telephony_bundle as tb

		env = tb.render_env(
			site_url="https://dmg-erp.example.com/", instance="dmg-voip-1",
			public_ip="89.167.116.92", ami_password="AMIPW", api_token="k:s",
		)
		self.assertIn("OC_SITE=https://dmg-erp.example.com", env)  # trailing slash trimmed
		self.assertIn("OC_INSTANCE=dmg-voip-1", env)
		self.assertIn("PUBLIC_IP=89.167.116.92", env)
		self.assertIn("AMI_PASSWORD=AMIPW", env)
		self.assertIn("OC_API_TOKEN=k:s", env)
		# AMI_USER/PORT for the listener half
		self.assertIn("AMI_USER=oc-listener", env)

	def test_read_bundle_returns_the_manifest_files(self):
		from press.infra import telephony_bundle as tb

		fake = {p: f"// {p}" for p in tb.BUNDLE_FILES}

		def fake_read(rel):
			return fake[rel]

		with patch.object(tb, "_read_app_file", side_effect=fake_read):
			files = tb.read_bundle()
		# every manifest entry is present, keyed by its on-HOST destination path
		for rel in tb.BUNDLE_FILES:
			dest = tb.HOST_DIR + "/" + rel
			self.assertIn(dest, files)

	def test_read_bundle_raises_clear_error_if_app_missing(self):
		from press.infra import telephony_bundle as tb

		with patch.object(tb, "_read_app_file", side_effect=FileNotFoundError("nope")):
			with self.assertRaises(frappe.ValidationError):
				tb.read_bundle()
