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


	def test_rejects_unsafe_host_name(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({"doctype": "Managed Host", "host_name": "bad name!", "ssh_host": "10.0.0.1", "ssh_user": "x", "server_type": "docker"}).insert()


class TestAudit(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_log_infra_action_creates_row(self):
		from press.infra.adapters.base import log_infra_action

		log_infra_action(host="host-x", unit="redis-queue", action="restart", outcome="success")
		row = frappe.get_last_doc("Infra Action Log")
		self.assertEqual(row.host, "host-x")
		self.assertEqual(row.action, "restart")
		self.assertEqual(row.outcome, "success")
		self.assertEqual(row.actor, "Administrator")
		frappe.delete_doc("Infra Action Log", row.name)
		frappe.db.commit()

	def test_actor_is_the_acting_user(self):
		from press.infra.adapters.base import log_infra_action

		frappe.set_user("Guest")
		try:
			log_infra_action(host="h2", unit="u2", action="stop", outcome="success")
			row = frappe.get_last_doc("Infra Action Log")
			self.assertEqual(row.actor, "Guest")
		finally:
			frappe.set_user("Administrator")
		frappe.delete_doc("Infra Action Log", row.name)
		frappe.db.commit()

	def test_failed_outcome_survives_rollback(self):
		from press.infra.adapters.base import log_infra_action

		log_infra_action(host="h3", unit="u3", action="kill", outcome="error", detail="boom")
		name = frappe.get_last_doc("Infra Action Log").name
		frappe.db.rollback()
		self.assertTrue(frappe.db.exists("Infra Action Log", name))  # durable
		frappe.delete_doc("Infra Action Log", name)
		frappe.db.commit()


class TestSshCa(FrappeTestCase):
	def test_sign_cert_uses_principal_and_ttl(self):
		from press.infra import ssh_ca

		calls = {}

		def fake_run(cmd, **kw):
			calls["cmd"] = cmd
			return MagicMock(returncode=0, stderr="")

		with patch.object(ssh_ca, "_ca_private_key", return_value="/tmp/fake-ca"), patch.object(
			ssh_ca.subprocess, "run", side_effect=fake_run
		):
			cert = ssh_ca.sign_cert(principal="client-prod-1", pubkey_path="/tmp/k.pub")

		joined = " ".join(calls["cmd"])
		self.assertIn("-n client-prod-1", joined)
		self.assertIn("-V +8h", joined)
		self.assertTrue(cert.endswith("-cert.pub"))
