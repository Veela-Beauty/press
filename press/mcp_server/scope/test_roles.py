from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from press.mcp_server.scope import roles

GUARD = "press.mcp_server.scope.roles.role_guard"
LISTED = {"Site": {"quest-dev.example.com"}, "Release Group": {"bench-0080"}, "Server": set()}
DB = {
	("Site", "quest-dev.example.com", "bench"): "bench-0080-000001",
	("Bench", "bench-0080-000001", "group"): "bench-0080",
	("Bench", "bench-0006-000001", "group"): "bench-0006",
	("Agent Job", "job-site", ("site", "bench", "server")): {
		"site": "quest-dev.example.com",
		"bench": "bench-0006-000001",
	},
	("Agent Job", "job-server", ("site", "bench", "server")): {"server": "f1.example.com"},
	# the call guard's and the target extractor's own reads of the same jobs
	("Agent Job", "job-site", "site"): "quest-dev.example.com",
	("Agent Job", "job-site", ("site", "bench")): {
		"site": "quest-dev.example.com",
		"bench": "bench-0006-000001",
	},
	("Agent Job", "job-server", ("site", "bench")): {"site": None, "bench": None},
}


def guard(limited=True):
	g = MagicMock()
	g.is_restricted.return_value = limited
	g.skip_roles.return_value = False
	return g


def get_value(doctype, name, field, **kwargs):
	return DB.get((doctype, name, tuple(field) if isinstance(field, list) else field))


class TestAssertCallInRoles(TestCase):
	def run_call(self, tool, args, resources, limited=True, listed=LISTED):
		with (
			patch(GUARD, guard(limited)),
			patch.object(roles, "_resources_of_call", return_value=resources),
			patch.object(roles, "_visible", side_effect=lambda doctype: listed.get(doctype)) as visible,
		):
			roles.assert_call_in_roles(tool, args)
		return visible

	def test_unlimited_member_is_not_checked(self):
		visible = self.run_call("site_status", {}, {"Site": {"prime.example.com"}}, limited=False)
		visible.assert_not_called()

	def test_listed_site_and_bench_pass(self):
		self.run_call(
			"bench_restart", {}, {"Site": {"quest-dev.example.com"}, "Release Group": {"bench-0080"}}
		)

	def test_unlisted_site_is_refused_with_the_not_visible_message(self):
		with self.assertRaises(frappe.PermissionError) as raised:
			self.run_call("site_status", {}, {"Site": {"prime.example.com"}})
		self.assertIn(
			"'prime.example.com' was not found, or is not in this token's team", str(raised.exception)
		)

	def test_unlisted_server_is_refused(self):
		with self.assertRaises(frappe.PermissionError):
			self.run_call("host_memory_pressure", {}, {"Server": {"f1.example.com"}})

	def test_an_all_servers_role_passes_any_server(self):
		self.run_call("host_memory_pressure", {}, {"Server": {"f1.example.com"}}, listed={"Server": None})

	def test_dashboard_login_is_refused_for_a_limited_member(self):
		with patch(GUARD, guard()), self.assertRaises(frappe.PermissionError):
			roles.assert_call_in_roles("mint_dashboard_login_url", {})


class TestResourcesOfCall(TestCase):
	def resources(self, tool, args):
		with patch.object(frappe.db, "get_value", side_effect=get_value):
			return roles._resources_of_call(tool, args)

	def test_a_plain_site_action_needs_the_site_only(self):
		found = self.resources("site_status", {"site_name": "quest-dev.example.com"})
		self.assertEqual(found["Site"], {"quest-dev.example.com"})
		self.assertEqual(found["Release Group"], set())

	def test_code_inside_the_container_also_needs_the_bench(self):
		found = self.resources("site_run_sql", {"site_name": "quest-dev.example.com", "query": "select 1"})
		self.assertEqual(found["Release Group"], {"bench-0080"})

	def test_target_bench_is_checked(self):
		found = self.resources(
			"clone_site", {"site": "quest-dev.example.com", "target_bench": "bench-0006-000001"}
		)
		self.assertIn("bench-0006", found["Release Group"])

	def test_a_site_job_needs_its_site_not_its_bench(self):
		found = self.resources("agent_job_progress", {"job_name": "job-site"})
		self.assertEqual(found["Site"], {"quest-dev.example.com"})
		self.assertNotIn("bench-0006", found["Release Group"])

	def test_a_server_job_needs_its_server(self):
		found = self.resources("agent_job_traceback", {"job_name": "job-server"})
		self.assertEqual(found["Server"], {"f1.example.com"})


class TestFilterToRoles(TestCase):
	def run_filter(self, tool, response, listed=LISTED):
		with (
			patch(GUARD, guard()),
			patch.object(roles, "_visible", side_effect=lambda doctype: listed.get(doctype)),
		):
			return roles.filter_to_roles(tool, response)

	def test_list_sites_keeps_only_listed_sites(self):
		rows = [{"name": "quest-dev.example.com"}, {"name": "prime.example.com"}]
		self.assertEqual(self.run_filter("list_sites", rows), [{"name": "quest-dev.example.com"}])

	def test_list_release_groups_keeps_only_listed_benches(self):
		rows = [{"name": "bench-0080"}, {"name": "bench-0006"}]
		self.assertEqual(self.run_filter("list_release_groups", rows), [{"name": "bench-0080"}])

	def test_an_all_sites_role_keeps_everything(self):
		rows = [{"name": "a"}, {"name": "b"}]
		self.assertEqual(self.run_filter("list_sites", rows, listed={"Site": None}), rows)

	def test_an_unknown_shape_shows_nothing(self):
		self.assertEqual(self.run_filter("list_sites", {"data": [{"name": "prime.example.com"}]}), [])

	def test_agent_jobs_keep_listed_sites_and_benches_only(self):
		rows = [
			{"name": "j1", "site": "quest-dev.example.com"},
			{"name": "j2", "site": "prime.example.com"},
			{"name": "j3", "bench": "bench-0080-000001"},
			{"name": "j4", "server": "f1.example.com"},
		]
		with patch.object(roles.frappe, "get_all", return_value=[("bench-0080-000001", "bench-0080")]):
			kept = self.run_filter("agent_job_list", rows)
		self.assertEqual([r["name"] for r in kept], ["j1", "j3"])

	def test_other_tools_pass_through(self):
		self.assertEqual(self.run_filter("site_status", {"name": "x"}), {"name": "x"})
