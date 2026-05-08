# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.mcp_server.script_runner import (
	MAX_TIMEOUT_SECONDS,
	bench_run_repo_script,
	validate_script_request,
)


class TestScriptRunner(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		# Default test allowlist
		self._patch_allowlist = patch(
			"press.mcp_server.script_runner._get_repo_allowlist",
			return_value=["accurate-systems/wazin_mx"],
		)
		self._patch_allowlist.start()
		self.addCleanup(self._patch_allowlist.stop)

	def test_validate_rejects_bad_repo_format(self):
		with self.assertRaises(frappe.ValidationError):
			validate_script_request("noslashrepo", "main", "scripts/x.py")

	def test_validate_rejects_non_py_extension(self):
		with self.assertRaises(frappe.ValidationError):
			validate_script_request("accurate-systems/wazin_mx", "main", "run.sh")

	def test_validate_rejects_traversal_in_path(self):
		with self.assertRaises(frappe.ValidationError):
			validate_script_request(
				"accurate-systems/wazin_mx", "main", "scripts/../etc/x.py"
			)

	def test_validate_rejects_repo_not_in_allowlist(self):
		with self.assertRaises(frappe.PermissionError):
			validate_script_request(
				"someone-else/evil-repo", "main", "scripts/x.py"
			)

	def test_validate_rejects_when_allowlist_is_empty(self):
		with patch(
			"press.mcp_server.script_runner._get_repo_allowlist",
			return_value=[],
		):
			with self.assertRaises(frappe.PermissionError) as ctx:
				validate_script_request(
					"accurate-systems/wazin_mx", "main", "scripts/x.py"
				)
			self.assertIn("empty", str(ctx.exception).lower())

	def test_validate_accepts_well_formed_request_in_allowlist(self):
		# No exception
		validate_script_request(
			"accurate-systems/wazin_mx", "main", "scripts/seed_report_data.py"
		)

	def test_bench_run_repo_script_happy_path(self):
		"""Happy path: validation passes, GitHub fetch returns content,
		run_python_on_site is invoked with the script as `code`."""
		fake_site = "wazin-mx-demo.sandbox.mvpstorm.com"

		def fake_get_value(doctype, filters, fieldname, **kw):
			if doctype == "Site":
				return fake_site
			return None

		fake_response = MagicMock(status_code=200, content=b"print('hi')\n", text="print('hi')\n")
		fake_response.raise_for_status = MagicMock()
		with patch(
			"press.mcp_server.script_runner.frappe.db.get_value",
			side_effect=fake_get_value,
		), patch(
			"press.mcp_server.script_runner.requests.get",
			return_value=fake_response,
		), patch(
			"press.press.doctype.bench.bench_dev_overview.run_python_on_site",
			return_value="hi",
		) as m_run:
			result = bench_run_repo_script(
				bench_name="bench-001",
				repo="accurate-systems/wazin_mx",
				branch="main",
				script_path="scripts/x.py",
			)
		self.assertEqual(result["site"], fake_site)
		self.assertEqual(result["repo"], "accurate-systems/wazin_mx")
		self.assertEqual(result["bytes_fetched"], len("print('hi')\n"))
		# run_python_on_site received the fetched script as `code`
		_, kwargs = m_run.call_args
		self.assertEqual(kwargs.get("code"), "print('hi')\n")
		self.assertEqual(kwargs.get("site_name"), fake_site)

	def test_bench_run_repo_script_clamps_timeout(self):
		"""timeout_seconds outside 1..600 must be clamped, not raised."""
		fake_response = MagicMock(status_code=200, content=b"x", text="x")
		fake_response.raise_for_status = MagicMock()
		with patch(
			"press.mcp_server.script_runner.frappe.db.get_value",
			return_value="site.example.com",
		), patch(
			"press.mcp_server.script_runner.requests.get",
			return_value=fake_response,
		), patch(
			"press.press.doctype.bench.bench_dev_overview.run_python_on_site",
			return_value="ok",
		):
			# Should not raise on extreme values
			bench_run_repo_script(
				bench_name="b1",
				repo="accurate-systems/wazin_mx",
				branch="main",
				script_path="x.py",
				timeout_seconds=99999,
			)
			bench_run_repo_script(
				bench_name="b1",
				repo="accurate-systems/wazin_mx",
				branch="main",
				script_path="x.py",
				timeout_seconds=0,
			)

	def test_bench_run_repo_script_no_active_site_raises(self):
		"""When bench has no Active site and site_name is omitted, raise."""
		with patch(
			"press.mcp_server.script_runner.frappe.db.get_value",
			return_value=None,
		):
			with self.assertRaises(frappe.ValidationError):
				bench_run_repo_script(
					bench_name="empty-bench",
					repo="accurate-systems/wazin_mx",
					branch="main",
					script_path="x.py",
				)

	def test_bench_run_repo_script_github_404_raises(self):
		"""GitHub returning 404 should surface as ValidationError."""
		fake_response = MagicMock(status_code=404, content=b"Not Found", text="Not Found")
		with patch(
			"press.mcp_server.script_runner.frappe.db.get_value",
			return_value="site.example.com",
		), patch(
			"press.mcp_server.script_runner.requests.get",
			return_value=fake_response,
		):
			with self.assertRaises(frappe.ValidationError):
				bench_run_repo_script(
					bench_name="b1",
					repo="accurate-systems/wazin_mx",
					branch="main",
					script_path="missing.py",
				)
