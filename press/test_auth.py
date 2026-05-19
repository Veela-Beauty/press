# Copyright (c) 2026, Frappe and contributors
# See license.txt
"""Tests for press/auth.py + the contract-audit script suite under scripts/.

Each audit catches a specific recurring class of bug we've hit multiple times
since 2026-05-10. The tests run the scripts in subprocesses and assert exit 0.
A failure here means a PR is about to ship a known regression — fix the
underlying issue, don't paper over by editing the script's exclusion list
(except where the script's docstring explicitly authorises a static skip).

Audit catalogue:
    1. allowlist coverage      — every dashboard caller is in ALLOWED_WILDCARD_PATHS
    2. method exists           — every dashboard caller resolves to a real symbol
    3. whitelist decorator     — every caller's target has @frappe.whitelist
    4. audit-log perm bypass   — Bench Shell Log insert uses ignore_permissions=True
    5. MCP catalog parity      — tools.py keys == _tool_catalog.js keys
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from frappe.tests.utils import FrappeTestCase


REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_audit(script_name: str) -> subprocess.CompletedProcess:
	script = REPO_ROOT / "scripts" / script_name
	assert script.exists(), f"audit script missing at {script}"
	return subprocess.run(
		["python3", str(script)],
		cwd=str(REPO_ROOT),
		capture_output=True,
		text=True,
		timeout=60,
	)


class TestDashboardContracts(FrappeTestCase):
	def _assert_audit_passes(self, script_name: str) -> None:
		result = _run_audit(script_name)
		self.assertEqual(
			result.returncode,
			0,
			f"{script_name} reported failures:\n"
			f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}",
		)

	def test_audit_allowlist_coverage(self):
		"""Every dotted-path caller in dashboard/src is in ALLOWED_WILDCARD_PATHS."""
		self._assert_audit_passes("audit_dashboard_allowlist.py")

	def test_audit_method_exists(self):
		"""Every dotted-path caller resolves to a real Python symbol."""
		self._assert_audit_passes("audit_dashboard_method_exists.py")

	def test_audit_whitelisted_decorator(self):
		"""Every dotted-path target carries @frappe.whitelist."""
		self._assert_audit_passes("audit_dashboard_whitelisted.py")

	def test_audit_audit_log_inserts(self):
		"""Bench Shell Log insert keeps ignore_permissions=True (locks in the 2026-05-19 fix)."""
		self._assert_audit_passes("audit_audit_log_inserts.py")

	def test_audit_mcp_catalog_parity(self):
		"""tools.py and _tool_catalog.js list exactly the same MCP tools."""
		self._assert_audit_passes("audit_mcp_catalog_parity.py")

	def test_audit_mcp_schema_vs_signature(self):
		"""Every MCP tool's args_schema matches the underlying Python signature.

		Catches: schema documents an arg the method doesn't accept (bench_deploy
		2026-05-19 — `apps` was list[str] in schema but list[dict] in the method).
		Runs in-process because the audit needs to import Press modules, which
		need a live Frappe context — can't run via subprocess like the others.
		"""
		import sys

		audit_script = REPO_ROOT / "scripts" / "audit_mcp_schema_vs_signature.py"
		self.assertTrue(audit_script.exists(), f"audit script missing: {audit_script}")
		# Run the audit's collect_drift() in-process so frappe imports work
		sys.path.insert(0, str(REPO_ROOT / "scripts"))
		try:
			from audit_mcp_schema_vs_signature import collect_drift
		finally:
			pass
		drift = collect_drift()
		if drift:
			msg = "\n".join(f"  -- {tool}: {reason}" for tool, reason in sorted(drift))
			self.fail(
				f"{len(drift)} MCP tools have schema/signature drift:\n{msg}\n"
				f"Fix: edit press/mcp_server/tools.py — update args_schema to "
				f"match the actual Python method's signature.",
			)
