# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


class _Base(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def _doc(self):
		return frappe._dict(host_name="pbx-1", server_type="docker", ssh_host="1.2.3.4",
			ssh_port=22, ssh_user="sanad", proxy_port=2375,
			ssh_identity="/k/i", ssh_cert="/k/c")


class TestGate(_Base):
	def test_provision_requires_telephony_ops_or_system_manager(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony", side_effect=frappe.PermissionError) as gate:
			with self.assertRaises(frappe.PermissionError):
				it.telephony_provision(host="pbx-1", site_url="https://s", oc_instance="i")
		gate.assert_called_once()


class TestProvision(_Base):
	def test_provision_pushes_bundle_runs_compose_and_audits(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony"), \
			patch.object(it, "_managed_doc", return_value=self._doc()), \
			patch("press.infra.telephony_bundle.read_bundle", return_value={"/srv/oc-asterisk/docker-compose.yml": "x"}), \
			patch("press.infra.telephony_bundle.render_env", return_value="OC_SITE=https://s\n"), \
			patch.object(it, "_resolve_public_ip", return_value="9.9.9.9"), \
			patch.object(it, "mint_listener_token", return_value="k:s"), \
			patch("press.infra.host_exec.run_host_script", return_value="up\n") as run, \
			patch.object(it, "log_infra_action") as audit, \
			patch.object(it, "_upsert_pbx_record") as rec:
			out = it.telephony_provision(host="pbx-1", site_url="https://s", oc_instance="i")

		self.assertTrue(out["ok"])
		# the .env was pushed (files dict carries it) and compose up was run
		_, kw = run.call_args
		self.assertIn("/srv/oc-asterisk/.env", kw["files"])
		self.assertIn("docker compose", run.call_args[0][1])
		audit.assert_called()
		self.assertEqual(audit.call_args.kwargs["outcome"], "success")
		rec.assert_called_once()
		# the minted secret is NOT echoed back to the caller
		self.assertNotIn("k:s", str(out))

	def test_provision_audits_error_and_reraises(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony"), \
			patch.object(it, "_managed_doc", return_value=self._doc()), \
			patch("press.infra.telephony_bundle.read_bundle", side_effect=RuntimeError("no app")), \
			patch.object(it, "log_infra_action") as audit:
			with self.assertRaises(RuntimeError):
				it.telephony_provision(host="pbx-1", site_url="https://s", oc_instance="i")
		self.assertEqual(audit.call_args.kwargs["outcome"], "error")


class TestFirewall(_Base):
	def test_allow_enables_ufw_ssh_first_then_sip_rtp_from_trunk_only(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony"), \
			patch.object(it, "_managed_doc", return_value=self._doc()), \
			patch("press.infra.host_exec.run_host_script", return_value="Rules updated\n") as run, \
			patch.object(it, "log_infra_action"):
			out = it.firewall_rule(host="pbx-1", trunk_ip="13.36.71.209", action="allow")

		script = run.call_args[0][1]
		# SSH is allowed BEFORE enable so we never lock ourselves out
		self.assertLess(script.index("allow 22"), script.index("--force enable"))
		self.assertIn("from 13.36.71.209 to any port 5060", script)
		self.assertIn("10000:20000", script)
		self.assertTrue(out["ok"])

	def test_rejects_bad_trunk_ip(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony"), patch.object(it, "_managed_doc", return_value=self._doc()):
			with self.assertRaises(frappe.ValidationError):
				it.firewall_rule(host="pbx-1", trunk_ip="13.36.71.209; rm -rf /", action="allow")

	def test_rejects_bad_action(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony"), patch.object(it, "_managed_doc", return_value=self._doc()):
			with self.assertRaises(frappe.ValidationError):
				it.firewall_rule(host="pbx-1", trunk_ip="1.2.3.4", action="nuke")


class TestMintToken(_Base):
	def test_self_source_mints_for_instance_owner(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_instance_owner", return_value="agent@x.com"), \
			patch("press.api.infra_telephony.frappe.get_doc") as get_doc:
			user = MagicMock()
			user.generate_keys.return_value = "SECRET"
			user.api_key = "KEY"
			get_doc.return_value = user
			tok = it.mint_listener_token(site="self", instance="i", listener_user=None)
		self.assertEqual(tok, "KEY:SECRET")

	def test_external_source_uses_operator_supplied_keysecret(self):
		from press.api import infra_telephony as it

		tok = it.mint_listener_token(site="https://cloud.frappe.io", instance="i",
			listener_user=None, supplied_key_secret="K2:S2")
		self.assertEqual(tok, "K2:S2")

	def test_external_without_supplied_secret_throws(self):
		from press.api import infra_telephony as it

		with self.assertRaises(frappe.ValidationError):
			it.mint_listener_token(site="https://cloud.frappe.io", instance="i", listener_user=None)


class TestDecommission(_Base):
	def test_stops_containers_closes_firewall_keeps_recordings_and_revokes(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony"), \
			patch.object(it, "_managed_doc", return_value=self._doc()), \
			patch("press.infra.host_exec.run_host_script", return_value="done\n") as run, \
			patch.object(it, "_revoke_token") as revoke, \
			patch.object(it, "log_infra_action"), \
			patch.object(it, "_mark_pbx_decommissioned") as mark:
			out = it.decommission_pbx(host="pbx-1", instance="i")

		script = run.call_args[0][1]
		self.assertIn("docker compose", script)
		self.assertIn("down", script)
		self.assertIn("deny 5060", script)
		# recordings are explicitly NOT deleted
		self.assertNotIn("rm -rf", script)
		self.assertIn("recordings", script)  # a comment/keep marker referencing them
		revoke.assert_called_once()
		mark.assert_called_once()
		self.assertTrue(out["ok"])


class TestDescribeIsSecretFree(_Base):
	def test_describe_returns_counts_only_no_secrets(self):
		from press.api import infra_telephony as it

		status = {"trunk_registered": True, "active_calls": 2, "listener_connected": True,
			"containers": [{"name": "oc-asterisk", "state": "run"}]}
		with patch.object(it, "_only_telephony"), \
			patch.object(it, "_managed_doc", return_value=self._doc()), \
			patch.object(it, "telephony_status", return_value=status):
			out = it.telephony_describe(host="pbx-1")

		self.assertEqual(out["active_calls"], 2)
		self.assertTrue(out["trunk_registered"])
		self.assertTrue(out["listener_connected"])
		# NO secret-bearing keys leak through
		blob = str(out).lower()
		for forbidden in ("password", "secret", "api_token", "ami_password", "pjsip", "trunk_password"):
			self.assertNotIn(forbidden, blob)


class TestStatusReader(_Base):
	def test_status_parses_registrations_and_channel_count(self):
		from press.api import infra_telephony as it

		# pjsip registrations block + `core show channels` count line
		reg = "<Registration/ServerURI..............................>  <Auth..>  <Status.......>\n" \
			"bevatel/sip:13.36.71.209                                  6050      Registered\n"
		chans = "2 active channels\n3 active calls\n5 calls processed\n"
		with patch("press.infra.host_exec.run_host_script", side_effect=[reg, chans, "oc-listener\n"]):
			doc = self._doc()
			out = it.telephony_status(doc)
		self.assertTrue(out["trunk_registered"])
		self.assertEqual(out["active_calls"], 3)
		self.assertTrue(out["listener_connected"])
