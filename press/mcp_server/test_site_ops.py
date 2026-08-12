# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Tests for the site provisioning wrappers (site_create / site_restore).

The wrappers exist to stop bad input reaching press.api.site, where a typo lands on
the Site document and only fails later inside an agent job. These tests pin the
guards, not the underlying Press flow.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from press.mcp_server import site_ops


class TestSiteOpsValidation(unittest.TestCase):
	def test_create_rejects_unknown_release_group(self):
		with patch.object(frappe.db, "exists", return_value=False):
			with self.assertRaises(frappe.DoesNotExistError):
				site_ops.site_create(new_subdomain="probe", release_group="bench-does-not-exist")

	def test_create_rejects_fqdn_as_subdomain(self):
		"""An FQDN would be joined with the root domain again : site.example.com.example.com."""
		with patch.object(frappe.db, "exists", return_value=True):
			with self.assertRaises(frappe.ValidationError) as ctx:
				site_ops.site_create(
					new_subdomain="probe.sandbox.mvpstorm.com", release_group="bench-0020"
				)
		self.assertIn("subdomain", str(ctx.exception).lower())

	def test_create_rejects_empty_subdomain(self):
		with patch.object(frappe.db, "exists", return_value=True):
			with self.assertRaises(frappe.ValidationError):
				site_ops.site_create(new_subdomain="   ", release_group="bench-0020")

	def test_create_rejects_missing_remote_file(self):
		"""A database docname that does not exist must fail before api.site.new."""

		def exists(doctype, name=None, *args, **kwargs):
			return doctype != "Remote File"

		with patch.object(frappe.db, "exists", side_effect=exists), patch.object(
			frappe.db, "get_single_value", return_value="sandbox.mvpstorm.com"
		):
			with self.assertRaises(frappe.DoesNotExistError) as ctx:
				site_ops.site_create(
					new_subdomain="probe",
					release_group="bench-0020",
					database="no-such-remote-file",
				)
		self.assertIn("upload_backup_file", str(ctx.exception))

	def test_restore_requires_at_least_one_file(self):
		with patch.object(frappe.db, "exists", return_value=True):
			with self.assertRaises(frappe.ValidationError) as ctx:
				site_ops.site_restore(site="probe.sandbox.mvpstorm.com")
		self.assertIn("required", str(ctx.exception).lower())

	def test_restore_rejects_unknown_site(self):
		with patch.object(frappe.db, "exists", return_value=False):
			with self.assertRaises(frappe.DoesNotExistError):
				site_ops.site_restore(site="ghost.sandbox.mvpstorm.com", database="rf-1")

	def test_restore_passes_only_supplied_files(self):
		"""Empty keys must be dropped, not forwarded as '' : a blank remote_public_file
		would otherwise overwrite whatever the site already had."""
		captured = {}

		def fake_restore(name, files, skip_failing_patches=False, skip_tables=None):
			captured["name"] = name
			captured["files"] = files
			captured["skip_tables"] = skip_tables

		with patch.object(frappe.db, "exists", return_value=True), patch.object(
			frappe.db, "commit"
		), patch.object(frappe.db, "get_value", return_value="Active"), patch.object(
			frappe, "get_all", return_value=[]
		), patch.object(site_ops.site_api, "restore", side_effect=fake_restore):
			out = site_ops.site_restore(site="probe.sandbox.mvpstorm.com", database="rf-db")

		self.assertEqual(captured["files"], {"database": "rf-db"})
		self.assertNotIn("public", captured["files"])
		self.assertEqual(out["site_status"], "Active")

	def test_restore_reports_null_job_when_nothing_was_queued(self):
		"""The false-success guard: no Agent Job means agent_job is null, not 'queued'.

		A hardcoded status is how site_config_set came to answer 'set' for a call that
		had raised. The caller must be able to tell the difference.
		"""
		with patch.object(frappe.db, "exists", return_value=True), patch.object(
			frappe.db, "commit"
		), patch.object(frappe.db, "get_value", return_value="Broken"), patch.object(
			frappe, "get_all", return_value=[]
		), patch.object(site_ops.site_api, "restore", return_value=None):
			out = site_ops.site_restore(site="probe.sandbox.mvpstorm.com", database="rf-db")

		self.assertIsNone(out["agent_job"])
		self.assertIsNone(out["agent_job_status"])
		self.assertEqual(out["site_status"], "Broken")
		self.assertNotIn("status", out)  # no hardcoded optimistic field

	def test_restore_reports_the_job_press_created(self):
		job = frappe._dict({"name": "job-123", "status": "Pending", "creation": "2026-08-12"})
		with patch.object(frappe.db, "exists", return_value=True), patch.object(
			frappe.db, "commit"
		), patch.object(frappe.db, "get_value", return_value="Pending"), patch.object(
			frappe, "get_all", return_value=[job]
		), patch.object(site_ops.site_api, "restore", return_value=None):
			out = site_ops.site_restore(site="probe.sandbox.mvpstorm.com", database="rf-db")

		self.assertEqual(out["agent_job"], "job-123")
		self.assertEqual(out["agent_job_status"], "Pending")

	def test_create_forwards_subdomain_and_group(self):
		captured = {}

		def fake_new(payload):
			captured.update(payload)
			return {"site": "probe.sandbox.mvpstorm.com"}

		def exists(doctype, name=None, *args, **kwargs):
			# Release Group and Remote File exist; the target Site does not yet.
			return doctype != "Site"

		with patch.object(frappe.db, "exists", side_effect=exists), patch.object(
			frappe.db, "get_single_value", return_value="sandbox.mvpstorm.com"
		), patch.object(frappe.db, "commit"), patch.object(
			site_ops.site_api, "new", side_effect=fake_new
		):
			out = site_ops.site_create(
				new_subdomain="PROBE",
				release_group="bench-0020",
				apps=["frappe", "erpnext"],
				database="rf-db",
			)

		self.assertEqual(captured["name"], "probe")  # lowercased
		self.assertEqual(captured["group"], "bench-0020")
		self.assertEqual(captured["apps"], ["frappe", "erpnext"])
		self.assertEqual(captured["files"], {"database": "rf-db"})
		self.assertEqual(out["site"], "probe.sandbox.mvpstorm.com")
		self.assertTrue(out["created"])


class TestResourceScopingRegistry(unittest.TestCase):
	"""The guard that makes this bug class non-recurring.

	Commit 252991d2a was titled "register six tools missing from _extract_target".
	It fixed six and missed two (app_git_status, bench_provision_progress), which
	stayed in the catalog and refused every call until 2026-08-12. Fixing the third
	and fourth by hand invites a fifth, so instead: walk the registry and fail if
	any tool declaring a resource argument is neither mapped in _extract_target nor
	explicitly allowlisted as resourceless.
	"""

	RESOURCE_ARGS = ("site", "site_name", "release_group", "bench_name", "name")

	def test_every_resource_tool_is_scoped(self):
		"""Resolution needs the DB lookups stubbed, or the probe fails for the wrong reason.

		_extract_target resolves several tool families through the database : bench_name to
		its parent Release Group, a Deploy Candidate to its group. A probe name that does not
		exist resolves to None and would be reported as "unmapped" when the mapping is
		actually fine. So stub the lookups the way test_server.py's _bench_group_get_value
		helper already does for the ssh-cert tests, and let this test assert only what it is
		about: whether the tool is wired into the function at all.
		"""
		from press.mcp_server.server import RESOURCELESS_TOOLS, _extract_target
		from press.mcp_server.tools import TOOLS

		probe = {
			"site": "probe.example.com",
			"site_name": "probe.example.com",
			"release_group": "bench-probe",
			"bench_name": "bench-probe-000001-server",
			"name": "probe-name",
			"target_doctype": "Site",
			"target_name": "probe.example.com",
		}

		def stub_get_value(*args, **kwargs):
			# as_dict callers (the Deploy Candidate branch) need attribute access.
			if kwargs.get("as_dict"):
				return frappe._dict(group="fake-rg", deploy_candidate="dc-probe", site="probe.example.com")
			return "fake-rg"

		unscoped = []
		with patch.object(frappe.db, "get_value", side_effect=stub_get_value), patch.object(
			frappe.db, "exists", return_value=True
		), patch.object(frappe, "get_value", side_effect=stub_get_value, create=True):
			unscoped = self._collect_unscoped(TOOLS, RESOURCELESS_TOOLS, _extract_target, probe)

		self.assertEqual(
			unscoped,
			[],
			"These tools carry a resource argument but _extract_target does not map them, "
			"so the fail-closed guard refuses every call. Add them to the matching set in "
			"_extract_target, or to RESOURCELESS_TOOLS if they genuinely own no resource:\n  "
			+ "\n  ".join(unscoped),
		)

	def _collect_unscoped(self, TOOLS, RESOURCELESS_TOOLS, _extract_target, probe):
		unscoped = []
		for tool_name, spec in TOOLS.items():
			if tool_name in RESOURCELESS_TOOLS:
				continue
			props = spec.get("args_schema", {}).get("properties", {})
			carried = [a for a in self.RESOURCE_ARGS if a in props]
			if not carried:
				continue
			args = {a: probe[a] for a in carried}
			# target_doctype/target_name pair is how the lock tools declare theirs.
			if "target_doctype" in props:
				args.update(target_doctype=probe["target_doctype"], target_name=probe["target_name"])
			try:
				doctype, name = _extract_target(tool_name, args)
			except Exception as exc:  # a raising mapper is also a failure to scope
				unscoped.append(f"{tool_name} (raised {type(exc).__name__})")
				continue
			if not doctype or not name:
				unscoped.append(f"{tool_name} (carries {carried}, resolved to {doctype!r})")

		return unscoped

	def test_new_site_tools_resolve_to_the_right_resource(self):
		from press.mcp_server.server import _extract_target

		self.assertEqual(
			_extract_target("site_restore", {"site": "probe.example.com"}),
			("Site", "probe.example.com"),
		)
		self.assertEqual(
			_extract_target("site_create", {"release_group": "bench-0020"}),
			("Release Group", "bench-0020"),
		)

	def test_previously_broken_tools_now_resolve(self):
		"""app_git_status and bench_provision_progress were catalogued but unmapped."""
		from press.mcp_server.server import _extract_target

		for tool in ("app_git_status", "bench_provision_progress"):
			self.assertEqual(
				_extract_target(tool, {"release_group": "bench-0020"}),
				("Release Group", "bench-0020"),
				f"{tool} must resolve to its Release Group",
			)
