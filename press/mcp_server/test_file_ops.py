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

	def _fake_bench(self, sent, common, site_conf):
		"""A site and bench whose docker_execute runs the sent code here, in a folder laid out like a bench."""
		import base64
		import contextlib
		import io
		import json
		import os
		import re
		import tempfile
		from types import SimpleNamespace

		def docker_execute(cmd):
			sent.append(cmd)
			code = base64.b64decode(re.search(r"echo (\S+) \|", cmd).group(1)).decode()
			out, cwd = io.StringIO(), os.getcwd()
			with tempfile.TemporaryDirectory() as root:
				os.makedirs(os.path.join(root, "sites", "x.example.com"))
				for path, data in (
					("sites/common_site_config.json", common),
					("sites/x.example.com/site_config.json", site_conf),
				):
					with open(os.path.join(root, path), "w") as f:
						json.dump(data, f)
				os.chdir(root)
				try:
					with contextlib.redirect_stdout(out):
						exec(code, {}, {})
				finally:
					os.chdir(cwd)
			return {"output": out.getvalue(), "returncode": 0}

		return SimpleNamespace(name="x.example.com"), SimpleNamespace(docker_execute=docker_execute)

	def _config_get(self, sent, common, site_conf, **kwargs):
		site_bench = self._fake_bench(sent, common, site_conf)
		with patch("press.utils.ensure_team_access"), patch(
			"press.press.doctype.bench.bench_dev_overview._get_site_bench", return_value=site_bench
		):
			return site_config_get(site_name="x.example.com", **kwargs)

	def test_site_config_get_reads_both_files_with_plain_python(self):
		"""The site's file wins over the bench's common file, as in frappe.conf; no bench console start (0.7.47)."""
		sent = []
		common = {"developer_mode": 0, "webserver_port": 8000, "db_host": "10.0.0.1"}
		result = self._config_get(sent, common, {"developer_mode": 1, "host_name": "https://x.example.com"})
		self.assertEqual(
			result,
			{"developer_mode": 1, "webserver_port": 8000, "db_host": "10.0.0.1", "host_name": "https://x.example.com"},
		)
		self.assertEqual(self._config_get(sent, common, {}, key="webserver_port"), {"key": "webserver_port", "value": 8000})
		self.assertTrue(all("env/bin/python -" in cmd and "bench --site" not in cmd for cmd in sent))

	def test_site_config_get_hides_every_secret_on_the_site_itself(self):
		"""The hiding runs in the code sent to the site: db_password* and encryption_key* are left out, app secrets and
		URL passwords come back as (hidden), and neither reaches the answer or the command Press logs."""
		sent = []
		common = {"redis_cache": "redis://:pw@localhost:13000", "redis_queue": "redis://u:pw@h:11000/0"}
		site_conf = {
			"db_password": "pw", "encryption_key": "pw", "sanad_review_seal_key": "pw",
			"sanad_review_converter_password": "pw", "some_api_token": "pw", "client_secret": "pw",
			"host_name": "https://x.example.com",
		}
		result = self._config_get(sent, common, site_conf)
		self.assertEqual(
			result,
			{
				"redis_cache": "redis://:(hidden)@localhost:13000", "redis_queue": "redis://u:(hidden)@h:11000/0",
				"sanad_review_seal_key": "(hidden)", "sanad_review_converter_password": "(hidden)",
				"some_api_token": "(hidden)", "client_secret": "(hidden)", "host_name": "https://x.example.com",
			},
		)
		key = self._config_get(sent, common, site_conf, key="sanad_review_seal_key")
		self.assertEqual(key, {"key": "sanad_review_seal_key", "value": "(hidden)"})
		self.assertFalse(any("pw" in cmd for cmd in sent))

	def test_site_config_get_reports_a_failed_read(self):
		from types import SimpleNamespace

		bench = SimpleNamespace(docker_execute=lambda cmd: {"output": "FileNotFoundError", "returncode": 1})
		with patch("press.utils.ensure_team_access"), patch(
			"press.press.doctype.bench.bench_dev_overview._get_site_bench",
			return_value=(SimpleNamespace(name="x.example.com"), bench),
		):
			result = site_config_get(site_name="x.example.com")
		self.assertEqual(result["error"], "reading the site config failed")

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
