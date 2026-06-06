# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestManagedHost(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_create_and_required_fields(self):
		doc = frappe.get_doc(
			{
				"doctype": "Managed Host",
				"host_name": "test-docker-1",
				"ssh_host": "10.0.0.9",
				"ssh_user": "sanad",
				"server_type": "docker",
			}
		).insert()
		self.assertEqual(doc.ssh_port, 22)
		self.assertEqual(doc.status, "Pending")
		self.assertEqual(doc.host_principal, "test-docker-1")
		doc.delete()
