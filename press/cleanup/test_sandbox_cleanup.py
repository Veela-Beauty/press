# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from press.cleanup.sandbox_cleanup import expire_sandbox_release_groups
from press.press.doctype.app.test_app import create_test_app
from press.press.doctype.release_group.test_release_group import (
	create_test_release_group,
)


class TestSandboxCleanup(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_expire_drops_only_expired_sandbox(self):
		app = create_test_app()
		expired = create_test_release_group(apps=[app])
		expired.clone_lifetime = "sandbox"
		expired.clone_expires_at = now_datetime() - timedelta(hours=1)
		expired.save(ignore_permissions=True)

		future = create_test_release_group(apps=[app])
		future.clone_lifetime = "sandbox"
		future.clone_expires_at = now_datetime() + timedelta(hours=10)
		future.save(ignore_permissions=True)

		persistent = create_test_release_group(apps=[app])
		persistent.clone_lifetime = "persistent"
		persistent.clone_expires_at = now_datetime() - timedelta(hours=99)
		persistent.save(ignore_permissions=True)

		with patch(
			"press.cleanup.sandbox_cleanup._archive_release_group"
		) as m:
			expire_sandbox_release_groups()
			archived = [c.args[0] for c in m.call_args_list]

		self.assertIn(expired.name, archived)
		self.assertNotIn(future.name, archived)
		self.assertNotIn(persistent.name, archived)
