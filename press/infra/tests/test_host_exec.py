# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestRunHostScript(FrappeTestCase):
	def test_builds_ssh_command_with_cert_and_returns_stdout(self):
		from press.infra import host_exec

		host = frappe._dict(ssh_user="sanad", ssh_host="1.2.3.4", ssh_port=22,
			ssh_identity="/k/sanad-infra", ssh_cert="/k/sanad-infra-cert.pub")
		completed = MagicMock(stdout="DONE\n", stderr="", returncode=0)
		with patch("press.infra.host_exec.subprocess.run", return_value=completed) as run:
			out = host_exec.run_host_script(host, "echo DONE")

		self.assertEqual(out, "DONE\n")
		argv = run.call_args[0][0]
		self.assertIn("-i", argv)
		self.assertIn("/k/sanad-infra", argv)
		self.assertIn("CertificateFile=/k/sanad-infra-cert.pub", argv)
		self.assertEqual(argv[-1], "sanad@1.2.3.4")
		self.assertIn("bash -s", run.call_args[1]["input"] or argv[-2] or "")

	def test_pushes_files_as_base64_heredoc_before_script(self):
		from press.infra import host_exec

		host = frappe._dict(ssh_user="sanad", ssh_host="h", ssh_port=22)
		completed = MagicMock(stdout="", stderr="", returncode=0)
		with patch("press.infra.host_exec.subprocess.run", return_value=completed) as run:
			host_exec.run_host_script(host, "true", files={"/srv/pbx/.env": "A=1\n"})

		script = run.call_args[1]["input"]
		self.assertIn("base64 -d", script)
		self.assertIn("/srv/pbx/.env", script)
		# the literal secret value is NOT in the script - only its base64 form
		self.assertNotIn("A=1", script)

	def test_nonzero_exit_raises_with_stderr(self):
		from press.infra import host_exec

		host = frappe._dict(ssh_user="sanad", ssh_host="h", ssh_port=22)
		completed = MagicMock(stdout="", stderr="ufw: command not found", returncode=127)
		with patch("press.infra.host_exec.subprocess.run", return_value=completed):
			with self.assertRaises(RuntimeError) as cm:
				host_exec.run_host_script(host, "ufw status")
		self.assertIn("ufw: command not found", str(cm.exception))

	def test_rejects_absolute_traversal_target_paths(self):
		from press.infra import host_exec

		host = frappe._dict(ssh_user="sanad", ssh_host="h", ssh_port=22)
		with self.assertRaises(frappe.ValidationError):
			host_exec.run_host_script(host, "true", files={"../etc/passwd": "x"})
