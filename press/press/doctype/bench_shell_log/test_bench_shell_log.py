# Copyright (c) 2024, Frappe and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from press.press.doctype.bench_shell_log.bench_shell_log import create_bench_shell_log


def _fake_result() -> dict:
	return {
		"command": "bash -c 'echo hello'",
		"status": "Success",
		"output": "hello\n",
		"start": "2026-05-19T12:00:00",
		"end": "2026-05-19T12:00:01",
		"returncode": 0,
		"traceback": "",
		"directory": "/home/frappe/frappe-bench",
		"duration": 1.0,
	}


class TestBenchShellLog(FrappeTestCase):
	def test_create_bench_shell_log_as_non_system_user_does_not_raise(self):
		# REGRESSION: Bench Shell Log doctype grants create perm only to
		# System Manager. Every dashboard dev feature that uses
		# Bench.docker_execute (bench dev watch, bench dev overview's
		# run_python_on_site / run_sql_on_site, app management, etc.)
		# hits create_bench_shell_log on every call. Non-System team users
		# would throw "No permission for Bench Shell Log" and the
		# 10-second-poll Bench Watch panel would flood the user's screen
		# with the error. Reported 2026-05-19 by ahmedmowafy74@gmail.com.
		#
		# Fix: insert with ignore_permissions=True so audit logging
		# survives the role gap. The `owner` field still captures the
		# real session user, so the audit trail stays intact.
		test_user_email = "test-team-user-bsl@example.com"
		if not frappe.db.exists("User", test_user_email):
			frappe.get_doc({
				"doctype": "User",
				"email": test_user_email,
				"first_name": "Test",
				"user_type": "Website User",
				"send_welcome_email": 0,
			}).insert(ignore_permissions=True)
			frappe.db.commit()
		self.addCleanup(
			lambda: frappe.delete_doc("User", test_user_email, force=True, ignore_permissions=True)
		)

		# Use any existing Bench docname — the FK only enforces existence
		bench_name = frappe.db.get_value("Bench", {}, "name")
		if not bench_name:
			self.skipTest("No Bench docs in test fixture")

		frappe.set_user(test_user_email)
		try:
			create_bench_shell_log(
				res=_fake_result(),
				bench=bench_name,
				cmd="echo hello",
				subdir=None,
				save_output=True,
			)
		finally:
			frappe.set_user("Administrator")

		# Find the row this user just inserted, assert owner reflects them
		rows = frappe.get_all(
			"Bench Shell Log",
			filters={"bench": bench_name, "owner": test_user_email},
			fields=["name", "owner", "cmd"],
			order_by="creation desc",
			limit=1,
		)
		self.assertEqual(len(rows), 1, "Bench Shell Log row not inserted for non-System user")
		self.assertEqual(rows[0]["owner"], test_user_email)
		self.assertEqual(rows[0]["cmd"], "echo hello")
		# Clean up the test row we just created
		frappe.delete_doc(
			"Bench Shell Log", rows[0]["name"], force=True, ignore_permissions=True
		)
		frappe.db.commit()
