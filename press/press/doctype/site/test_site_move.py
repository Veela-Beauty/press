# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.api.site_move import (
	get_site_move_context,
	list_eligible_target_release_groups,
	move_to_release_group,
)
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
		# Add an extra app to the site directly in the DB.
		# target_rg only has self.app (frappe) so moving will fail coverage check.
		extra_app = create_test_app(name="erpnext_extra", title="ERPNext Extra")
		frappe.get_doc(
			{
				"doctype": "Site App",
				"parent": self.site.name,
				"parenttype": "Site",
				"parentfield": "apps",
				"app": extra_app.name,
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)
		with self.assertRaises(frappe.ValidationError):
			move_to_release_group(
				site=self.site.name,
				target_release_group=self.target_rg.name,
			)

	# ------------------------------------------------------------------
	# list_eligible_target_release_groups — picker filter (depth: full)
	# Critical: drives what RGs the user sees in the move dialog.
	# A bug here either hides valid moves (frustrating) or shows invalid
	# moves (server-side rejects with confusing error).
	# ------------------------------------------------------------------

	def test_eligible_includes_target_rg_on_same_server_with_active_bench(self):
		# Test fixtures don't guarantee same server — pin them explicitly.
		site_server = frappe.db.get_value("Bench", self.site.bench, "server")
		frappe.db.set_value("Bench", self.target_bench.name, "server", site_server)
		result = list_eligible_target_release_groups(self.site.name)
		names = [rg["name"] for rg in result]
		self.assertIn(self.target_rg.name, names)

	def test_eligible_excludes_current_rg(self):
		current_rg = frappe.db.get_value("Site", self.site.name, "group")
		result = list_eligible_target_release_groups(self.site.name)
		names = [rg["name"] for rg in result]
		self.assertNotIn(current_rg, names)

	def test_eligible_excludes_rg_with_no_active_bench(self):
		empty_rg = create_test_release_group(apps=[self.app])
		# No Bench created → not eligible
		result = list_eligible_target_release_groups(self.site.name)
		names = [rg["name"] for rg in result]
		self.assertNotIn(empty_rg.name, names)

	def test_eligible_excludes_rg_missing_required_app(self):
		# Add a second app to the site that target_rg doesn't have.
		extra_app = create_test_app(name="erpnext_pickerfilter", title="ERPNext PF")
		frappe.get_doc(
			{
				"doctype": "Site App",
				"parent": self.site.name,
				"parenttype": "Site",
				"parentfield": "apps",
				"app": extra_app.name,
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)
		result = list_eligible_target_release_groups(self.site.name)
		names = [rg["name"] for rg in result]
		# target_rg is missing extra_app → should NOT be eligible
		self.assertNotIn(self.target_rg.name, names)

	def test_eligible_excludes_rg_on_different_server(self):
		other_rg = create_test_release_group(apps=[self.app])
		# Insert an Active Bench on a DIFFERENT server
		other_bench = create_test_bench(group=other_rg)
		frappe.db.set_value("Bench", other_bench.name, "server", "different-server-12345")
		result = list_eligible_target_release_groups(self.site.name)
		names = [rg["name"] for rg in result]
		self.assertNotIn(other_rg.name, names)

	def test_eligible_returns_required_shape(self):
		# Picker UI relies on these specific keys — guard against drift.
		result = list_eligible_target_release_groups(self.site.name)
		if result:
			required_keys = {"name", "title", "server", "app_count"}
			self.assertEqual(set(result[0].keys()), required_keys)
			self.assertIsInstance(result[0]["app_count"], int)

	# ------------------------------------------------------------------
	# get_site_move_context — wrapper used by the dialog (depth: normal)
	# ------------------------------------------------------------------

	def test_context_returns_current_release_group(self):
		current_rg = frappe.db.get_value("Site", self.site.name, "group")
		ctx = get_site_move_context(self.site.name)
		self.assertEqual(ctx["current_release_group"], current_rg)
		self.assertEqual(ctx["site"], self.site.name)
		# Title falls back to the technical name when title is empty,
		# but the key must always be present so the dialog has something to show.
		self.assertIn("current_release_group_title", ctx)

	def test_context_returns_current_bench_and_server(self):
		ctx = get_site_move_context(self.site.name)
		self.assertEqual(ctx["current_bench"], self.site.bench)
		# server may be empty string in test fixtures, but key must exist
		self.assertIn("server", ctx)

	def test_context_eligible_matches_standalone_list(self):
		# get_site_move_context.eligible should be exactly what
		# list_eligible_target_release_groups returns. Catches accidental
		# divergence if someone duplicates the filter logic.
		ctx = get_site_move_context(self.site.name)
		standalone = list_eligible_target_release_groups(self.site.name)
		self.assertEqual(
			[rg["name"] for rg in ctx["eligible"]],
			[rg["name"] for rg in standalone],
		)
