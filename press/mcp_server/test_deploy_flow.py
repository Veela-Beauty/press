# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from press.mcp_server.deploy_flow import (
	agent_job_list,
	register_existing_app,
	app_release_approve,
	bench_provision_progress,
	deploy_candidate_schedule_build,
	deploy_candidate_status,
	release_group_create_deploy_candidate,
	site_schedule_update,
	site_status,
	wait_for_bench_flip,
)


class TestDeployFlow(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_register_existing_app_populates_versions_from_branch(self):
		"""REGRESSION (2026-06-05): register_existing_app built the App Source
		doc WITHOUT the required `versions` child table, so .insert() failed
		with 'Data missing in table: Versions' and the tool could NEVER create
		a valid App Source (it looped, getting stuck on every retry). Verify the
		Frappe Version is now derived from a version-NN branch and passed into
		the doc.
		"""
		captured = {}

		def fake_get_doc(d):
			if isinstance(d, dict) and d.get("doctype") == "App Source":
				captured.update(d)
			m = MagicMock()
			m.name = "SRC-test-001"
			m.repository_url = d.get("repository_url") if isinstance(d, dict) else ""
			m.create_release.return_value = "rel-1"
			return m

		with patch("press.utils.get_current_team", return_value="Team-X"), patch(
			"press.mcp_server.deploy_flow.frappe.db.exists", return_value=True
		), patch(
			"press.mcp_server.deploy_flow.frappe.db.get_value", return_value=None
		), patch(
			"press.mcp_server.deploy_flow._installation_for_owner", return_value="4242"
		), patch(
			"press.mcp_server.deploy_flow._repo_is_public", return_value=False
		), patch(
			"press.mcp_server.deploy_flow.frappe.get_doc", side_effect=fake_get_doc
		):
			result = register_existing_app(
				repository_url="https://github.com/x/rentix",
				branch="version-15",
				app_name="rentix",
			)

		self.assertEqual(captured.get("versions"), [{"version": "Version 15"}])
		self.assertEqual(result["versions"], ["Version 15"])

	def test_register_existing_app_explicit_versions_arg_wins(self):
		"""An explicit versions arg is honoured (and validated) over branch derivation."""
		captured = {}

		def fake_get_doc(d):
			if isinstance(d, dict) and d.get("doctype") == "App Source":
				captured.update(d)
			m = MagicMock()
			m.name = "SRC-test-002"
			m.repository_url = ""
			m.create_release.return_value = None
			return m

		with patch("press.utils.get_current_team", return_value="Team-X"), patch(
			"press.mcp_server.deploy_flow.frappe.db.exists", return_value=True
		), patch(
			"press.mcp_server.deploy_flow.frappe.db.get_value", return_value=None
		), patch(
			"press.mcp_server.deploy_flow._installation_for_owner", return_value="4242"
		), patch(
			"press.mcp_server.deploy_flow._repo_is_public", return_value=False
		), patch(
			"press.mcp_server.deploy_flow.frappe.get_doc", side_effect=fake_get_doc
		):
			register_existing_app(
				repository_url="x/rentix",
				branch="main",
				app_name="rentix",
				versions=["Version 14"],
			)

		self.assertEqual(captured.get("versions"), [{"version": "Version 14"}])

	def test_register_existing_app_stores_the_github_installation_id(self):
		"""REGRESSION (2026-08-06): the App Source was created WITHOUT
		github_installation_id, so App Source.get_repo_url() returned a bare
		credential-less URL and every build of a PRIVATE repo died at
		`git clone` with an empty error and 0.0s duration. Registration itself
		still looked healthy, because create_release authenticates through the
		team token instead. Cost an evening on eta_bridge.
		"""
		captured = {}

		def fake_get_doc(d):
			if isinstance(d, dict) and d.get("doctype") == "App Source":
				captured.update(d)
			m = MagicMock()
			m.name = "SRC-test-003"
			m.repository_url = ""
			m.public = 0
			m.create_release.return_value = "rel-3"
			return m

		with patch("press.utils.get_current_team", return_value="Team-X"), patch(
			"press.mcp_server.deploy_flow.frappe.db.exists", return_value=True
		), patch(
			"press.mcp_server.deploy_flow.frappe.db.get_value", return_value=None
		), patch(
			"press.mcp_server.deploy_flow._repo_is_public", return_value=False
		), patch(
			"press.mcp_server.deploy_flow.frappe.get_all", return_value=["77777"]
		), patch(
			"press.mcp_server.deploy_flow.frappe.get_doc", side_effect=fake_get_doc
		):
			result = register_existing_app(
				repository_url="https://github.com/Acme/widget",
				branch="main",
				app_name="widget",
				versions=["Version 15"],
			)

		self.assertEqual(captured.get("github_installation_id"), "77777")
		self.assertEqual(result["github_installation_id"], "77777")

	def test_register_existing_app_refuses_a_private_repo_with_no_installation(self):
		"""Fail at registration, not minutes later inside a build."""
		with patch("press.utils.get_current_team", return_value="Team-X"), patch(
			"press.mcp_server.deploy_flow.frappe.db.exists", return_value=True
		), patch(
			"press.mcp_server.deploy_flow.frappe.db.get_value", return_value=None
		), patch(
			"press.mcp_server.deploy_flow._repo_is_public", return_value=False
		), patch(
			"press.mcp_server.deploy_flow.frappe.get_all", return_value=[]
		):
			with self.assertRaises(frappe.ValidationError):
				register_existing_app(
					repository_url="https://github.com/Acme/private-widget",
					branch="main",
					app_name="private_widget",
					versions=["Version 15"],
				)

	def test_register_existing_app_allows_a_public_repo_with_no_installation(self):
		"""A public repo clones with no credentials, so no installation is needed."""
		captured = {}

		def fake_get_doc(d):
			if isinstance(d, dict) and d.get("doctype") == "App Source":
				captured.update(d)
			m = MagicMock()
			m.name = "SRC-test-004"
			m.repository_url = ""
			m.public = 1
			m.create_release.return_value = "rel-4"
			return m

		with patch("press.utils.get_current_team", return_value="Team-X"), patch(
			"press.mcp_server.deploy_flow.frappe.db.exists", return_value=True
		), patch(
			"press.mcp_server.deploy_flow.frappe.db.get_value", return_value=None
		), patch(
			"press.mcp_server.deploy_flow._repo_is_public", return_value=True
		), patch(
			"press.mcp_server.deploy_flow.frappe.get_all", return_value=[]
		), patch(
			"press.mcp_server.deploy_flow.frappe.get_doc", side_effect=fake_get_doc
		):
			register_existing_app(
				repository_url="https://github.com/frappe/hrms",
				branch="version-15",
				app_name="hrms",
			)

		self.assertEqual(captured.get("public"), 1)

	def test_app_release_approve_flips_status(self):
		fake_doc = MagicMock(status="Draft")
		with patch("press.mcp_server.deploy_flow.frappe.get_doc", return_value=fake_doc):
			result = app_release_approve("rel-x")
		self.assertEqual(result["status"], "Approved")
		self.assertEqual(fake_doc.status, "Approved")
		fake_doc.save.assert_called_once_with(ignore_permissions=True)

	def test_app_release_approve_idempotent_when_already_approved(self):
		fake_doc = MagicMock(status="Approved")
		with patch("press.mcp_server.deploy_flow.frappe.get_doc", return_value=fake_doc):
			result = app_release_approve("rel-y")
		self.assertTrue(result.get("already_approved"))
		fake_doc.save.assert_not_called()

	def test_release_group_create_deploy_candidate_returns_candidate_name(self):
		fake_candidate = MagicMock(name="cand")
		fake_candidate.name = "deploy-0001-000001"
		fake_rg = MagicMock()
		fake_rg.create_deploy_candidate.return_value = fake_candidate
		with patch("press.mcp_server.deploy_flow.frappe.get_doc", return_value=fake_rg):
			result = release_group_create_deploy_candidate("bench-0001")
		self.assertEqual(result["candidate"], "deploy-0001-000001")
		self.assertEqual(result["release_group"], "bench-0001")

	def test_release_group_create_deploy_candidate_disabled_raises(self):
		fake_rg = MagicMock()
		fake_rg.create_deploy_candidate.return_value = None
		with patch("press.mcp_server.deploy_flow.frappe.get_doc", return_value=fake_rg):
			with self.assertRaises(frappe.ValidationError):
				release_group_create_deploy_candidate("bench-disabled")

	def test_deploy_candidate_schedule_build_returns_build_name(self):
		fake_dc = MagicMock()
		fake_dc.schedule_build_and_deploy.return_value = {"error": False, "name": "build-xyz"}
		with patch("press.mcp_server.deploy_flow.frappe.get_doc", return_value=fake_dc):
			result = deploy_candidate_schedule_build("deploy-0001-000001")
		self.assertEqual(result["build"], "build-xyz")
		self.assertEqual(result["candidate"], "deploy-0001-000001")
		fake_dc.schedule_build_and_deploy.assert_called_once_with(run_now=True)

	def test_deploy_candidate_status_resolves_build_first(self):
		# Build exists → return build shape
		def fake_exists(doctype, name):
			return doctype == "Deploy Candidate Build"

		def fake_get_value(doctype, name, fields, as_dict=False):
			if doctype == "Deploy Candidate Build":
				return frappe._dict({
					"name": "build-001",
					"status": "Running",
					"build_start": now_datetime(),
					"build_end": None,
					"deploy_candidate": "deploy-X",
				})
			return None

		with patch("press.mcp_server.deploy_flow.frappe.db.exists", side_effect=fake_exists), \
			patch("press.mcp_server.deploy_flow.frappe.db.get_value", side_effect=fake_get_value):
			result = deploy_candidate_status("build-001")
		self.assertEqual(result["kind"], "build")
		self.assertEqual(result["candidate"], "deploy-X")
		self.assertEqual(result["status"], "Running")
		self.assertIsNone(result["build_end"])

	def test_deploy_candidate_status_falls_back_to_candidate(self):
		def fake_exists(doctype, name):
			return doctype == "Deploy Candidate"

		def fake_get_value(doctype, name, fields, as_dict=False):
			if doctype == "Deploy Candidate":
				return frappe._dict({
					"name": "deploy-Y",
					"status": "Pending",
					"group": "bench-0002",
				})
			return None

		with patch("press.mcp_server.deploy_flow.frappe.db.exists", side_effect=fake_exists), \
			patch("press.mcp_server.deploy_flow.frappe.db.get_value", side_effect=fake_get_value):
			result = deploy_candidate_status("deploy-Y")
		self.assertEqual(result["kind"], "candidate")
		self.assertEqual(result["release_group"], "bench-0002")

	def test_deploy_candidate_status_unknown_raises(self):
		with patch("press.mcp_server.deploy_flow.frappe.db.exists", return_value=False):
			with self.assertRaises(frappe.DoesNotExistError):
				deploy_candidate_status("nonexistent-name")

	def test_site_schedule_update_calls_underlying_method(self):
		fake_site = MagicMock()
		fake_site.schedule_update.return_value = "site-update-001"
		with patch("press.mcp_server.deploy_flow.frappe.get_doc", return_value=fake_site):
			result = site_schedule_update("x.example.com")
		self.assertEqual(result["site"], "x.example.com")
		self.assertEqual(result["site_update"], "site-update-001")
		fake_site.schedule_update.assert_called_once_with(
			skip_failing_patches=False, skip_backups=False
		)

	def test_site_status_returns_bench_and_jobs(self):
		def fake_get_value(doctype, name, fields, as_dict=False):
			if doctype == "Site" and name == "x.example.com":
				return frappe._dict({
					"name": "x.example.com",
					"bench": "bench-X-press-f1",
					"status": "Active",
					"modified": now_datetime(),
				})

		fake_jobs = [
			{"name": "job-1", "job_type": "Update Site Migrate", "status": "Success",
			 "creation": now_datetime()},
		]
		with patch("press.mcp_server.deploy_flow.frappe.db.get_value", side_effect=fake_get_value), \
			patch("press.mcp_server.deploy_flow.frappe.get_all", return_value=fake_jobs):
			result = site_status("x.example.com")
		self.assertEqual(result["bench"], "bench-X-press-f1")
		self.assertEqual(result["status"], "Active")
		self.assertEqual(len(result["recent_agent_jobs"]), 1)
		self.assertEqual(result["recent_agent_jobs"][0]["status"], "Success")

	def test_site_status_unknown_site_raises(self):
		with patch("press.mcp_server.deploy_flow.frappe.db.get_value", return_value=None):
			with self.assertRaises(frappe.DoesNotExistError):
				site_status("does-not-exist.example.com")

	def test_agent_job_list_filters_correctly(self):
		fake_jobs = [
			{"name": "j1", "site": "a.com", "job_type": "Migrate", "status": "Success",
			 "creation": now_datetime(), "bench": "b1"},
		]
		with patch(
			"press.mcp_server.deploy_flow.frappe.get_all",
			return_value=fake_jobs,
		) as m:
			result = agent_job_list(site="a.com", status="Success", since_minutes=60)
		self.assertEqual(len(result), 1)
		# Verify the filters dict passed to get_all
		_, kwargs = m.call_args
		filters = kwargs.get("filters") or m.call_args[1].get("filters")
		self.assertEqual(filters.get("site"), "a.com")
		self.assertEqual(filters.get("status"), "Success")

	def test_agent_job_list_clamps_since_minutes(self):
		"""since_minutes is clamped to 1..1440 — test boundary."""
		with patch("press.mcp_server.deploy_flow.frappe.get_all", return_value=[]):
			# Negative or zero should not raise
			agent_job_list(since_minutes=0)
			agent_job_list(since_minutes=99999)

	def test_wait_for_bench_flip_returns_pending_when_mismatch(self):
		def fake_get_value(doctype, name, fieldname=None, *a, **kw):
			if doctype == "Site":
				return "bench-OLD-press-f1"
			if doctype == "Bench":
				return "deploy-OLD"
			# Build row lookup for Gate C — returns a non-Success build so
			# Gate C doesn't fire and we get the normal 'pending' path.
			if doctype == "Deploy Candidate Build":
				return MagicMock(name="build-x", status="Building")
			return None

		with patch("press.mcp_server.deploy_flow.frappe.db.get_value", side_effect=fake_get_value), \
				patch("press.mcp_server.deploy_flow.frappe.db.exists", return_value=True), \
				patch("press.mcp_server.deploy_flow.frappe.db.count", return_value=0), \
				patch("press.mcp_server.deploy_flow.frappe.get_all", return_value=[]):
			result = wait_for_bench_flip(
				site_name="x.example.com",
				target_candidate="deploy-NEW",
			)
		# Build is 'Building' (not Success) so Gates C/E don't fire; falls
		# through to normal 'pending'.
		self.assertEqual(result["status"], "pending")
		self.assertEqual(result["current_candidate"], "deploy-OLD")
		self.assertEqual(result["target_candidate"], "deploy-NEW")

	# ---- Safety gate tests (Gates B / C / D added 2026-05-20) ----

	def test_gate_b_no_build_for_target_candidate(self):
		"""Gate B: target_candidate has no Deploy Candidate Build → return
		early with status='no_build' + a hint. Prevents the 'agent polls
		forever on a phantom build' pattern from 2026-05-20 dmg-erp."""
		def fake_get_value(doctype, name, fieldname=None, *a, **kw):
			if doctype == "Site":
				return "bench-OLD-press-f1"
			if doctype == "Bench":
				return "deploy-OLD"
			return None

		def fake_exists(doctype, filters):
			# Build does not exist; candidate does exist
			if doctype == "Deploy Candidate Build":
				return False
			if doctype == "Deploy Candidate":
				return True
			return False

		with patch("press.mcp_server.deploy_flow.frappe.db.get_value", side_effect=fake_get_value), \
				patch("press.mcp_server.deploy_flow.frappe.db.exists", side_effect=fake_exists):
			result = wait_for_bench_flip(
				site_name="x.example.com",
				target_candidate="deploy-NEW",
			)
		self.assertEqual(result["status"], "no_build")
		self.assertIn("deploy_candidate_schedule_build", result["hint"])

	def test_gate_b_no_candidate_at_all(self):
		"""Gate B: neither candidate NOR build exists — hint says the
		candidate name itself is wrong."""
		def fake_get_value(doctype, name, fieldname=None, *a, **kw):
			if doctype == "Site":
				return "bench-OLD-press-f1"
			if doctype == "Bench":
				return "deploy-OLD"
			return None

		with patch("press.mcp_server.deploy_flow.frappe.db.get_value", side_effect=fake_get_value), \
				patch("press.mcp_server.deploy_flow.frappe.db.exists", return_value=False):
			result = wait_for_bench_flip(
				site_name="x.example.com",
				target_candidate="deploy-GHOST",
			)
		self.assertEqual(result["status"], "no_build")
		self.assertIn("does not exist", result["hint"])

	def test_gate_c_flip_not_triggered_when_build_success_but_no_migrate(self):
		"""Gate C: Build is Success but no Update Site Migrate job in 30min
		→ status='flip_not_triggered'. Stops today's exact pattern where the
		agent polls forever expecting an auto-flip that standalone Press
		never performs."""
		def fake_get_value(doctype, name, fieldname=None, *a, **kw):
			if doctype == "Site":
				return "bench-OLD-press-f1"
			if doctype == "Bench":
				return "deploy-OLD"
			if doctype == "Deploy Candidate Build":
				return MagicMock(name="build-success", status="Success")
			return None

		# count=0 for stale-Undelivered (Gate D); get_all=[] for migrate (Gate C)
		with patch("press.mcp_server.deploy_flow.frappe.db.get_value", side_effect=fake_get_value), \
				patch("press.mcp_server.deploy_flow.frappe.db.exists", return_value=True), \
				patch("press.mcp_server.deploy_flow.frappe.db.count", return_value=0), \
				patch("press.mcp_server.deploy_flow.frappe.get_all", return_value=[]):
			result = wait_for_bench_flip(
				site_name="x.example.com",
				target_candidate="deploy-NEW",
			)
		self.assertEqual(result["status"], "flip_not_triggered")
		self.assertEqual(result["build_status"], "Success")
		self.assertIn("site_update_and_wait", result["hint"])

	def test_gate_e_flip_failed_with_recover(self):
		"""Gate E: Update Site Migrate FAILED and Recover Failed Site Migrate
		ran after it → status='flip_failed'. This catches dmg-erp's exact
		2026-05-20 state: agent was polling forever but the migrate already
		failed at 06:55 and was rolled back at 07:06."""
		from frappe.utils import now_datetime, add_to_date as _add
		def fake_get_value(doctype, name, fieldname=None, *a, **kw):
			if doctype == "Site":
				return "bench-OLD-press-f1"
			if doctype == "Bench":
				return "deploy-OLD"
			if doctype == "Deploy Candidate Build":
				return MagicMock(name="build-success", status="Success")
			return None

		now = now_datetime()
		fake_jobs = [
			MagicMock(
				name="recover-1", job_type="Recover Failed Site Migrate",
				status="Success", creation=now,
			),
			MagicMock(
				name="migrate-1", job_type="Update Site Migrate",
				status="Failure", creation=_add(now, minutes=-11),
			),
		]
		# Override the .name attr because MagicMock(name=...) sets the mock's name, not its .name attr
		fake_jobs[0].name = "recover-1"
		fake_jobs[1].name = "migrate-1"

		with patch("press.mcp_server.deploy_flow.frappe.db.get_value", side_effect=fake_get_value), \
				patch("press.mcp_server.deploy_flow.frappe.db.exists", return_value=True), \
				patch("press.mcp_server.deploy_flow.frappe.db.count", return_value=0), \
				patch("press.mcp_server.deploy_flow.frappe.get_all", return_value=fake_jobs):
			result = wait_for_bench_flip(
				site_name="x.example.com",
				target_candidate="deploy-NEW",
			)
		self.assertEqual(result["status"], "flip_failed")
		self.assertEqual(result["failed_migrate_job"], "migrate-1")
		self.assertEqual(result["recover_job"], "recover-1")
		self.assertIn("agent_job_traceback", result["hint"])

	def test_gate_d_kicks_poll_pending_jobs_when_stale_undelivered(self):
		"""Gate D: stale Undelivered jobs >2min old trigger ONE
		poll_pending_jobs call before returning. Idempotent — Press's own
		scheduler does this every 60s. Recovers from scheduler hiccups
		(the 2026-05-20 selfstorage-stg incident) automatically."""
		call_log = {"poll_called": False}

		def fake_get_value(doctype, name, fieldname=None, *a, **kw):
			if doctype == "Site":
				return "bench-OLD-press-f1"
			if doctype == "Bench":
				return "deploy-OLD"
			if doctype == "Deploy Candidate Build":
				return MagicMock(name="build-x", status="Building")
			return None

		# count > 0 ONLY for the stale-Undelivered query (Gate D); 0 for migrate
		def fake_count(doctype, filters):
			if filters.get("status") == "Undelivered":
				return 3
			return 0

		def fake_poll():
			call_log["poll_called"] = True

		with patch("press.mcp_server.deploy_flow.frappe.db.get_value", side_effect=fake_get_value), \
				patch("press.mcp_server.deploy_flow.frappe.db.exists", return_value=True), \
				patch("press.mcp_server.deploy_flow.frappe.db.count", side_effect=fake_count), \
				patch("press.mcp_server.deploy_flow.frappe.get_all", return_value=[]), \
				patch("press.press.doctype.agent_job.agent_job.poll_pending_jobs", side_effect=fake_poll), \
				patch("press.mcp_server.deploy_flow.frappe.db.commit"):
			result = wait_for_bench_flip(
				site_name="x.example.com",
				target_candidate="deploy-NEW",
			)
		self.assertTrue(call_log["poll_called"], "Gate D should have kicked poll_pending_jobs")
		# Bench didn't actually flip in this test (mocks return old bench
		# even after re-read), so we expect 'pending' not 'flipped'.
		self.assertEqual(result["status"], "pending")

	def test_wait_for_bench_flip_returns_flipped_when_match(self):
		# 'flipped' short-circuits BEFORE the gate checks (no exists/count
		# mocks needed). This test verifies the early-return path.
		def fake_get_value(doctype, name, fieldname=None, *a, **kw):
			if doctype == "Site":
				return "bench-NEW-press-f1"
			if doctype == "Bench":
				return "deploy-NEW"
			return None

		with patch("press.mcp_server.deploy_flow.frappe.db.get_value", side_effect=fake_get_value):
			result = wait_for_bench_flip(
				site_name="x.example.com",
				target_candidate="deploy-NEW",
			)
		self.assertEqual(result["status"], "flipped")

	def test_wait_for_bench_flip_unknown_site_raises(self):
		with patch("press.mcp_server.deploy_flow.frappe.db.get_value", return_value=None):
			with self.assertRaises(frappe.DoesNotExistError):
				wait_for_bench_flip(site_name="ghost.example.com", target_candidate="deploy-X")

	def test_candidate_to_release_group_orphan_build_raises(self):
		"""A Deploy Candidate Build whose deploy_candidate is NULL must NOT
		silently fall through; it must raise so scope-check isn't bypassed."""
		from press.mcp_server.server import _candidate_to_release_group

		def fake_get_value(doctype, name, fields=None, as_dict=False, **kw):
			# Build exists but its deploy_candidate is null
			if doctype == "Deploy Candidate Build":
				return frappe._dict({"name": name, "deploy_candidate": None})
			return None

		with patch(
			"press.mcp_server.server.frappe.db.get_value",
			side_effect=fake_get_value,
		):
			with self.assertRaises(frappe.ValidationError):
				_candidate_to_release_group("orphan-build")


class TestBenchProvisionProgress(FrappeTestCase):
	"""Stage rollup for bench provision chain. Patch DB calls so tests don't
	depend on a real bench existing."""

	def setUp(self):
		frappe.set_user("Administrator")

	def _patch_db(self, bench_doc, agent_jobs=None, builds=None, site_updates=None):
		"""Helper: set up the patches needed for one bench scenario."""
		agent_jobs = agent_jobs or []
		builds = builds or []
		site_updates = site_updates or []

		def fake_get_value(doctype, name=None, *args, **kwargs):
			if doctype == "Bench" and isinstance(name, str):
				return bench_doc
			return None

		def fake_exists(doctype, name=None, *args, **kwargs):
			return doctype == "Bench" and name == bench_doc["name"]

		def fake_sql(query, *args, **kwargs):
			q = query.strip().lower()
			if "deploy candidate build" in q:
				return builds
			if "agent job" in q:
				return agent_jobs
			if "site update" in q:
				return site_updates
			return []

		return patch.multiple(
			"press.mcp_server.deploy_flow.frappe.db",
			get_value=MagicMock(side_effect=fake_get_value),
			exists=MagicMock(side_effect=fake_exists),
			sql=MagicMock(side_effect=fake_sql),
		)

	def test_unknown_bench_raises(self):
		with patch(
			"press.mcp_server.deploy_flow.frappe.db.exists", return_value=False
		):
			with self.assertRaises(frappe.DoesNotExistError):
				bench_provision_progress("no-such-bench")

	def test_active_bench_with_no_jobs_returns_ready(self):
		bench_doc = frappe._dict({
			"name": "bench-X",
			"status": "Active",
			"candidate": None,
			"group": "rg-X",
			"creation": now_datetime(),
			"server": "press-f1.sandbox.mvpstorm.com",
		})
		with self._patch_db(bench_doc):
			result = bench_provision_progress("bench-X")
		self.assertEqual(result["stage"], "ready")
		self.assertEqual(result["bench_status"], "Active")

	def test_pending_bench_with_running_setup_bench_returns_setup_bench(self):
		bench_doc = frappe._dict({
			"name": "bench-Y",
			"status": "Pending",
			"candidate": "deploy-Y",
			"group": "rg-Y",
			"creation": now_datetime(),
			"server": "press-f1.sandbox.mvpstorm.com",
		})
		agent_jobs = [
			frappe._dict({
				"name": "job-new",
				"job_type": "New Bench",
				"status": "Success",
				"creation": now_datetime(),
				"start": now_datetime(),
				"end": now_datetime(),
			}),
			frappe._dict({
				"name": "job-setup",
				"job_type": "Setup Bench",
				"status": "Running",
				"creation": now_datetime(),
				"start": now_datetime(),
				"end": None,
			}),
		]
		with self._patch_db(bench_doc, agent_jobs=agent_jobs):
			result = bench_provision_progress("bench-Y")
		self.assertEqual(result["stage"], "setup_bench")
		self.assertIn("Cloning apps", result["stage_label"])

	def test_failed_new_bench_returns_failed(self):
		bench_doc = frappe._dict({
			"name": "bench-Z",
			"status": "Pending",
			"candidate": "deploy-Z",
			"group": "rg-Z",
			"creation": now_datetime(),
			"server": "press-f1.sandbox.mvpstorm.com",
		})
		agent_jobs = [
			frappe._dict({
				"name": "job-fail",
				"job_type": "New Bench",
				"status": "Failure",
				"creation": now_datetime(),
				"start": now_datetime(),
				"end": now_datetime(),
			}),
		]
		with self._patch_db(bench_doc, agent_jobs=agent_jobs):
			result = bench_provision_progress("bench-Z")
		self.assertEqual(result["stage"], "failed")
