from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from press.mcp_server.scope import roles

GUARD = "press.mcp_server.scope.roles.role_guard"


def guard(limited=True, allowed=()):
	g = MagicMock()
	g.is_restricted.return_value = limited
	g.skip_roles.return_value = False
	g.check.side_effect = lambda doctype, name: (doctype, name) in set(allowed)
	return g


class TestAssertCallInRoles(TestCase):
	def run_call(self, tool, args, g, resources):
		with patch(GUARD, g), patch.object(roles, "_resources_of_call", return_value=resources):
			roles.assert_call_in_roles(tool, args)

	def test_unlimited_member_is_not_checked(self):
		g = guard(limited=False)
		self.run_call("site_status", {}, g, {"Site": {"other.example.com"}})
		g.check.assert_not_called()

	def test_listed_site_passes(self):
		g = guard(allowed=[("Site", "quest-dev.example.com")])
		self.run_call(
			"site_status", {}, g, {"Site": {"quest-dev.example.com"}, "Release Group": set(), "Server": set()}
		)

	def test_unlisted_site_is_refused_with_the_not_visible_message(self):
		g = guard(allowed=[("Site", "quest-dev.example.com")])
		with self.assertRaises(frappe.PermissionError) as raised:
			self.run_call("site_status", {}, g, {"Site": {"prime.example.com"}})
		self.assertIn(
			"'prime.example.com' was not found, or is not in this token's team", str(raised.exception)
		)

	def test_unlisted_server_is_refused(self):
		g = guard(allowed=[("Release Group", "bench-0080")])
		with self.assertRaises(frappe.PermissionError):
			self.run_call(
				"host_memory_pressure", {}, g, {"Release Group": {"bench-0080"}, "Server": {"f1.example.com"}}
			)

	def test_dashboard_login_is_refused_for_a_limited_member(self):
		with patch(GUARD, guard()), self.assertRaises(frappe.PermissionError):
			roles.assert_call_in_roles("mint_dashboard_login_url", {})


class TestResourcesOfCall(TestCase):
	def test_bench_job_and_server_args_map_to_their_doctypes(self):
		values = {
			("Bench", "bench-0080-000001", "group"): "bench-0080",
			("Site", "quest-dev.example.com", "bench"): "bench-0080-000001",
		}
		get_value = MagicMock(side_effect=lambda dt, name, field, **kw: values.get((dt, name, field)))
		with patch.object(frappe.db, "get_value", get_value):
			found = roles._resources_of_call(
				"bench_restart", {"bench_name": "bench-0080-000001", "server": "f1.example.com"}
			)
		self.assertEqual(found["Release Group"], {"bench-0080"})
		self.assertEqual(found["Server"], {"f1.example.com"})
		self.assertEqual(found["Site"], set())


class TestFilterToRoles(TestCase):
	def run_filter(self, tool, response, all_access=False, listed=()):
		g = guard()
		with (
			patch(GUARD, g),
			patch.object(roles, "has_user_permission", return_value=all_access),
			patch.object(roles, "documents", return_value=list(listed)),
		):
			return roles.filter_to_roles(tool, response)

	def test_list_sites_keeps_only_listed_sites(self):
		rows = [{"name": "quest-dev.example.com"}, {"name": "prime.example.com"}]
		kept = self.run_filter("list_sites", rows, listed=["quest-dev.example.com"])
		self.assertEqual(kept, [{"name": "quest-dev.example.com"}])

	def test_an_all_sites_role_keeps_everything(self):
		rows = [{"name": "a"}, {"name": "b"}]
		self.assertEqual(self.run_filter("list_sites", rows, all_access=True), rows)

	def test_agent_jobs_keep_listed_sites_and_benches_only(self):
		rows = [
			{"name": "j1", "site": "quest-dev.example.com"},
			{"name": "j2", "site": "prime.example.com"},
			{"name": "j3", "bench": "bench-0080-000001"},
			{"name": "j4", "server": "f1.example.com"},
		]
		with patch.object(roles.frappe, "get_all", return_value=[("bench-0080-000001", "bench-0080")]):
			kept = self.run_filter("agent_job_list", rows, listed=["quest-dev.example.com", "bench-0080"])
		self.assertEqual([r["name"] for r in kept], ["j1", "j3"])

	def test_other_tools_pass_through(self):
		self.assertEqual(self.run_filter("site_status", {"name": "x"}), {"name": "x"})
