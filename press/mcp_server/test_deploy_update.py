# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""bench_deploy_and_update / deploy_update_status (0.7.49) and the review follow-ups of 0.7.52: the site list in
scope/sites.py (the caller's team's sites by default), status over every bench of a build."""

from __future__ import annotations

import pathlib
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from press.mcp_server import deploy_update
from press.mcp_server.scope import call_guard
from press.mcp_server.scope import sites as scope_sites

APPS = [{"app": "frappe", "release": "r1", "hash": "h1"}]
SITES = [
	frappe._dict(name="a.example.com", server="f1", bench="bench-1"),
	frappe._dict(name="b.example.com", server="f1", bench="bench-1"),
]


class TestChosenSites(FrappeTestCase):
	def _chosen(self, sites):
		calls = []

		def get_all(doctype, filters=None, fields=None, **kwargs):
			calls.append(filters)
			return SITES

		with (
			patch.object(scope_sites.frappe, "get_all", side_effect=get_all),
			patch.object(scope_sites, "_calling_team", return_value="team-1"),
		):
			return [s.name for s in scope_sites.chosen_sites("rg-1", sites)], calls

	def test_left_out_means_the_calling_teams_active_sites_on_the_group(self):
		names, calls = self._chosen(None)
		self.assertEqual(names, ["a.example.com", "b.example.com"])
		self.assertEqual(calls, [{"group": "rg-1", "status": "Active", "team": "team-1"}])

	def test_named_sites_as_a_list_a_json_string_or_one_name(self):
		self.assertEqual(self._chosen(["b.example.com"])[0], ["b.example.com"])
		self.assertEqual(self._chosen('["b.example.com"]')[0], ["b.example.com"])
		self.assertEqual(self._chosen("a.example.com")[0], ["a.example.com"])
		self.assertEqual(self._chosen([])[0], [])
		self.assertNotIn("team", self._chosen(["a.example.com"])[1][0])  # named: the guard checks the team

	def test_left_out_with_no_team_is_refused_not_a_silent_empty_deploy(self):
		with (
			patch.object(scope_sites.frappe, "get_all", return_value=[]),
			patch.object(scope_sites, "_calling_team", return_value=None),
			self.assertRaises(frappe.ValidationError),
		):
			scope_sites.chosen_sites("rg-1", None)

	def test_bad_input_and_a_site_not_on_the_group_are_refused(self):
		for bad in ([1], "[not json", {"a": 1}, ["other.example.com"]):
			with self.assertRaises(frappe.ValidationError):
				self._chosen(bad)


class TestBenchDeployAndUpdate(FrappeTestCase):
	def _deploy(self, sites=None, apps=APPS):
		sent = {}

		def fake_deploy(name, apps, sites):
			sent.update(name=name, apps=apps, sites=sites)
			return "build-1"

		with (
			patch.object(scope_sites.frappe, "get_all", return_value=SITES),
			patch.object(scope_sites, "_calling_team", return_value="team-1"),
			patch("press.api.bench.deploy_and_update", side_effect=fake_deploy),
			patch.object(deploy_update.frappe.db, "get_value", return_value="cand-1"),
		):
			result = deploy_update.bench_deploy_and_update(name="rg-1", apps=apps, sites=sites)
		return result, sent

	def test_the_dashboards_deploy_gets_the_site_payload(self):
		result, sent = self._deploy()
		self.assertEqual((result["build"], result["candidate"]), ("build-1", "cand-1"))
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

	def test_a_site_not_on_the_group_is_refused_before_any_deploy(self):
		with (
			patch.object(scope_sites.frappe, "get_all", return_value=SITES),
			patch("press.api.bench.deploy_and_update") as deploy,
			self.assertRaises(frappe.ValidationError),
		):
			deploy_update.bench_deploy_and_update(name="rg-1", apps=APPS, sites=["other.example.com"])
		deploy.assert_not_called()

	def test_apps_must_be_release_dicts(self):
		for bad in ('["frappe"]', "not json", []):
			with self.assertRaises(frappe.ValidationError):
				deploy_update.bench_deploy_and_update(name="rg-1", apps=bad)


class TestDeployUpdateStatus(FrappeTestCase):
	def _status(self, build_status, bench_statuses=(), sites=(), bench_update="bu-1", built_minutes_ago=1):
		build_end = add_to_date(None, minutes=-built_minutes_ago)
		build = frappe._dict(name="build-1", status=build_status, deploy_candidate="cand-1", build_end=build_end)
		benches = [
			frappe._dict(name=f"bench-{i}", status=s, modified=now_datetime())
			for i, s in enumerate(bench_statuses)
		]
		values = {"Deploy Candidate Build": build, "Bench Update": bench_update}
		with (
			patch.object(deploy_update.frappe.db, "get_value", side_effect=lambda dt, *a, **k: values[dt]),
			patch.object(deploy_update.frappe, "get_all", return_value=benches),
			patch.object(deploy_update, "_site_rows", return_value=list(sites)),
			patch.object(deploy_update, "_visible", side_effect=lambda rows: rows),
		):
			return deploy_update.deploy_update_status(name="build-1")

	def _stage(self, *args, **kwargs):
		r = self._status(*args, **kwargs)
		return r["stage"], r["done"], r["ok"]

	def test_the_build(self):
		self.assertEqual(self._stage("Running"), ("build", False, False))
		r = self._status("Failure")
		self.assertEqual((r["stage"], r["done"], r["ok"]), ("build", True, False))
		self.assertIn("deploy_failure_details", r["hint"])

	def test_every_bench_of_a_two_server_group_is_waited_for(self):
		self.assertEqual(self._stage("Success"), ("bench", False, False))  # benches not made yet
		r = self._status("Success", built_minutes_ago=20)  # and none ever came
		self.assertEqual((r["stage"], r["done"], r["ok"]), ("bench", True, False))
		self.assertIn("no bench was made", r["hint"])
		self.assertEqual(self._stage("Success", ["Active", "Installing"]), ("bench", False, False))
		self.assertEqual(self._stage("Success", ["Active", "Broken"]), ("bench", True, False))
		self.assertEqual(
			self._stage("Success", ["Active", "Archived"], [{"site": "a", "status": "Success"}]),
			("done", True, True),
		)
		r = self._status("Success", ["Active", "Installing"])
		self.assertEqual(
			r["benches"],
			[{"bench": "bench-0", "status": "Active"}, {"bench": "bench-1", "status": "Installing"}],
		)

	def test_the_sites(self):
		running = [{"site": "a", "status": "Success"}, {"site": "b", "status": "Running"}]
		self.assertEqual(self._stage("Success", ["Active"], running), ("sites", False, False))
		self.assertEqual(self._stage("Success", ["Active"], []), ("done", True, True))
		r = self._status(
			"Success", ["Active"], [{"site": "a", "status": "Success"}, {"site": "b", "status": "Recovered"}]
		)
		self.assertEqual((r["done"], r["ok"]), (True, False))
		self.assertIn("agent_job_traceback", r["hint"])

	def test_a_plain_bench_deploy_build_says_it_updates_no_sites(self):
		r = self._status("Success", ["Active"], bench_update=None)
		self.assertIn("updates no sites", r["note"])
		self.assertEqual(r["sites"], [])


class TestSiteRows(FrappeTestCase):
	def _rows(self, minutes_since_ready):
		rows = [
			frappe._dict(site="a", site_update="su-1", status="Pending"),
			frappe._dict(site="b", site_update=None, status="Pending"),
		]
		updates = [frappe._dict(name="su-1", status="Running", update_job="job-1")]
		ready_since = (
			add_to_date(None, minutes=-minutes_since_ready) if minutes_since_ready is not None else None
		)
		with patch.object(deploy_update.frappe, "get_all", side_effect=[rows, updates]):
			return deploy_update._site_rows("bu-1", ready_since)

	def test_the_site_update_status_is_read_and_an_unscheduled_row_fails_only_after_the_grace(self):
		self.assertEqual(
			self._rows(1),
			[
				{"site": "a", "status": "Running", "site_update": "su-1", "update_job": "job-1"},
				{"site": "b", "status": "Waiting for the bench"},
			],
		)
		self.assertEqual(self._rows(10)[1], {"site": "b", "status": "Not scheduled"})
		self.assertEqual(
			self._rows(None)[1], {"site": "b", "status": "Waiting for the bench"}
		)  # benches not ready

	def test_hidden_sites_are_left_out(self):
		rows = [{"site": s, "status": "Success"} for s in ("a", "b", "c")]
		try:
			with patch("press.mcp_server.scope.confidential.confidential_sites", return_value=["c"]):
				frappe.local.mcp_token_allowed_sites = None
				frappe.local.mcp_token_confidential_sites = None
				self.assertEqual([r["site"] for r in deploy_update._visible(rows)], ["a", "b"])
				frappe.local.mcp_token_allowed_sites = ["a"]
				self.assertEqual([r["site"] for r in deploy_update._visible(rows)], ["a"])
		finally:
			frappe.local.mcp_token_allowed_sites = None


class TestSiteListGuard(FrappeTestCase):
	def tearDown(self):
		frappe.local.mcp_token_allowed_sites = None

	def test_each_site_is_checked_for_team_allowlist_and_confidential(self):
		checked = []
		with (
			patch("press.mcp_server.scope.sites.chosen_sites", return_value=SITES) as chosen,
			patch.object(
				call_guard, "assert_in_team", side_effect=lambda team, dt, site: checked.append(site)
			),
			patch.object(call_guard, "assert_unlocked") as unlocked,
		):
			frappe.local.mcp_token_allowed_sites = None
			call_guard._rule_site_list(
				"team-1", {"name": "rg-1", "sites": ["a.example.com", "b.example.com"]}
			)
			self.assertEqual(checked, ["a.example.com", "b.example.com"])
			unlocked.assert_called_once_with({"a.example.com", "b.example.com"})

			frappe.local.mcp_token_allowed_sites = ["a.example.com"]
			with self.assertRaises(frappe.PermissionError):
				call_guard._rule_site_list("team-1", {"name": "rg-1"})
			chosen.assert_called_with(
				"rg-1", None
			)  # left out: the list the tool acts on is checked, not skipped

	def test_the_rule_is_wired_to_the_tool(self):
		self.assertIs(call_guard._TOOL_RULES["bench_deploy_and_update"], call_guard._rule_site_list)

	def test_the_scope_layer_does_not_import_the_tools_it_guards(self):
		scope_dir = pathlib.Path(call_guard.__file__).parent
		for path in scope_dir.glob("*.py"):
			if not path.name.startswith("test_"):
				self.assertNotIn("press.mcp_server.deploy_update", path.read_text(), path.name)


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
