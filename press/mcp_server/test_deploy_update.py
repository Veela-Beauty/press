# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.mcp_server import deploy_update
from press.mcp_server.scope import call_guard

APPS = [{"app": "frappe", "release": "r1", "hash": "h1"}]
SITES = [
	frappe._dict(name="a.example.com", server="f1", bench="bench-1"),
	frappe._dict(name="b.example.com", server="f1", bench="bench-1"),
]


class TestBenchDeployAndUpdate(FrappeTestCase):
	def _deploy(self, sites=None, apps=APPS):
		sent = {}

		def fake_deploy(name, apps, sites):
			sent.update(name=name, apps=apps, sites=sites)
			return "build-1"

		with (
			patch.object(deploy_update.frappe, "get_all", return_value=SITES),
			patch("press.api.bench.deploy_and_update", side_effect=fake_deploy),
			patch.object(deploy_update.frappe.db, "get_value", return_value="cand-1"),
		):
			result = deploy_update.bench_deploy_and_update(name="rg-1", apps=apps, sites=sites)
		return result, sent

	def test_sites_default_to_every_active_site_on_the_group(self):
		result, sent = self._deploy()
		self.assertEqual(result["build"], "build-1")
		self.assertEqual(result["candidate"], "cand-1")
		self.assertEqual(result["sites"], ["a.example.com", "b.example.com"])
		self.assertEqual(
			sent["sites"][0],
			{
				"name": "a.example.com",
				"server": "f1",
				"bench": "bench-1",
				"skip_failing_patches": False,
				"skip_backups": False,
			},
		)

	def test_named_sites_as_a_json_string_or_one_name(self):
		self.assertEqual(self._deploy(sites='["b.example.com"]')[0]["sites"], ["b.example.com"])
		self.assertEqual(self._deploy(sites="a.example.com")[0]["sites"], ["a.example.com"])

	def test_a_site_not_on_the_group_is_refused_before_any_deploy(self):
		with (
			patch.object(deploy_update.frappe, "get_all", return_value=SITES),
			patch("press.api.bench.deploy_and_update") as deploy,self.assertRaises(frappe.ValidationError)
		):
			deploy_update.bench_deploy_and_update(name="rg-1", apps=APPS, sites=["other.example.com"])
		deploy.assert_not_called()

	def test_apps_must_be_release_dicts(self):
		with self.assertRaises(frappe.ValidationError):
			deploy_update.bench_deploy_and_update(name="rg-1", apps='["frappe"]')

	def test_sites_must_be_names_and_an_empty_list_means_none(self):
		with self.assertRaises(frappe.ValidationError):
			self._deploy(sites=[1])
		with self.assertRaises(frappe.ValidationError):
			self._deploy(sites="[not json")
		self.assertEqual(self._deploy(sites=[])[0]["sites"], [])


class TestDeployUpdateStatus(FrappeTestCase):
	def _status(self, build_status, bench_status=None, sites=(), bench_update="bu-1"):
		build = frappe._dict(name="build-1", status=build_status, deploy_candidate="cand-1")
		bench = (
			frappe._dict(name="bench-2", status=bench_status, modified=frappe.utils.now_datetime())
			if bench_status
			else None
		)
		values = {"Deploy Candidate Build": build, "Bench": bench, "Bench Update": bench_update}

		with (
			patch.object(deploy_update.frappe.db, "get_value", side_effect=lambda dt, *a, **k: values[dt]),
			patch.object(deploy_update, "_site_rows", return_value=list(sites)),
			patch.object(deploy_update, "_visible", side_effect=lambda rows: rows),
		):
			return deploy_update.deploy_update_status(name="build-1")

	def test_running_build(self):
		r = self._status("Running")
		self.assertEqual((r["stage"], r["done"]), ("build", False))

	def test_failed_build_points_to_the_failure_details(self):
		r = self._status("Failure")
		self.assertEqual((r["stage"], r["done"], r["ok"]), ("build", True, False))
		self.assertIn("deploy_failure_details", r["hint"])

	def test_built_but_bench_not_active_yet(self):
		r = self._status("Success", "Installing")
		self.assertEqual((r["stage"], r["done"]), ("bench", False))

	def test_sites_still_updating(self):
		r = self._status(
			"Success", "Active", [{"site": "a", "status": "Success"}, {"site": "b", "status": "Running"}]
		)
		self.assertEqual((r["stage"], r["done"]), ("sites", False))

	def test_all_sites_updated(self):
		r = self._status("Success", "Active", [{"site": "a", "status": "Success"}])
		self.assertEqual((r["stage"], r["done"], r["ok"]), ("done", True, True))

	def test_a_failed_site_is_done_but_not_ok(self):
		r = self._status(
			"Success", "Active", [{"site": "a", "status": "Success"}, {"site": "b", "status": "Recovered"}]
		)
		self.assertEqual((r["done"], r["ok"]), (True, False))
		self.assertIn("agent_job_traceback", r["hint"])

	def test_no_sites_is_done_when_the_bench_is_active(self):
		r = self._status("Success", "Active", [])
		self.assertEqual((r["stage"], r["done"], r["ok"]), ("done", True, True))

	def test_an_archived_bench_was_ready_and_a_broken_one_failed(self):
		r = self._status("Success", "Archived", [{"site": "a", "status": "Success"}])
		self.assertEqual((r["done"], r["ok"]), (True, True))
		r = self._status("Success", "Broken")
		self.assertEqual((r["stage"], r["done"], r["ok"]), ("bench", True, False))

	def test_a_plain_bench_deploy_build_says_it_updates_no_sites(self):
		r = self._status("Success", "Active", bench_update=None)
		self.assertIn("updates no sites", r["note"])
		self.assertEqual(r["sites"], [])


class TestSiteRows(FrappeTestCase):
	def _rows(self, minutes_since_ready):
		rows = [
			frappe._dict(site="a", site_update="su-1", status="Pending"),
			frappe._dict(site="b", site_update=None, status="Pending"),
		]
		updates = [frappe._dict(name="su-1", status="Running", update_job="job-1")]
		ready = frappe._dict(modified=frappe.utils.add_to_date(None, minutes=-minutes_since_ready))
		with patch.object(deploy_update.frappe, "get_all", side_effect=[rows, updates]):
			return deploy_update._site_rows("bu-1", ready)

	def test_the_site_update_status_is_read_and_an_unscheduled_row_fails_after_the_grace(self):
		self.assertEqual(
			self._rows(1),
			[
				{"site": "a", "status": "Running", "site_update": "su-1", "update_job": "job-1"},
				{"site": "b", "status": "Waiting for the bench"},
			],
		)
		self.assertEqual(self._rows(10)[1], {"site": "b", "status": "Not scheduled"})

	def test_hidden_sites_are_left_out(self):
		rows = [{"site": "a", "status": "Success"}, {"site": "b", "status": "Success"}, {"site": "c", "status": "Success"}]
		with patch("press.mcp_server.scope.confidential.confidential_sites", return_value=["c"]):
			frappe.local.mcp_token_allowed_sites = None
			frappe.local.mcp_token_confidential_sites = None
			self.assertEqual([r["site"] for r in deploy_update._visible(rows)], ["a", "b"])
			frappe.local.mcp_token_allowed_sites = ["a"]
			self.assertEqual([r["site"] for r in deploy_update._visible(rows)], ["a"])
		frappe.local.mcp_token_allowed_sites = None


class TestSiteListGuard(FrappeTestCase):
	def tearDown(self):
		frappe.local.mcp_token_allowed_sites = None

	def test_each_site_is_checked_for_team_allowlist_and_confidential(self):
		checked = []
		with (
			patch("press.mcp_server.deploy_update.chosen_sites", return_value=SITES) as chosen,
			patch.object(
				call_guard, "assert_in_team", side_effect=lambda team, dt, site: checked.append(site)
			),
			patch.object(call_guard, "assert_unlocked") as unlocked,
		):
			frappe.local.mcp_token_allowed_sites = None
			call_guard._rule_site_list("team-1", {"name": "rg-1", "sites": ["a.example.com", "b.example.com"]})
			self.assertEqual(checked, ["a.example.com", "b.example.com"])
			unlocked.assert_called_once_with({"a.example.com", "b.example.com"})

			frappe.local.mcp_token_allowed_sites = ["a.example.com"]
			with self.assertRaises(frappe.PermissionError):
				call_guard._rule_site_list("team-1", {"name": "rg-1"})
			# leaving sites out is checked against every Active site of the group, not skipped
			chosen.assert_called_with("rg-1", None)

	def test_the_rule_is_wired_to_the_tool(self):
		self.assertIs(call_guard._TOOL_RULES["bench_deploy_and_update"], call_guard._rule_site_list)


class TestScopeTargets(FrappeTestCase):
	def test_the_deploy_is_scoped_to_its_group_and_the_status_to_the_build_group(self):
		from press.mcp_server.scope import targets

		self.assertEqual(
			targets._extract_target("bench_deploy_and_update", {"name": "rg-1", "apps": APPS}),
			("Release Group", "rg-1"),
		)
		with patch.object(targets, "_candidate_to_release_group", return_value="rg-1"):
			self.assertEqual(
				targets._extract_target("deploy_update_status", {"name": "build-1"}),
				("Release Group", "rg-1"),
			)
