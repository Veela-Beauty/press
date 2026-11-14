from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.api.site import get_analyze_result

SITE = "scan-test.example.com"


def scan_job(status, traceback=None, data=None):
	job = frappe._dict(status=status, traceback=traceback, data=data)
	original = frappe.db.get_value

	def get_value(doctype, *args, **kwargs):
		return job if doctype == "Agent Job" else original(doctype, *args, **kwargs)

	return patch.object(frappe.db, "get_value", side_effect=get_value)


class TestRestoreScanResult(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_scan_the_agent_rejected_lets_the_restore_go_on(self):
		with scan_job("Undelivered", traceback="Status Code: 500 ... NotFound"):
			self.assertEqual(get_analyze_result(name=SITE, job_name="j1")["status"], "Failure")

	def test_scan_given_up_after_retries_lets_the_restore_go_on(self):
		with scan_job("Delivery Failure", traceback="timeout"):
			self.assertEqual(get_analyze_result(name=SITE, job_name="j1")["status"], "Failure")

	def test_scan_not_sent_yet_keeps_waiting(self):
		with scan_job("Undelivered"):
			self.assertEqual(get_analyze_result(name=SITE, job_name="j1")["status"], "Undelivered")

	def test_finished_scan_returns_the_tables(self):
		with scan_job("Success", data='{"noise_tables": ["tabError Log"]}'):
			result = get_analyze_result(name=SITE, job_name="j1")
		self.assertEqual(result["data"]["noise_tables"], ["tabError Log"])

	def test_failed_scan_reports_the_error(self):
		with scan_job("Failure", traceback="boom"):
			self.assertRaises(frappe.ValidationError, get_analyze_result, name=SITE, job_name="j1")
