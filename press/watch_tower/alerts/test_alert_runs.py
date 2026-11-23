# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""The Watch Tower fixes of 2026-11-23, pinned: Frappe's clock in every window (0.7.48), a global check runs once per
evaluation (0.7.50, 0.7.52), a refused alert email says why and reports False (0.7.51, 0.7.52).

Mock-only: no database write, no Redis write, no email sent (it is on the press-ctrl test runner's MOCK_ONLY list).
"""

from __future__ import annotations

import ast
import contextlib
import logging
import pathlib
import re
import smtplib
from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_datetime

from press.watch_tower import email_branding
from press.watch_tower._hard_timeout import HardTimeoutError
from press.watch_tower.alerts import deploy_alerts, mcp_alerts, scheduler_alerts, site_alerts

WATCH_TOWER = pathlib.Path(email_branding.__file__).parent
SQL_WORD = re.compile(r"\b(select|update|delete|where|interval|datediff|timestampdiff)\b", re.I)
DB_CLOCK = re.compile(r"\bnow\(\)", re.I)


class FakeCache:
	"""Stands in for frappe.cache() so the memo is tested without touching the real Redis."""

	def __init__(self):
		self.data = {}

	def get_value(self, key, expires=False):
		return self.data.get(key)

	def set_value(self, key, value, expires_in_sec=None):
		self.data[key] = value


def _strings_outside_docstrings(tree):
	docstrings = {
		id(node.body[0].value)
		for node in ast.walk(tree)
		if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
		and node.body
		and isinstance(node.body[0], ast.Expr)
		and isinstance(node.body[0].value, ast.Constant)
	}
	for node in ast.walk(tree):
		if isinstance(node, ast.JoinedStr):
			yield node.lineno, "".join(v.value for v in node.values if isinstance(v, ast.Constant))
		elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
			yield node.lineno, node.value


class TestFrappeClock(FrappeTestCase):
	def test_no_watch_tower_query_uses_the_database_clock(self):
		"""press-ctrl's database NOW() is UTC while Frappe writes creation and modified in Asia/Riyadh: a NOW() window
		read 4 hours as "the last hour". Every query takes Frappe's time (alerts/_helpers.now_sql)."""
		offenders = []
		for path in sorted(WATCH_TOWER.rglob("*.py")):
			if path.name.startswith("test_"):
				continue
			for lineno, text in _strings_outside_docstrings(ast.parse(path.read_text())):
				if DB_CLOCK.search(text) and SQL_WORD.search(text):
					offenders.append(f"{path.relative_to(WATCH_TOWER)}:{lineno}")
		self.assertEqual(
			offenders, [], "use now_sql() or add_to_date(now_datetime(), ...), not the database NOW()"
		)

	def test_the_mcp_slow_check_takes_its_cutoffs_from_frappes_clock(self):
		fixed = get_datetime("2026-11-23 13:00:00")
		seen = {}

		def sql(query, params=None, **kwargs):
			seen.update(query=query, params=params)
			return []

		with (
			patch.object(mcp_alerts, "now_datetime", return_value=fixed),
			patch.object(mcp_alerts.frappe.db, "sql", side_effect=sql),
		):
			self.assertFalse(mcp_alerts._eval_mcp_calls_slow())
		self.assertEqual(seen["params"]["hour_ago"], fixed - timedelta(hours=1))
		self.assertEqual(seen["params"]["week_ago"], fixed - timedelta(days=7))
		self.assertIsNone(DB_CLOCK.search(seen["query"]))


class TestOncePerEvaluation(FrappeTestCase):
	@staticmethod
	def _spike_sql(query, *args, **kwargs):
		if "GROUP BY method" in query:  # the top errors (it holds COUNT(*) too, so it is checked first)
			return [frappe._dict(method="m", cnt=500)]
		if "COUNT(*)" in query:
			return [[500]]
		return []  # the most recent errors

	def test_the_error_spike_check_runs_once_for_many_candidates_and_keeps_the_throttle(self):
		for allowed, sends in ((True, 1), (False, 0)):
			with (
				patch.object(scheduler_alerts.frappe, "cache", return_value=FakeCache()),
				patch.object(scheduler_alerts.frappe.db, "sql", side_effect=self._spike_sql) as sql,
				patch.object(scheduler_alerts, "should_send_alert", return_value=allowed),
				patch.object(scheduler_alerts, "_send_error_spike_email") as send,
				patch.object(scheduler_alerts.frappe, "log_error"),  # a failing check must not write an Error Log
			):
				results = [
					scheduler_alerts.check_error_log_spike({"name": f"server-{i}"}, None) for i in range(4)
				]
			self.assertEqual(results, [True] * 4)
			self.assertEqual(send.call_count, sends)
			self.assertLessEqual(sql.call_count, 3)  # one evaluation: count, top errors, recent

	def test_the_failed_deploy_check_queries_once_for_many_candidates(self):
		with (
			patch.object(deploy_alerts.frappe, "cache", return_value=FakeCache()),
			patch.object(deploy_alerts.frappe.db, "sql", return_value=[]) as sql,
			patch.object(deploy_alerts.frappe, "log_error"),
		):
			results = [deploy_alerts.check_failed_deploys({"name": f"server-{i}"}, None) for i in range(4)]
		self.assertEqual((results, sql.call_count), ([False] * 4, 1))

	def test_the_pending_build_check_reads_builds_once_for_many_benches(self):
		"""WT-RULE-1208 failed on all 4,501 benches every day: it read `status` from Deploy Candidate (0.7.58)."""
		with (
			patch.object(site_alerts.frappe, "cache", return_value=FakeCache()),
			patch.object(site_alerts.frappe.db, "sql", return_value=[]) as sql,
			patch.object(site_alerts.frappe, "log_error") as log_error,
		):
			results = [site_alerts.check_bench_updates_pending({"name": f"bench-{i}"}, None) for i in range(4)]
		self.assertEqual((results, sql.call_count), ([False] * 4, 1))
		log_error.assert_not_called()
		query = sql.call_args[0][0]
		self.assertIn("FROM `tabDeploy Candidate Build`", query)
		self.assertIn("status IN ('Draft', 'Pending')", query)
		self.assertIn("INTERVAL 30 DAY", query)

	def test_a_build_that_never_started_sends_one_email_for_many_benches(self):
		row = frappe._dict(name="ttso2sautm", group="bench-0034", status="Draft", days_old=5)
		with (
			patch.object(site_alerts.frappe, "cache", return_value=FakeCache()),
			patch.object(site_alerts.frappe.db, "sql", return_value=[row]),
			patch.object(site_alerts, "should_send_alert", return_value=True),
			patch.object(email_branding, "send_alert_email") as send,
			patch.object(site_alerts.frappe, "log_error"),
		):
			results = [site_alerts.check_bench_updates_pending({"name": f"bench-{i}"}, None) for i in range(4)]
		self.assertEqual(results, [True] * 4)
		send.assert_called_once()
		self.assertIn("ttso2sautm", send.call_args.kwargs["message"])


class AcceptingSMTP:
	def __init__(self, *args, **kwargs):
		pass

	def __enter__(self):
		return self

	def __exit__(self, *args):
		return False

	def starttls(self):
		pass

	def login(self, *args):
		pass

	def sendmail(self, *args):
		return {}


class RefusingSMTP(AcceptingSMTP):
	def sendmail(self, *args):
		raise smtplib.SMTPDataError(421, b"too many messages, slow down")


@contextlib.contextmanager
def _timing_out(seconds):
	raise HardTimeoutError("Hard timeout exceeded")
	yield  # never reached: makes this a generator for contextmanager


SMTP_CFG = {
	"server": "smtp.example.test",
	"port": 587,
	"login": "l",
	"password": "p",
	"sender": "S <s@example.test>",
	"use_tls": True,
}


class TestAlertEmailResult(FrappeTestCase):
	def _send(self, smtp=AcceptingSMTP, timeout=None):
		logger = logging.getLogger("test_alert_runs")
		records = []
		handler = logging.Handler()
		handler.emit = records.append
		logger.addHandler(handler)
		patches = [
			patch.object(email_branding, "_get_smtp_config", return_value=dict(SMTP_CFG)),
			patch.object(email_branding.smtplib, "SMTP", smtp),
			patch.object(frappe, "logger", return_value=logger),  # nothing written to watch_tower.log
		]
		if timeout:
			patches.append(patch.object(email_branding, "hard_timeout", timeout))
		try:
			with contextlib.ExitStack() as stack:
				for p in patches:
					stack.enter_context(p)
				ok = email_branding.send_alert_email(
					recipients=["x@example.test"], subject="TEST", message="<p>x</p>"
				)
		finally:
			logger.removeHandler(handler)
		return ok, [r.getMessage() for r in records]

	def test_a_relay_that_takes_it_reports_true_and_logs_nothing(self):
		self.assertEqual(self._send(), (True, []))

	def test_a_refusal_reports_false_with_the_relays_reason(self):
		ok, messages = self._send(RefusingSMTP)
		self.assertFalse(ok)
		self.assertEqual(len(messages), 1)
		self.assertIn("SMTPDataError: (421, b'too many messages, slow down')", messages[0])

	def test_a_hard_timeout_reports_false_not_sent(self):
		ok, messages = self._send(timeout=_timing_out)
		self.assertFalse(ok)
		self.assertIn("HardTimeoutError", messages[0])
