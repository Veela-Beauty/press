# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.api.bench import _service_action


class TestServiceAction(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_rejects_invalid_action(self):
		with self.assertRaises(frappe.ValidationError):
			_service_action("bench-X-001-press-f1", "redis-queue", "delete")

	def test_rejects_unknown_program(self):
		with patch("press.api.bench.get_processes", return_value=[{"program": "redis-queue"}]):
			with self.assertRaises(frappe.ValidationError):
				_service_action("bench-X-001-press-f1", "ghost-program", "restart")

	def test_calls_supervisorctl_for_valid_program(self):
		fake_bench = MagicMock()
		with patch("press.api.bench.get_processes", return_value=[{"program": "redis-queue"}, {"program": "frappe-web"}]), patch(
			"press.api.bench.frappe.get_doc", return_value=fake_bench
		):
			result = _service_action("bench-X-001-press-f1", "redis-queue", "restart")
		fake_bench.supervisorctl.assert_called_once_with("restart", programs=["redis-queue"])
		self.assertTrue(result["ok"])
		self.assertEqual(result["action"], "restart")
		self.assertEqual(result["program"], "redis-queue")
