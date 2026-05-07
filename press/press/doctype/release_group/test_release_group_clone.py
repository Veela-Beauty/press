# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.press.doctype.release_group.release_group_clone import clone_release_group
from press.press.doctype.app.test_app import create_test_app
from press.press.doctype.release_group.test_release_group import (
	create_test_release_group,
)


class TestReleaseGroupClone(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		# Block real builds on demo.mvpstorm.com — every test in this class
		# gets a mocked create_deploy_candidate. Task 4's specific test uses
		# its own context-local patch and asserts call args.
		self._deploy_patcher = patch(
			"press.press.doctype.release_group.release_group.ReleaseGroup.create_deploy_candidate"
		)
		self._mock_deploy = self._deploy_patcher.start()
		self._mock_deploy.return_value.schedule_build_and_deploy.return_value = None
		self.addCleanup(self._deploy_patcher.stop)

		self.source = create_test_release_group(
			apps=[create_test_app()],
		)

	def test_clone_copies_apps_version_and_server(self):
		new_name = clone_release_group(
			self.source.name,
			new_title="Clone of " + self.source.title,
			lifetime="persistent",
		)

		clone = frappe.get_doc("Release Group", new_name)
		self.assertEqual(clone.version, self.source.version)
		self.assertEqual(
			[a.app for a in clone.apps],
			[a.app for a in self.source.apps],
		)
		self.assertEqual(
			[s.server for s in clone.servers],
			[s.server for s in self.source.servers],
		)
		self.assertEqual(clone.cloned_from, self.source.name)
		self.assertEqual(clone.clone_lifetime, "persistent")
		self.assertIsNone(clone.clone_expires_at)

	def test_clone_sandbox_sets_expires_at_24h(self):
		from datetime import timedelta

		from frappe.utils import now_datetime

		before = now_datetime()
		new_name = clone_release_group(
			self.source.name,
			new_title="Sandbox " + self.source.title,
			lifetime="sandbox",
		)

		clone = frappe.get_doc("Release Group", new_name)
		self.assertEqual(clone.clone_lifetime, "sandbox")
		self.assertIsNotNone(clone.clone_expires_at)
		delta = clone.clone_expires_at - before
		self.assertGreater(delta, timedelta(hours=23, minutes=55))
		self.assertLess(delta, timedelta(hours=24, minutes=5))

	def test_clone_invalid_lifetime_raises(self):
		with self.assertRaises(frappe.ValidationError):
			clone_release_group(
				self.source.name,
				new_title="Bad",
				lifetime="forever",  # not in {sandbox, persistent}
			)

	def test_clone_unknown_source_raises(self):
		with self.assertRaises(frappe.DoesNotExistError):
			clone_release_group(
				"RG-does-not-exist-9999",
				new_title="X",
				lifetime="persistent",
			)
