# A confidential site is reachable over MCP only by a token the Admin PIN unlocked at issue time.
from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.model.naming import make_autoname
from frappe.tests.utils import FrappeTestCase

from press.mcp_server.auth import issue_token, verify_token
from press.mcp_server.scope.call_guard import _sites_of_call, assert_call_in_team
from press.press.doctype.site.site import Site
from press.press.doctype.site.test_site import create_test_site
from press.press.doctype.team.test_team import create_test_team


class TestConfidentialMCPAccess(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.lm = MagicMock()
		self.lm.check_password.return_value = None
		for p in (
			patch.object(frappe.local, "login_manager", self.lm, create=True),
			patch.object(Site, "_send_wrong_pin_alert"),
		):
			p.start()
			self.addCleanup(p.stop)
		frappe.db.set_single_value("Press Settings", "admin_login_pin", "1234")
		self.site = create_test_site(make_autoname("confmcp-.#####"))
		self.site.db_set("is_confidential", 1)
		self.team = self.site.team
		self.neighbour = create_test_site(make_autoname("confnbr-.#####"), bench=self.site.bench, team=self.team)
		team_patch = patch("press.mcp_server.auth._get_team_for_user", return_value=self.team)
		team_patch.start()
		self.addCleanup(team_patch.stop)
		r = frappe.cache()
		for k in r.keys("confidential_pin_fail:*"):
			r.delete(k)
		self._unlock([])

	def tearDown(self):
		frappe.local.mcp_token_confidential_sites = None
		frappe.db.delete("Press MCP Token")
		frappe.db.delete("Press MCP Auth Attempt")

	def _unlock(self, sites):
		frappe.local.mcp_token_confidential_sites = sites

	def _issue(self, allowed_sites, pin=""):
		return issue_token(
			username="Administrator",
			password="ignored",
			scope=["site_migrate"],
			ttl_minutes=10,
			label="conf-test",
			allowed_sites=allowed_sites,
			confidential_pin=pin,
		)

	def _fails(self):
		return frappe.cache().get(f"confidential_pin_fail:{frappe.session.user}:{self.site.name}")

	# Issuing

	def test_naming_a_confidential_site_needs_the_pin(self):
		with self.assertRaises(frappe.ValidationError):
			self._issue([self.site.name])
		with self.assertRaises(frappe.ValidationError):
			self._issue([self.site.name], pin="0000")
		self.assertEqual(self._issue([self.site.name], pin="1234")["confidential_sites"], [self.site.name])

	def test_all_sites_token_unlocks_nothing(self):
		self.assertEqual(self._issue([])["confidential_sites"], [])

	def test_password_is_checked_before_the_pin(self):
		self.lm.check_password.side_effect = frappe.AuthenticationError
		with self.assertRaises(Exception):
			self._issue([self.site.name], pin="0000")
		self.assertFalse(self._fails())

	def test_another_teams_site_gets_no_pin_prompt(self):
		other = create_test_site(make_autoname("confoth-.#####"), team=create_test_team().name)
		other.db_set("is_confidential", 1)
		self.assertEqual(self._issue([other.name])["confidential_sites"], [])

	def test_verify_token_carries_the_unlock(self):
		token = self._issue([self.site.name], pin="1234")["token"]
		verify_token(token, tool_name="site_migrate")
		self.assertEqual(frappe.local.mcp_token_confidential_sites, [self.site.name])

	# Calling, through the real guard

	def test_guard_refuses_a_locked_site_by_any_arg_name(self):
		for tool, args in (
			("site_migrate", {"name": self.site.name}),
			("site_run_sql", {"site_name": self.site.name, "query": "select 1"}),
			("clone_site", {"site": self.site.name}),
		):
			with self.assertRaises(frappe.PermissionError):
				assert_call_in_team(tool, args, self.team)
		self._unlock([self.site.name])
		assert_call_in_team("site_migrate", {"name": self.site.name}, self.team)

	def test_guard_refuses_in_container_access_on_a_shared_bench(self):
		args = {"site_name": self.neighbour.name, "code": "print(1)"}
		with self.assertRaises(frappe.PermissionError):
			assert_call_in_team("site_run_python", args, self.team)
		assert_call_in_team("site_migrate", {"name": self.neighbour.name}, self.team)  # not in-container
		self._unlock([self.site.name])
		assert_call_in_team("site_run_python", args, self.team)

	def test_archived_confidential_site_does_not_lock_its_bench(self):
		self.site.db_set("status", "Archived")
		assert_call_in_team("site_run_python", {"site_name": self.neighbour.name, "code": "print(1)"}, self.team)

	def test_dashboard_login_refused_while_the_team_has_a_locked_site(self):
		with self.assertRaises(frappe.PermissionError):
			assert_call_in_team("mint_dashboard_login_url", {}, self.team)
		self._unlock([self.site.name])
		assert_call_in_team("mint_dashboard_login_url", {}, self.team)

	def test_every_way_of_naming_the_site_is_seen(self):
		# api/site.py tools take the site as `name`, bench_dev_overview tools as `site_name`.
		self.assertIn(self.site.name, _sites_of_call("site_migrate", {"name": self.site.name}))
		self.assertIn(self.site.name, _sites_of_call("site_run_sql", {"site_name": self.site.name}))
		self.assertIn(self.site.name, _sites_of_call("clone_site", {"site": self.site.name}))
