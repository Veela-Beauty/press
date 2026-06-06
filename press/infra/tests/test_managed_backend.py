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


class TestAdapterFactory(FrappeTestCase):
	def test_factory_routes_by_type(self):
		from press.infra.adapters import base
		from press.infra.adapters.ssh_docker import SshDockerAdapter
		from press.infra.adapters.ssh_plain import SshPlainAdapter

		dh = frappe._dict(server_type="docker")
		ph = frappe._dict(server_type="plain")
		self.assertIsInstance(base.get_adapter(dh), SshDockerAdapter)
		self.assertIsInstance(base.get_adapter(ph), SshPlainAdapter)

	def test_factory_rejects_unknown(self):
		from press.infra.adapters import base

		with self.assertRaises(frappe.ValidationError):
			base.get_adapter(frappe._dict(server_type="quantum"))


class TestSshPlain(FrappeTestCase):
	def test_enumerate_parses_systemctl_and_df(self):
		from press.infra.adapters.ssh_plain import SshPlainAdapter

		host = frappe._dict(host_name="storage-1", ssh_host="10.0.0.5", ssh_user="sanad", ssh_port=22, server_type="plain")
		systemctl_out = "sshd.service loaded active running\nborgmatic.timer loaded active waiting\nfail2ban.service loaded failed failed"
		# enumerate now issues ONE compound _ssh call; output is marker-joined
		combined = systemctl_out + "\n##B##\n13\n##B##\n8\n##B##\n3"
		ad = SshPlainAdapter()
		with patch.object(ad, "_ssh", return_value=combined):
			out = ad.enumerate(host)

		names = {u["name"] for u in out["units"]}
		self.assertIn("sshd.service", names)
		failed = next(u for u in out["units"] if u["name"] == "fail2ban.service")
		self.assertEqual(failed["state"], "down")  # failed -> down
		self.assertEqual(out["metrics"]["disk"], 13)

	def test_enumerate_unreachable_host_is_empty(self):
		from press.infra.adapters.ssh_plain import SshPlainAdapter

		host = frappe._dict(host_name="storage-1", ssh_host="10.0.0.5", ssh_user="sanad", ssh_port=22, server_type="plain")
		ad = SshPlainAdapter()
		# unreachable host -> _ssh returns empty stdout for every probe
		with patch.object(ad, "_ssh", return_value=""):
			out = ad.enumerate(host)

		self.assertEqual(out["units"], [])
		self.assertEqual(out["metrics"], {"cpu": 0, "mem": 0, "disk": 0, "req": 0})


class TestSshDocker(FrappeTestCase):
	def _host(self):
		return frappe._dict(host_name="acc-1", ssh_host="10.0.0.7", ssh_user="sanad", ssh_port=22, proxy_port=2375, server_type="docker")

	def test_enumerate_maps_containers(self):
		from press.infra.adapters.ssh_docker import SshDockerAdapter

		api_list = [
			{"Id": "a" * 64, "Names": ["/eltarak-frontend"], "Image": "erpnext15:latest", "State": "running", "Status": "Up 3 days"},
			{"Id": "b" * 64, "Names": ["/eltarak-configurator"], "Image": "erpnext15:latest", "State": "exited", "Status": "Exited (2) 1h ago"},
		]
		ad = SshDockerAdapter()
		with patch.object(ad, "_api", return_value=api_list):
			out = ad.enumerate(self._host())

		names = {u["name"] for u in out["units"]}
		self.assertIn("eltarak-frontend", names)
		cfg = next(u for u in out["units"] if u["name"] == "eltarak-configurator")
		self.assertEqual(cfg["state"], "exit2")  # exited code 2
		self.assertEqual(cfg["kind"], "container")

	def test_control_validates_action_and_id(self):
		from press.infra.adapters.ssh_docker import SshDockerAdapter

		ad = SshDockerAdapter()
		with patch.object(ad, "_api", return_value=[{"Id": "a" * 64, "Names": ["/x"]}]):
			# bad action rejected
			with self.assertRaises(frappe.ValidationError):
				ad.control(self._host(), "a" * 64, "exec")
			# unknown id rejected (not in enumerated set)
			with self.assertRaises(frappe.ValidationError):
				ad.control(self._host(), "f" * 64, "restart")

	def test_control_posts_for_valid(self):
		from press.infra.adapters.ssh_docker import SshDockerAdapter

		ad = SshDockerAdapter()
		posted = {}
		def fake_api(host, method, path, **kw):
			if method == "GET":
				return [{"Id": "a" * 64, "Names": ["/x"]}]
			posted["path"] = path
			return {}
		with patch.object(ad, "_api", side_effect=fake_api):
			res = ad.control(self._host(), "a" * 64, "restart")
		self.assertTrue(res["ok"])
		self.assertEqual(posted["path"], "/containers/" + "a" * 64 + "/restart")

	def test_state_unhealthy_not_heal(self):
		from press.infra.adapters.ssh_docker import SshDockerAdapter
		ad = SshDockerAdapter()
		api_list = [{"Id": "a" * 64, "Names": ["/x"], "State": "running", "Status": "Up 5 minutes (unhealthy)"}]
		with patch.object(ad, "_api", return_value=api_list):
			out = ad.enumerate(self._host())
		self.assertEqual(out["units"][0]["state"], "unhealth")

	def test_state_oom_exit_is_error(self):
		from press.infra.adapters.ssh_docker import SshDockerAdapter
		ad = SshDockerAdapter()
		api_list = [{"Id": "a" * 64, "Names": ["/x"], "State": "exited", "Status": "Exited (137) 2m ago"}]
		with patch.object(ad, "_api", return_value=api_list):
			out = ad.enumerate(self._host())
		self.assertEqual(out["units"][0]["state"], "exit2")

	def test_state_restarting(self):
		from press.infra.adapters.ssh_docker import SshDockerAdapter
		ad = SshDockerAdapter()
		api_list = [{"Id": "a" * 64, "Names": ["/x"], "State": "restarting", "Status": "Restarting (1) 3s ago"}]
		with patch.object(ad, "_api", return_value=api_list):
			out = ad.enumerate(self._host())
		self.assertEqual(out["units"][0]["state"], "restart")

	def test_control_rejects_trailing_newline_id(self):
		from press.infra.adapters.ssh_docker import SshDockerAdapter
		ad = SshDockerAdapter()
		with patch.object(ad, "_api", return_value=[{"Id": "a" * 64, "Names": ["/x"]}]):
			with self.assertRaises(frappe.ValidationError):
				ad.control(self._host(), "a" * 64 + "\n", "restart")

	def test_logs_rejects_trailing_newline_and_unknown_id(self):
		from press.infra.adapters.ssh_docker import SshDockerAdapter
		ad = SshDockerAdapter()
		with patch.object(ad, "_api", return_value=[{"Id": "a" * 64, "Names": ["/x"]}]):
			with self.assertRaises(frappe.ValidationError):
				ad.logs(self._host(), "a" * 64 + "\n")
			with self.assertRaises(frappe.ValidationError):
				ad.logs(self._host(), "f" * 64)

	def test_logs_clamps_tail_and_checks_membership(self):
		from press.infra.adapters.ssh_docker import SshDockerAdapter
		ad = SshDockerAdapter()
		captured = {}
		def fake_api(host, method, path, **kw):
			if path.startswith("/containers/json"):
				return [{"Id": "a" * 64, "Names": ["/x"]}]
			captured["path"] = path
			return "line1\nline2"
		with patch.object(ad, "_api", side_effect=fake_api):
			out = ad.logs(self._host(), "a" * 64, tail=999999)
		self.assertIn("tail=5000", captured["path"])
		self.assertEqual(out, ["line1", "line2"])



class TestMergedTree(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_managed_hosts_merge_with_overload(self):
		from press.api import infra_board

		host = frappe._dict(host_name="acc-1", server_type="docker", ssh_host="10.0.0.7", reach="ok")
		enum = {"units": [{"name": "x", "kind": "container", "state": "stop"}], "metrics": {"cpu": 10, "mem": 92, "disk": 40, "req": 100}}
		with patch.object(infra_board, "_press_servers", return_value=[]), patch.object(
			infra_board, "_managed_hosts", return_value=[host]
		), patch.object(infra_board, "_enumerate_managed", return_value=enum):
			tree = infra_board._build_tree()

		node = next(s for s in tree["servers"] if s["name"] == "acc-1")
		self.assertEqual(node["kind"], "managed")
		self.assertEqual(node["server_type"], "docker")
		self.assertEqual(node["overload"], "crit")  # mem 92 -> crit
		self.assertEqual(node["health"], "down")     # a container is stopped

	def test_managed_enumerate_failure_is_unknown(self):
		from press.api import infra_board

		host = frappe._dict(host_name="acc-2", server_type="plain", status="Active")
		failed = {"units": [], "metrics": {"cpu": 0, "mem": 0, "disk": 0, "req": 0}, "reach": "fail"}
		with patch.object(infra_board, "_press_servers", return_value=[]), patch.object(
			infra_board, "_managed_hosts", return_value=[host]
		), patch.object(infra_board, "_enumerate_managed", return_value=failed):
			tree = infra_board._build_tree()
		node = next(s for s in tree["servers"] if s["name"] == "acc-2")
		self.assertEqual(node["health"], "unknown")


class TestHostControl(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_action_routes_to_adapter_and_audits(self):
		from press.api import infra_board

		host = frappe._dict(host_name="acc-1", server_type="docker")
		adapter = MagicMock()
		adapter.control.return_value = {"ok": True}
		with patch("press.api.infra_board.frappe.only_for"), patch.object(
			infra_board, "_managed_doc", return_value=host
		), patch("press.infra.adapters.base.get_adapter", return_value=adapter):
			res = infra_board.host_unit_action("acc-1", "a" * 64, "restart")

		self.assertTrue(res["ok"])
		adapter.control.assert_called_once_with(host, "a" * 64, "restart")
		row = frappe.get_last_doc("Infra Action Log")
		self.assertEqual(row.action, "restart")
		row.delete()

	def test_action_audits_error_and_reraises(self):
		from press.api import infra_board

		host = frappe._dict(host_name="acc-1", server_type="docker")
		adapter = MagicMock()
		adapter.control.side_effect = frappe.ValidationError("bad")
		with patch("press.api.infra_board.frappe.only_for"), patch.object(
			infra_board, "_managed_doc", return_value=host
		), patch("press.infra.adapters.base.get_adapter", return_value=adapter):
			with self.assertRaises(frappe.ValidationError):
				infra_board.host_unit_action("acc-1", "a" * 64, "exec")
		row = frappe.get_last_doc("Infra Action Log")
		self.assertEqual(row.outcome, "error")
		row.delete()
