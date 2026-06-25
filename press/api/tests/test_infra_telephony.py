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


# ─── Plan-3 dashboard reads + actions ─────────────────────────────────────────


class TestGetPbxTreeGate(_Base):
	def test_get_pbx_tree_requires_telephony_role(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony", side_effect=frappe.PermissionError) as gate, \
			patch.object(it.frappe, "cache"):
			with self.assertRaises(frappe.PermissionError):
				it.get_pbx_tree()
		gate.assert_called_once()


class TestHostAction(_Base):
	def test_reregister_runs_fixed_asterisk_reload_and_audits(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony"), \
			patch.object(it, "_managed_doc", return_value=self._doc()), \
			patch("press.infra.host_exec.run_host_script", return_value="ok\n") as run, \
			patch.object(it, "log_infra_action") as audit:
			out = it.host_action(host="pbx-1", action="reregister")

		script = run.call_args[0][1]
		self.assertIn("pjsip send register", script)
		# no host-controlled interpolation in the action script
		self.assertNotIn("pbx-1", script)
		self.assertEqual(audit.call_args.kwargs["outcome"], "success")
		self.assertTrue(out["ok"])

	def test_restart_targets_oc_asterisk_via_compose(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony"), \
			patch.object(it, "_managed_doc", return_value=self._doc()), \
			patch("press.infra.host_exec.run_host_script", return_value="ok\n") as run, \
			patch.object(it, "log_infra_action"):
			it.host_action(host="pbx-1", action="restart")
		script = run.call_args[0][1]
		self.assertIn("docker compose restart oc-asterisk", script)

	def test_rejects_unknown_action(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony"), patch.object(it, "_managed_doc", return_value=self._doc()):
			with self.assertRaises(frappe.ValidationError):
				it.host_action(host="pbx-1", action="nuke")

	def test_error_path_audits_and_reraises(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony"), \
			patch.object(it, "_managed_doc", return_value=self._doc()), \
			patch("press.infra.host_exec.run_host_script", side_effect=RuntimeError("down")), \
			patch.object(it, "log_infra_action") as audit:
			with self.assertRaises(RuntimeError):
				it.host_action(host="pbx-1", action="stop")
		self.assertEqual(audit.call_args.kwargs["outcome"], "error")


class TestListenerLog(_Base):
	def test_log_tails_oc_listener_and_audits_read(self):
		from press.api import infra_telephony as it

		raw = "2026-06-25T10:00:00 INFO listener started\n2026-06-25T10:00:01 ERROR ami auth failed\n"
		with patch.object(it, "_only_telephony"), \
			patch.object(it, "_managed_doc", return_value=self._doc()), \
			patch("press.infra.host_exec.run_host_script", return_value=raw) as run, \
			patch.object(it, "log_infra_action") as audit:
			out = it.get_listener_log(host="pbx-1", tail=50)

		self.assertIn("docker logs --tail 50 oc-listener", run.call_args[0][1])
		self.assertEqual(audit.call_args.kwargs["outcome"], "read")
		self.assertEqual(out[0]["level"], "INFO")
		self.assertEqual(out[1]["level"], "ERR")
		self.assertIn("ami auth failed", out[1]["msg"])

	def test_rejects_bad_tail(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony"):
			with self.assertRaises(frappe.ValidationError):
				it.get_listener_log(host="pbx-1", tail="abc")

	def test_parse_log_lines_keeps_unmatched_as_info(self):
		from press.api import infra_telephony as it

		out = it._parse_log_lines("a plain line with no level\n\n  WARN something\n")
		self.assertEqual(out[0], {"ts": "", "level": "INFO", "msg": "a plain line with no level"})
		self.assertEqual(out[1]["level"], "WARN")


class TestRotateSecret(_Base):
	def test_rotate_gates_validates_and_never_returns_secret(self):
		from press.api import infra_telephony as it
		from press.api import telephony_secrets as ts

		env_before = "AMI_PASSWORD=old\nOC_API_TOKEN=k:s\nOC_SITE=https://x\n"
		with patch.object(it, "_only_telephony"), \
			patch.object(it, "_sole_active_instance", return_value="i"), \
			patch.object(it, "_managed_doc", return_value=self._doc()), \
			patch.object(ts, "_managed_doc", return_value=self._doc()), \
			patch("press.infra.host_exec.run_host_script", side_effect=[env_before, "recreated\n"]) as run, \
			patch("press.infra.telephony_bundle.gen_secret", return_value="NEWAMIPW"), \
			patch.object(it, "log_infra_action") as audit:
			out = it.rotate_secret(host="pbx-1", secret_id="ami_password")

		# the .env push carries the rewritten AMI line, the rest preserved
		pushed = run.call_args.kwargs["files"]["/srv/oc-asterisk/.env"]
		self.assertIn("AMI_PASSWORD=NEWAMIPW", pushed)
		self.assertIn("OC_API_TOKEN=k:s", pushed)        # untouched
		self.assertIn("OC_SITE=https://x", pushed)        # untouched
		self.assertEqual(audit.call_args.kwargs["outcome"], "success")
		# the new secret is NOT echoed back
		self.assertNotIn("NEWAMIPW", str(out))

	def test_rotate_requires_a_secret_id(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony"):
			with self.assertRaises(frappe.ValidationError):
				it.rotate_secret(host="pbx-1")

	def test_normalize_which_maps_aliases_and_rejects_unknown(self):
		from press.api import telephony_secrets as ts

		self.assertEqual(ts.normalize_which("ami_password"), "ami")
		self.assertEqual(ts.normalize_which("api_token"), "token")
		self.assertEqual(ts.normalize_which("AMI"), "ami")
		with self.assertRaises(frappe.ValidationError):
			ts.normalize_which("trunk_password")

	def test_rewrite_env_line_replaces_only_target_and_appends_when_missing(self):
		from press.api import telephony_secrets as ts

		text = "A=1\nAMI_PASSWORD=old\nB=2\n"
		out = ts._rewrite_env_line(text, "AMI_PASSWORD", "new")
		self.assertEqual(out, "A=1\nAMI_PASSWORD=new\nB=2\n")
		# appended when absent
		out2 = ts._rewrite_env_line("A=1\n", "OC_API_TOKEN", "k:s")
		self.assertEqual(out2, "A=1\nOC_API_TOKEN=k:s\n")


class TestProvisionTargets(_Base):
	def test_external_site_returns_empty_sites_gracefully(self):
		from press.api import telephony_targets as tt

		with patch.object(tt, "_provisionable_hosts", return_value=[{"name": "h", "label": "h", "has_headroom": True}]):
			out = tt.build_provision_targets(site_url="https://acme.frappe.cloud")
		self.assertEqual(out["sites"], [])
		self.assertEqual(len(out["hosts"]), 1)

	def test_local_site_lists_voip_instances_with_presence_only(self):
		from press.api import telephony_targets as tt

		rows = [{"name": "i1", "instance_name": "Acme VoIP", "company": "Acme", "trunk_password": "secret"}]
		with patch.object(tt, "_oc_doctype_present", return_value=True), \
			patch.object(tt, "_provisionable_hosts", return_value=[]), \
			patch("press.api.telephony_targets.frappe.get_all", return_value=rows):
			out = tt.build_provision_targets(site_url="self")
		inst = out["sites"][0]["instances"][0]
		self.assertTrue(inst["has_auth"])
		# the actual trunk secret never leaks into the payload
		self.assertNotIn("secret", str(out))


class TestValidateInstanceAuth(_Base):
	def test_local_presence_true_when_trunk_password_set(self):
		from press.api import telephony_targets as tt

		with patch.object(tt, "_oc_doctype_present", return_value=True), \
			patch("press.api.telephony_targets.frappe.db.get_value", return_value="x"):
			out = tt._validate_local("i")
		self.assertTrue(out["has_auth"])
		self.assertNotIn("x", out["detail"])  # the value is not echoed

	def test_local_presence_false_when_missing(self):
		from press.api import telephony_targets as tt

		with patch.object(tt, "_oc_doctype_present", return_value=True), \
			patch("press.api.telephony_targets.frappe.db.get_value", return_value=None):
			out = tt._validate_local("i")
		self.assertFalse(out["has_auth"])

	def test_external_without_token_is_unauthenticated(self):
		from press.api import telephony_targets as tt

		out = tt._validate_external(site_url="https://x", instance="i", api_token=None)
		self.assertFalse(out["has_auth"])


class TestTestHostConnection(_Base):
	def test_existing_host_reuses_test_connection(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony"), \
			patch("press.api.telephony_targets.frappe.db.exists"), \
			patch("press.api.infra_telephony.frappe.db.exists", return_value=True), \
			patch("press.api.infra_board.test_connection", return_value={"ssh_ok": True, "docker_ok": True}) as tc, \
			patch("press.api.infra_board.add_managed_host") as add:
			out = it.test_host_connection(host_name="pbx-1")
		add.assert_not_called()
		tc.assert_called_once()
		self.assertTrue(out["ok"])
		self.assertTrue(out["docker_ok"])

	def test_failure_returns_ok_false_with_detail_not_raises(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony"), \
			patch("press.api.infra_telephony.frappe.db.exists", return_value=True), \
			patch("press.api.infra_board.test_connection", side_effect=RuntimeError("refused")):
			out = it.test_host_connection(host_name="pbx-1")
		self.assertFalse(out["ok"])
		self.assertIn("refused", out["detail"])


class TestProvisionStatus(_Base):
	def test_sync_backend_returns_terminal_done_with_all_steps(self):
		from press.api import infra_telephony as it

		with patch.object(it, "_only_telephony"):
			out = it.provision_status(job_id=None)
		self.assertEqual(out["state"], "done")
		self.assertEqual(len(out["steps"]), 4)
		self.assertTrue(all(s["state"] == "done" for s in out["steps"]))


class TestPbxTreeShape(_Base):
	def test_host_status_pure_mapping(self):
		from press.api import telephony_tree as tr

		self.assertEqual(tr._host_status(reach_ok=False, listener_connected=True, any_unreg=False), "unknown")
		self.assertEqual(tr._host_status(reach_ok=True, listener_connected=False, any_unreg=False), "warn")
		self.assertEqual(tr._host_status(reach_ok=True, listener_connected=True, any_unreg=True), "warn")
		self.assertEqual(tr._host_status(reach_ok=True, listener_connected=True, any_unreg=False), "up")

	def test_build_host_shape_matches_page_contract(self):
		from press.api import telephony_tree as tr

		status = {"trunk_registered": True, "active_calls": 2, "listener_connected": True}
		with patch("press.api.infra_telephony._managed_doc", return_value=self._doc()), \
			patch("press.api.infra_telephony.telephony_status", return_value=status), \
			patch.object(tr, "_instance_meta", return_value={"trunk": "Acme", "did": "+966"}):
			h = tr._build_host("pbx-1", [{"instance": "i", "site_url": "https://s", "public_ip": "9.9.9.9"}])
		for key in ("name", "ip", "status", "container", "listener", "active_calls", "cpu_pct", "uptime", "instances"):
			self.assertIn(key, h)
		self.assertEqual(h["listener"], "connected")
		self.assertEqual(h["active_calls"], 2)
		self.assertEqual(h["instances"][0]["reg"], "reg")
		self.assertEqual(h["instances"][0]["site"], "s")

	def test_roll_up_matches_tele_derive_summary(self):
		from press.api import telephony_tree as tr

		hosts = [
			{"listener": "connected", "active_calls": 1, "instances": [{"reg": "reg"}, {"reg": "reg"}]},
			{"listener": "connected", "active_calls": 0, "instances": [{"reg": "unreg"}]},
			{"listener": "disconnected", "active_calls": 0, "instances": []},
		]
		s = tr._roll_up(hosts)
		self.assertEqual(s, {"hosts": 3, "trunks": 3, "registered": 2, "trunkDown": 1, "activeCalls": 1, "listenersUp": 2})
