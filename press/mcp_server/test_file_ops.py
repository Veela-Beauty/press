# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.mcp_server.file_ops import (
	_parse_python_output,
	_resolve_site_path,
	_validate_config_key,
	site_config_get,
	site_config_set,
	site_file_read,
	site_file_write,
)


class TestMCPFileOps(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	# --- _validate_config_key ---

	def test_validate_config_key_rejects_db_password(self):
		with self.assertRaises(frappe.PermissionError):
			_validate_config_key("db_password")

	def test_validate_config_key_rejects_encryption_key(self):
		with self.assertRaises(frappe.PermissionError):
			_validate_config_key("encryption_key")

	def test_validate_config_key_rejects_db_password_prefix(self):
		with self.assertRaises(frappe.PermissionError):
			_validate_config_key("db_password_extra")

	def test_validate_config_key_accepts_normal_keys(self):
		_validate_config_key("developer_mode")  # must not raise
		_validate_config_key("disable_mail_notifications")

	def test_validate_config_key_rejects_empty_string(self):
		with self.assertRaises(frappe.ValidationError):
			_validate_config_key("")

	# --- _resolve_site_path ---

	def test_resolve_site_path_rejects_dotdot_traversal(self):
		with self.assertRaises(frappe.ValidationError):
			_resolve_site_path("a.example.com", "public/files/../../etc/passwd")

	def test_resolve_site_path_rejects_outside_allowed_prefix(self):
		with self.assertRaises(frappe.ValidationError):
			_resolve_site_path("a.example.com", "private/keys/secret.pem")

	def test_resolve_site_path_accepts_public_files(self):
		path = _resolve_site_path("a.example.com", "public/files/x.txt")
		self.assertEqual(path, "sites/a.example.com/public/files/x.txt")

	def test_resolve_site_path_accepts_private_files(self):
		path = _resolve_site_path("a.example.com", "private/files/y.txt")
		self.assertEqual(path, "sites/a.example.com/private/files/y.txt")

	# --- site_config_get ---

	def test_site_config_get_blocks_db_password_key(self):
		with self.assertRaises(frappe.PermissionError):
			site_config_get(site_name="x.example.com", key="db_password")

	def test_site_config_get_all_redacts_sensitive_in_output(self):
		"""Even without a specific key, the agent code strips sensitive keys before printing."""
		fake_response = '{"developer_mode": 1, "some_key": "value"}'
		with patch(
			"press.press.doctype.bench.bench_dev_overview.run_python_on_site",
			return_value=fake_response,
		):
			result = site_config_get(site_name="x.example.com")
		self.assertNotIn("db_password", result)
		self.assertEqual(result.get("developer_mode"), 1)

	def test_site_config_get_hides_every_secret_on_the_site_itself(self):
		"""The hiding runs in the code sent to the site, which the bench console runs with globals and locals apart
		(0.7.45 failed there with a NameError): app secrets and URL passwords never reach the answer."""
		import contextlib
		import io
		import json

		from press.mcp_server.file_ops import _site_code

		checks = [
			("sanad_review_seal_key", "abc"), ("sanad_review_converter_password", "abc"), ("some_api_token", "abc"),
			("client_secret", "abc"), ("redis_cache", "redis://:pw@localhost:13000"),
			("redis_queue", "redis://u:pw@h:11000/0"), ("host_name", "https://x.example.com"),
			("db_host", "10.0.0.1"), ("webserver_port", 8000),
		]
		code = _site_code([f"print(json.dumps([clean(k, v) for k, v in {checks!r}]))"])
		self.assertNotIn("\n\n", code)  # a blank line would end the statement in the console
		out = io.StringIO()
		with contextlib.redirect_stdout(out):
			exec(code, {}, {})
		self.assertEqual(
			json.loads(out.getvalue()),
			["(hidden)"] * 4
			+ ["redis://:(hidden)@localhost:13000", "redis://u:(hidden)@h:11000/0", "https://x.example.com", "10.0.0.1", 8000],
		)
		sent = []
		with patch(
			"press.press.doctype.bench.bench_dev_overview.run_python_on_site",
			side_effect=lambda site_name, code: sent.append(code) or '{"key": "x_key", "value": "(hidden)"}',
		):
			site_config_get(site_name="x.example.com")
			site_config_get(site_name="x.example.com", key="sanad_review_seal_key")
		self.assertTrue(all("_press_config()" in code and "clean(" in code for code in sent))

	# --- site_config_set ---

	def test_site_config_set_blocks_encryption_key(self):
		with self.assertRaises(frappe.PermissionError):
			site_config_set(site_name="x.example.com", key="encryption_key", value="evil")

	def test_site_config_set_returns_status_ok(self):
		with patch(
			"press.press.doctype.bench.bench_dev_overview.run_python_on_site",
			return_value="OK",
		):
			result = site_config_set(
				site_name="x.example.com", key="developer_mode", value=1
			)
		self.assertEqual(result["status"], "set")
		self.assertEqual(result["key"], "developer_mode")

	# --- site_file_write ---

	def test_site_file_write_rejects_invalid_encoding(self):
		with self.assertRaises(frappe.ValidationError):
			site_file_write(
				site_name="x.example.com",
				relative_path="public/files/x.txt",
				content="hello",
				encoding="rot13",
			)

	def test_site_file_write_rejects_path_outside_public_private(self):
		with self.assertRaises(frappe.ValidationError):
			site_file_write(
				site_name="x.example.com",
				relative_path="sites/common_site_config.json",
				content="{}",
			)

	# --- _parse_python_output ---

	def test_parse_python_output_parses_last_json_line(self):
		raw = "some preamble\n{\"key\": \"value\"}"
		result = _parse_python_output(raw)
		self.assertEqual(result["key"], "value")

	def test_parse_python_output_wraps_non_json(self):
		result = _parse_python_output("plain text output")
		self.assertIn("raw", result)

	def test_parse_python_output_handles_none(self):
		result = _parse_python_output(None)
		self.assertEqual(result, {"raw": None})
