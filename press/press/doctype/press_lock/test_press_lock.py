# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from press.api.lock import acquire, release, status
from press.press.doctype.app.test_app import create_test_app
from press.press.doctype.release_group.test_release_group import (
	create_test_release_group,
)


class TestPressLock(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		# Block real builds during RG creation
		self._deploy_patcher = patch(
			"press.press.doctype.release_group.release_group.ReleaseGroup.create_deploy_candidate"
		)
		self._deploy_patcher.start()
		self.addCleanup(self._deploy_patcher.stop)

		self.app = create_test_app()
		self.rg = create_test_release_group(apps=[self.app])

	def tearDown(self):
		frappe.db.delete(
			"Press Lock",
			{"target_doctype": ("in", ("Site", "Release Group"))},
		)

	def test_acquire_when_free_returns_active_status(self):
		result = acquire(
			target_doctype="Release Group",
			target_name=self.rg.name,
			reason="testing acquire",
			ttl_minutes=10,
		)
		self.assertEqual(result["status"], "active")
		self.assertEqual(result["holder"], frappe.session.user)
		self.assertEqual(result["reason"], "testing acquire")
		self.assertIn("expires_at", result)

	def test_same_user_reacquire_refreshes_ttl(self):
		acquire(
			target_doctype="Release Group",
			target_name=self.rg.name,
			reason="first call",
			ttl_minutes=10,
		)
		# Same user re-acquires with new reason — should succeed and refresh
		result = acquire(
			target_doctype="Release Group",
			target_name=self.rg.name,
			reason="updated reason",
			ttl_minutes=20,
		)
		self.assertEqual(result["status"], "active")
		self.assertEqual(result["reason"], "updated reason")

	def test_override_logs_both_reasons(self):
		acquire(
			target_doctype="Release Group",
			target_name=self.rg.name,
			reason="first reason",
			ttl_minutes=10,
		)
		# Pretend a different user overrides — write directly to simulate
		frappe.db.set_value(
			"Press Lock",
			{"target_doctype": "Release Group", "target_name": self.rg.name, "revoked": 0},
			"holder",
			"someone-else@example.com",
		)
		result = acquire(
			target_doctype="Release Group",
			target_name=self.rg.name,
			reason="must do critical fix",
			ttl_minutes=5,
			override=True,
		)
		self.assertEqual(result["status"], "active")
		s = status(target_doctype="Release Group", target_name=self.rg.name)
		self.assertEqual(s["holder"], frappe.session.user)
		self.assertGreaterEqual(len(s.get("override_history", [])), 1)
		hist = s["override_history"][0]
		self.assertEqual(hist["override_reason"], "must do critical fix")
		self.assertEqual(hist["prev_reason"], "first reason")

	def test_release_clears_lock(self):
		acquire(
			target_doctype="Release Group",
			target_name=self.rg.name,
			reason="r",
			ttl_minutes=10,
		)
		release(target_doctype="Release Group", target_name=self.rg.name)
		s = status(target_doctype="Release Group", target_name=self.rg.name)
		self.assertEqual(s["status"], "free")

	def test_status_free_when_no_lock(self):
		s = status(target_doctype="Release Group", target_name=self.rg.name)
		self.assertEqual(s["status"], "free")

	def test_lock_auto_expires_after_ttl(self):
		acquire(
			target_doctype="Release Group",
			target_name=self.rg.name,
			reason="r",
			ttl_minutes=10,
		)
		# Force expiry by backdating expires_at
		frappe.db.set_value(
			"Press Lock",
			{"target_doctype": "Release Group", "target_name": self.rg.name, "revoked": 0},
			"expires_at",
			now_datetime() - timedelta(minutes=1),
		)
		s = status(target_doctype="Release Group", target_name=self.rg.name)
		self.assertEqual(s["status"], "free")  # expired => free

	def test_bench_lock_blocks_site_lock_status(self):
		# Lock the Release Group
		acquire(
			target_doctype="Release Group",
			target_name=self.rg.name,
			reason="parent lock",
			ttl_minutes=10,
		)
		# Check status of a site whose group is self.rg.name (mocked).
		fake_site = "fake-site-for-parent-lock-test.example.com"
		original_get_value = frappe.db.get_value

		def fake_get_value(doctype, name, fieldname=None, *a, **kw):
			if doctype == "Site" and name == fake_site and fieldname == "group":
				return self.rg.name
			return original_get_value(doctype, name, fieldname, *a, **kw)

		with patch.object(frappe.db, "get_value", side_effect=fake_get_value):
			s = status(target_doctype="Site", target_name=fake_site)
		self.assertEqual(s["status"], "blocked_by_parent")
		self.assertEqual(s["parent_lock"]["target_name"], self.rg.name)
