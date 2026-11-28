# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Tests for the site provisioning wrappers (site_create / site_restore).

The wrappers exist to stop bad input reaching press.api.site, where a typo lands on
the Site document and only fails later inside an agent job. These tests pin the
guards, not the underlying Press flow.
"""

from __future__ import annotations

import unittest
from contextlib import ExitStack
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
		"""A database docname that does not exist must fail before api.site.new.

		The stub has to say the target Site does NOT exist : a blanket "everything exists"
		makes site_create throw "Site already exists" first and the assertion passes for
		the wrong reason.
		"""

		def exists(doctype, name=None, *args, **kwargs):
			return doctype in ("Release Group", "Site Plan")

		with patch.object(frappe.db, "exists", side_effect=exists), patch.object(
			frappe.db, "get_single_value", return_value="sandbox.mvpstorm.com"
		):
			with self.assertRaises(frappe.DoesNotExistError) as ctx:
				site_ops.site_create(
					new_subdomain="probe",
					release_group="bench-0020",
					plan="USD 25",
					database="no-such-remote-file",
				)
		self.assertIn("upload_backup_file", str(ctx.exception))

	def test_create_refuses_an_empty_plan(self):
		"""An empty plan used to reach Press, and the site then showed No plan set (27 Nov 2026)."""
		with patch.object(frappe.db, "exists", return_value=True), patch.object(
			frappe, "get_all", return_value=["USD 10", "USD 25"]
		), patch.object(site_ops.site_api, "new") as new:
			with self.assertRaises(frappe.ValidationError) as ctx:
				site_ops.site_create(new_subdomain="probe", release_group="bench-0020")
		self.assertIn("plan is required", str(ctx.exception))
		self.assertIn("USD 25", str(ctx.exception))
		new.assert_not_called()

	def test_create_refuses_an_unknown_plan(self):
		def exists(doctype, name=None, *args, **kwargs):
			return doctype != "Site Plan"

		with patch.object(frappe.db, "exists", side_effect=exists), patch.object(
			frappe, "get_all", return_value=["USD 10", "USD 25"]
		) as get_all, patch.object(site_ops.site_api, "new") as new:
			with self.assertRaises(frappe.ValidationError) as ctx:
				site_ops.site_create(new_subdomain="probe", release_group="bench-0020", plan="USD25")
		self.assertIn("'USD25' is not a Site Plan", str(ctx.exception))
		get_all.assert_called_once_with(
			"Site Plan", filters={"enabled": 1, "document_type": "Site"}, pluck="name"
		)
		new.assert_not_called()

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
				plan="USD 25",
				database="rf-db",
			)

		self.assertEqual(captured["name"], "probe")  # lowercased
		self.assertEqual(captured["group"], "bench-0020")
		self.assertEqual(captured["apps"], ["frappe", "erpnext"])
		self.assertEqual(captured["files"], {"database": "rf-db"})
		self.assertEqual(captured["plan"], "USD 25")
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

	def test_guard_message_blames_the_caller_before_the_server(self):
		"""A wrong-argument call must not read as a server bug.

		app_git_status and bench_provision_progress declare ["bench_name"]. Called with
		release_group they are correctly refused, but the old message said "This is a
		server-side bug; please add <tool> to _extract_target" : so both were written off
		as broken tools for a week when the mapping had been right all along. The message
		now names the declared argument first.
		"""
		from press.mcp_server.server import _assert_target_extracted

		for tool in ("app_git_status", "bench_provision_progress"):
			with self.assertRaises(frappe.PermissionError) as ctx:
				_assert_target_extracted(tool, {"release_group": "bench-0020"}, None, None)
			msg = str(ctx.exception)
			self.assertIn("bench_name", msg, "must name the argument the tool actually declares")
			self.assertIn("release_group", msg, "must name what the caller wrongly passed")
			self.assertLess(
				msg.index("bench_name"),
				msg.index("_extract_target"),
				"the caller-side hint must come before the server-side one",
			)


class TestSiteArchive(unittest.TestCase):
	"""site_archive drops a site, so its guards are the point: only a deactivated site, and
	only once a healthy offsite backup taken after the switch-off exists."""

	SITE = "probe.sandbox.mvpstorm.com"

	def _flow(self, stack, status="Inactive", backup=None, problem=None):
		"""Patch the reads site_archive makes; return the mocks a test asserts on."""
		stack.enter_context(patch.object(frappe.db, "exists", return_value=True))
		stack.enter_context(patch.object(frappe.db, "get_value", side_effect=[status, "Pending"]))
		stack.enter_context(patch.object(site_ops, "_deactivated_at", return_value="2026-11-28 06:00:00"))
		stack.enter_context(patch.object(site_ops, "_backup_since", return_value=backup))
		stack.enter_context(patch.object(site_ops, "_backup_problem", return_value=problem))
		site_doc = frappe._dict(backup=lambda **kw: frappe._dict(name="backup-new", kwargs=kw))
		return {
			"get_doc": stack.enter_context(patch.object(frappe, "get_doc", return_value=site_doc)),
			"commit": stack.enter_context(patch.object(frappe.db, "commit")),
			"rollback": stack.enter_context(patch.object(frappe.db, "rollback")),
			"get_all": stack.enter_context(patch.object(frappe, "get_all", return_value=[])),
			"archive": stack.enter_context(patch.object(site_ops.site_api, "archive")),
		}

	def test_archive_rejects_unknown_site(self):
		with (
			patch.object(frappe.db, "exists", return_value=False),
			patch.object(site_ops.site_api, "archive") as archive,
			self.assertRaises(frappe.DoesNotExistError),
		):
			site_ops.site_archive(name="ghost.sandbox.mvpstorm.com")
		archive.assert_not_called()

	def test_archive_refuses_a_site_that_is_not_inactive(self):
		"""One wrong call must never drop a live site, nor touch one already archived."""
		for status in ("Active", "Broken", "Suspended", "Pending", "Archived", None):
			with ExitStack() as stack:
				mocks = self._flow(stack, status=status)
				with self.assertRaises(frappe.ValidationError) as ctx:
					site_ops.site_archive(name=self.SITE)
			mocks["archive"].assert_not_called()
			mocks["get_doc"].assert_not_called()
			self.assertIn("site_deactivate", str(ctx.exception), "must tell the caller the first step")

	def test_no_backup_since_switch_off_starts_an_offsite_backup_with_files(self):
		with ExitStack() as stack:
			mocks = self._flow(stack, backup=None)
			out = site_ops.site_archive(name=self.SITE)
		mocks["archive"].assert_not_called()
		self.assertEqual(out["stage"], "backup_started")
		self.assertEqual(out["backup"], "backup-new")
		mocks["commit"].assert_called_once()

	def test_backup_started_is_offsite_with_files(self):
		calls = {}

		def fake_backup(**kwargs):
			calls.update(kwargs)
			return frappe._dict(name="backup-new")

		with ExitStack() as stack:
			mocks = self._flow(stack, backup=None)
			mocks["get_doc"].return_value = frappe._dict(backup=fake_backup)
			site_ops.site_archive(name=self.SITE)
		self.assertEqual(calls, {"with_files": True, "offsite": True})

	def test_a_running_backup_is_waited_for_not_doubled(self):
		running = frappe._dict(name="backup-1", status="Running")
		with ExitStack() as stack:
			mocks = self._flow(stack, backup=running)
			out = site_ops.site_archive(name=self.SITE)
		self.assertEqual(out["stage"], "backup_running")
		mocks["get_doc"].assert_not_called()
		mocks["archive"].assert_not_called()

	def test_an_unhealthy_backup_starts_a_new_one_and_never_archives(self):
		failed = frappe._dict(name="backup-1", status="Failure")
		with ExitStack() as stack:
			mocks = self._flow(stack, backup=failed, problem="backup backup-1 is Failure")
			out = site_ops.site_archive(name=self.SITE)
		self.assertEqual(out["stage"], "backup_started")
		self.assertEqual(out["reason"], "backup backup-1 is Failure")
		mocks["archive"].assert_not_called()

	def test_a_healthy_backup_lets_the_archive_go_without_force(self):
		good = frappe._dict(name="backup-ok", status="Success")
		job = frappe._dict({"name": "job-9", "status": "Pending"})
		with ExitStack() as stack:
			mocks = self._flow(stack, backup=good, problem=None)
			mocks["get_all"].return_value = [job]
			out = site_ops.site_archive(name=self.SITE)
		mocks["archive"].assert_called_once_with(name=self.SITE, force=False)
		mocks["commit"].assert_called_once()
		filters = mocks["get_all"].call_args.kwargs["filters"]
		self.assertEqual((filters["site"], filters["job_type"]), (self.SITE, "Archive Site"))
		self.assertEqual(filters["creation"][0], ">=", "only a job this call created may be reported")
		self.assertEqual((out["stage"], out["backup"], out["agent_job"]), ("archive_queued", "backup-ok", "job-9"))

	def test_archive_rolls_back_when_press_fails_half_way(self):
		"""Site.archive saves Pending before its later steps : a failure must not be committed."""
		good = frappe._dict(name="backup-ok", status="Success")
		with ExitStack() as stack:
			mocks = self._flow(stack, backup=good, problem=None)
			mocks["archive"].side_effect = RuntimeError("agent down")
			with self.assertRaises(RuntimeError):
				site_ops.site_archive(name=self.SITE)
		mocks["rollback"].assert_called_once()
		mocks["commit"].assert_not_called()

	def test_archive_is_scoped_to_its_site_high_risk_and_listed(self):
		from press.mcp_server.help import TOOL_CATEGORY
		from press.mcp_server.server import _extract_target
		from press.mcp_server.tools import TOOLS

		self.assertEqual(_extract_target("site_archive", {"name": self.SITE}), ("Site", self.SITE))
		self.assertEqual(TOOLS["site_archive"]["risk"], "high")
		self.assertEqual(TOOL_CATEGORY["site_archive"], "dangerous")


class TestBackupHealth(unittest.TestCase):
	"""_backup_problem decides whether a backup can bring a dropped site back."""

	@staticmethod
	def _good():
		return {
			"name": "b1", "status": "Success", "offsite": 1, "with_files": 1, "files_availability": "Available",
			"remote_database_file": "rf-db", "remote_public_file": "rf-pub", "remote_private_file": "rf-priv",
		}

	def _problem(self, files=None, db_size="2048", **changes):
		files = files or {}
		backup = frappe._dict({**self._good(), **changes})

		def get_value(doctype, name, fields, *args, **kwargs):
			if isinstance(fields, list):
				return files.get(name, frappe._dict(status="Available", file_size="10"))
			return db_size

		with patch.object(frappe.db, "get_value", side_effect=get_value):
			return site_ops._backup_problem(backup)

	def test_a_complete_offsite_backup_is_healthy(self):
		self.assertIsNone(self._problem())

	def test_each_unhealthy_shape_is_named(self):
		cases = {
			"is Pending": {"status": "Pending"},
			"is Failure": {"status": "Failure"},
			"no offsite copy": {"offsite": 0},
			"no offsite copy ": {"files_availability": "Unavailable"},
			"no public and private files": {"with_files": 0},
			"no public and private files ": {"remote_private_file": None},
		}
		for expected, change in cases.items():
			with self.subTest(change=change):
				self.assertIn(expected.strip(), self._problem(**change))

	def test_a_file_missing_from_storage_is_unhealthy(self):
		self.assertIn("missing from storage", self._problem(files={"rf-pub": None}))
		gone = frappe._dict(status="Unavailable", file_size="10")
		self.assertIn("missing from storage", self._problem(files={"rf-db": gone}))

	def test_an_empty_database_file_is_unhealthy(self):
		self.assertIn("database file is empty", self._problem(db_size="0"))
		self.assertIn("database file is empty", self._problem(db_size=None))
