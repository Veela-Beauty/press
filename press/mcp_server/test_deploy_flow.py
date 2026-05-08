# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from press.mcp_server.deploy_flow import (
	agent_job_list,
	app_release_approve,
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
			return None

		with patch("press.mcp_server.deploy_flow.frappe.db.get_value", side_effect=fake_get_value):
			result = wait_for_bench_flip(
				site_name="x.example.com",
				target_candidate="deploy-NEW",
			)
		self.assertEqual(result["status"], "pending")
		self.assertEqual(result["current_candidate"], "deploy-OLD")
		self.assertEqual(result["target_candidate"], "deploy-NEW")

	def test_wait_for_bench_flip_returns_flipped_when_match(self):
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
