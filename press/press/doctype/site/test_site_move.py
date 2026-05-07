# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.api.site_move import move_to_release_group
from press.press.doctype.app.test_app import create_test_app
from press.press.doctype.release_group.test_release_group import (
	create_test_release_group,
)
from press.press.doctype.site.test_site import create_test_bench, create_test_site


def _insert_active_bench(group_name: str) -> str:
	"""Insert a minimal Active Bench row for a release group without triggering deploys."""
	bench_name = frappe.generate_hash(length=10)
	frappe.db.set_value(
		"Bench",
		{"name": bench_name},
		{
			"name": bench_name,
			"group": group_name,
			"status": "Active",
			"server": "",
			"background_workers": 1,
			"gunicorn_workers": 2,
		},
	)
	return bench_name


class TestSiteMove(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self._deploy_patcher = patch(
			"press.press.doctype.release_group.release_group.ReleaseGroup.create_deploy_candidate"
		)
		self._deploy_patcher.start()
		self.addCleanup(self._deploy_patcher.stop)

		self.app = create_test_app()
		# create_test_site() creates its own bench + RG internally
		self.site = create_test_site()
		self.target_rg = create_test_release_group(apps=[self.app])
		# Create an active bench for target_rg using the full helper
		# (deploy patcher prevents the candidate from actually building)
		self.target_bench = create_test_bench(group=self.target_rg)

	def tearDown(self):
		frappe.db.delete("Press Lock", {"target_doctype": "Site"})

	def test_move_resolves_target_rg_to_active_bench(self):
		# Mock the underlying Site.move_to_bench so we don't hit the agent
		with patch("press.press.doctype.site.site.Site.move_to_bench") as m:
			m.return_value = type("J", (), {"name": "fake-job"})()
			result = move_to_release_group(
				site=self.site.name,
				target_release_group=self.target_rg.name,
			)
			self.assertTrue(m.called)
			self.assertIn("job", result)
			self.assertEqual(result["target_bench"], self.target_bench.name)
			self.assertEqual(result["target_release_group"], self.target_rg.name)

	def test_move_to_rg_with_no_active_bench_raises(self):
		empty_rg = create_test_release_group(apps=[self.app])
		# No Bench rows are created automatically by create_test_release_group;
		# so the target should have no active bench → expect ValidationError
		with self.assertRaises(frappe.ValidationError):
			move_to_release_group(
				site=self.site.name,
				target_release_group=empty_rg.name,
			)

	def test_move_to_same_rg_raises(self):
		# Resolve current site's group
		current_rg = frappe.db.get_value("Site", self.site.name, "group")
		with self.assertRaises(frappe.ValidationError):
			move_to_release_group(
				site=self.site.name,
				target_release_group=current_rg,
			)

	def test_move_app_coverage_mismatch_raises(self):
		# Create a target RG with different apps (simulate mismatch by removing apps)
		mismatch_rg = create_test_release_group(apps=[self.app])
		mismatch_rg.apps = []
		mismatch_rg.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			move_to_release_group(
				site=self.site.name,
				target_release_group=mismatch_rg.name,
			)
