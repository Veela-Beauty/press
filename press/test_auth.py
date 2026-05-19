# Copyright (c) 2026, Frappe and contributors
# See license.txt
"""Tests for press/auth.py — specifically the ALLOWED_WILDCARD_PATHS coverage.

The recurring bug: dev adds a new whitelisted method in
press.press.doctype.<x>.<y>.<method>, wires the Vue dashboard to call it,
forgets to add the auth.py allowlist entry. Non-System team users get a 401
on first call; Vue interprets it as session-expired and force-logs-out.

Three documented incidents in two weeks (deploy_candidate_build,
bench_dev_watch + bench_code_health, release_group_clone + bench_vscode +
press.ai.api). This test runs scripts/audit_dashboard_allowlist.py and fails
CI if it returns anything other than "OK — every dashboard dotted-path
caller is covered."
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from frappe.tests.utils import FrappeTestCase


class TestAuthAllowlistCoverage(FrappeTestCase):
	def test_every_dashboard_caller_is_in_allowlist(self):
		repo_root = Path(__file__).resolve().parent.parent
		script = repo_root / "scripts" / "audit_dashboard_allowlist.py"
		self.assertTrue(script.exists(), f"audit script missing at {script}")

		result = subprocess.run(
			["python3", str(script)],
			cwd=str(repo_root),
			capture_output=True,
			text=True,
			timeout=30,
		)
		# Show the output so a CI failure is self-explaining
		self.assertEqual(
			result.returncode,
			0,
			f"audit_dashboard_allowlist.py reported missing allowlist entries:\n"
			f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}",
		)
