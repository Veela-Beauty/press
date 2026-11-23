# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""MCP Agent Watch (0.7.59). No database write, no Redis write, no email (on the press-ctrl test runner's MOCK_ONLY
list). Two tests run read-only SELECTs: the MariaDB secret pattern itself, and every query of the watch."""

import json
import pathlib
from datetime import datetime
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from press.watch_tower import email_branding
from press.watch_tower.alerts import mcp_agent_watch as watch

NOW = datetime(2026, 11, 23, 10, 30)
PRESS = pathlib.Path(__file__).parents[
	2
]  # this file's own tree (the press-ctrl runner copies the tree with it)


class FakeCache:
	def __init__(self):
		self.data = {}

	def get_value(self, key, expires=False):
		return self.data.get(key)

	def set_value(self, key, value, expires_in_sec=None):
		self.data[key] = value


def _call(name, tool, args, token="MCPT-1", user="dev@example.com"):
	args_json = args if isinstance(args, str) else json.dumps(args)
	return frappe._dict(name=name, tool=tool, token=token, user=user, creation=NOW, args_json=args_json)


class TestPatterns(FrappeTestCase):
	def test_destructive_sql(self):
		cases = [
			("site_run_sql", "DELETE FROM `tabToDo`", True, True),
			("site_run_sql", "DELETE FROM `tabToDo` WHERE name = 'x'", True, False),
			("site_run_sql", "UPDATE tabUser SET enabled = 0", True, True),
			("site_run_sql", "update tabUser set enabled = 0 where name = 'a'; select 1", True, False),
			("site_run_sql", "/* tidy */ DELETE FROM tabToDo", True, True),
			("site_run_sql", "(DELETE FROM tabToDo)", True, True),
			("site_run_sql", "UPDATE tabToDo SET a = (SELECT b FROM tabX WHERE c = 1)", True, True),
			("site_run_sql", "UPDATE tabToDo SET note = 'see where' ", True, True),
			("site_run_sql", "DROP TABLE `tabToDo`", True, True),
			("site_run_sql", "DROP TABLE `tabToDo`", False, False),  # refused without commit, so not damage
			("site_run_python", "frappe.db.sql('truncate `tabError Log`')", False, True),
			("site_run_python", "frappe.db.sql('TRUNCATE TABLE __global_search')", False, True),
			("site_run_python", "f = open('x', 'r+'); f.truncate(10)", False, False),
			("site_run_python", "# truncate the list first", False, False),
			("site_run_python", "print(frappe.get_all('Site'))", False, False),
			("site_run_sql", "SELECT name FROM tabUser", True, False),
		]
		for tool, text, commit, expected in cases:
			with self.subTest(text=text, commit=commit):
				self.assertEqual(watch.is_destructive(tool, text, commit), expected)

	def test_secret_hunt(self):
		for text in (
			"frappe.utils.password.get_decrypted_password('User', 'a', 'api_secret')",
			"select * from __Auth",
			"print(frappe.conf.db_password)",
			"open('/home/frappe/.ssh/id_rsa').read()",
		):
			with self.subTest(text=text):
				self.assertTrue(watch.SECRET_HUNT.search(text))
		for text in (
			"print(frappe.conf.host_name)",
			"frappe.get_all('Site', pluck='name')",
			"frappe.get_site_config()",
		):
			with self.subTest(text=text):
				self.assertFalse(watch.SECRET_HUNT.search(text))

	def test_secret_value_pattern_matches_a_value_not_a_hidden_one(self):
		real = '{\\"db_password\\": \\"Zx81kQ0pLm2Vn7Rt4Ws\\"}'
		hidden = '{\\"db_password\\": \\"(hidden)\\"}'

		def match(s):
			return frappe.db.sql("SELECT %s REGEXP %s", (s, watch.SECRET_VALUE))[0][0]

		self.assertEqual((match(real), match(hidden)), (1, 0))

	def test_code_events_name_the_row_and_read_cut_json_as_text(self):
		cut = '{"query": "DELETE FROM tabToDo", "commit": true, "site_name": "x", "pad": "' + "a" * 40
		rows = [
			_call("MCPC-1", "site_run_sql", {"query": "DELETE FROM tabToDo", "commit": True}),
			_call("MCPC-2", "site_run_python", {"code": "frappe.get_password('User', 'a', 'api_key')"}),
			_call("MCPC-3", "site_run_python", {"code": "print(1)"}),
			_call("MCPC-4", "site_run_sql", cut),  # cut at the log limit: not valid JSON
		]
		with patch.object(watch.frappe.db, "sql", return_value=rows):
			events = watch._code_events(NOW, NOW)
		self.assertEqual(
			[(e["pattern"], e["call"]) for e in events],
			[("destructive", "MCPC-1"), ("secret hunt", "MCPC-2"), ("destructive", "MCPC-4")],
		)

	def test_every_query_runs_on_the_database(self):
		"""Read-only: the real SQL of all six patterns (tuple IN, %% escaping, REGEXP) runs without an error."""
		events = watch.find_events(now_datetime())
		self.assertIsInstance(events, list)

	def test_refusals_and_runaways_use_clock_hours(self):
		with (
			patch.object(watch, "row_events", return_value=[]),
			patch.object(watch, "hour_events", return_value=[]) as hours,
		):
			watch.find_events(NOW)
		self.assertEqual(
			[(c.args[0].hour, c.args[1].hour) for c in hours.call_args_list], [(7, 8), (8, 9), (9, 10)]
		)


class TestEvaluation(FrappeTestCase):
	def _events(self, n=2):
		return [
			watch._event("secret hunt", _call(f"MCPC-{i}", "site_run_python", {})) for i in range(1, n + 1)
		]

	def _run(self, seen, events=None, sent=True):
		inserted = []

		def get_doc(d):
			inserted.append(d)
			return frappe._dict(insert=lambda **kw: None)

		with (
			patch.object(watch, "find_events", return_value=events or self._events()),
			patch.object(watch.frappe, "get_all", return_value=seen),
			patch.object(watch.frappe, "get_doc", side_effect=get_doc),
			patch.object(email_branding, "send_alert_email", return_value=sent) as send,
		):
			result = watch._eval_mcp_agent_watch(frappe._dict(name="WT-RULE-1"), now=NOW)
		return result, inserted, send

	def test_new_events_are_sent_in_one_email_then_recorded(self):
		result, inserted, send = self._run(seen=["secret hunt:MCPC-1"])
		self.assertTrue(result)
		self.assertEqual([d["target_document_name"] for d in inserted], ["secret hunt:MCPC-2"])
		send.assert_called_once()
		self.assertIn("MCPC-2", send.call_args.kwargs["message"])
		self.assertNotIn("MCPC-1<", send.call_args.kwargs["message"])

	def test_nothing_new_sends_nothing(self):
		result, inserted, send = self._run(seen=["secret hunt:MCPC-1", "secret hunt:MCPC-2"])
		self.assertEqual((result, inserted), (False, []))
		send.assert_not_called()

	def test_a_refused_email_records_nothing_so_the_next_run_sends_again(self):
		result, inserted, send = self._run(seen=[], sent=False)
		self.assertEqual((result, inserted), (False, []))
		send.assert_called_once()

	def test_beyond_the_listed_fifty_every_event_is_still_recorded(self):
		result, inserted, send = self._run(seen=[], events=self._events(60))
		self.assertEqual(len(inserted), 60)
		self.assertIn("60 new MCP agent event(s)", send.call_args.kwargs["message"])
		self.assertIn("the first 50 below", send.call_args.kwargs["message"])

	def test_the_alert_log_row_holds_no_code_sql_or_user(self):
		_, inserted, _ = self._run(seen=[])
		for d in inserted:
			self.assertEqual(
				set(d) - {"doctype"},
				{
					"rule",
					"rule_name",
					"status",
					"alert_datetime",
					"triggered_by",
					"target_doctype",
					"target_document",
					"target_document_name",
					"action_summary",
				},
			)
			self.assertNotIn("dev@example.com", json.dumps(d, default=str))

	def test_runs_once_for_many_candidates(self):
		with (
			patch.object(watch.frappe, "cache", return_value=FakeCache()),
			patch.object(watch, "_eval_mcp_agent_watch", return_value=False) as ev,
			patch.object(watch.frappe, "log_error"),
		):
			results = [watch.check_mcp_agent_watch({"name": f"server-{i}"}, None) for i in range(4)]
		self.assertEqual((results, ev.call_count), ([False] * 4, 1))


class TestNoiseAndAccess(FrappeTestCase):
	def test_successful_risky_calls_write_no_error_log_line(self):
		self.assertNotIn("MCP-DESTRUCTIVE", (PRESS / "mcp_server" / "server.py").read_text())

	def test_only_mcp_auditor_reads_the_call_log(self):
		meta = json.loads(
			(PRESS / "press" / "doctype" / "press_mcp_call_log" / "press_mcp_call_log.json").read_text()
		)
		self.assertEqual([p["role"] for p in meta["permissions"]], ["MCP Auditor"])

	def test_every_user_no_longer_reads_the_alert_log(self):
		meta = json.loads((PRESS / "watch_tower" / "doctype" / "watch_tower_alert_log" / "watch_tower_alert_log.json").read_text())
		self.assertEqual([p["role"] for p in meta["permissions"]], ["System Manager"])
