# Copyright (c) 2026, Frappe and Contributors
# See license.txt

import base64
import re
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.press.doctype.ssh_certificate import revoked_keys as rk

ED = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl"
RSA = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC7"


def row(user="islam@x.com", key=ED, key_name="k1", disabled=0, removed=0, enabled=1):
	return frappe._dict(
		user=user,
		ssh_public_key=f"{key} laptop; rm -rf /",
		key_name=key_name,
		is_disabled=disabled,
		is_removed=removed,
		enabled=enabled,
	)


class TestPlainKey(FrappeTestCase):
	def test_comment_is_dropped(self):
		self.assertEqual(rk.plain_key(f"{ED} eslam@laptop 'x'"), ED)

	def test_anything_but_a_key_is_refused(self):
		for bad in (None, "", "ssh-ed25519", "ssh-ed25519 AAAA'$(id)", "bash -c x", "ssh-dss AAAAB3"):
			self.assertIsNone(rk.plain_key(bad), bad)


class TestKeysToRevoke(FrappeTestCase):
	def run_with(self, rows, reach=True):
		with (
			patch("frappe.db.get_value", return_value="team1"),
			patch("frappe.db.sql", return_value=rows),
			patch.object(rk, "reaches", return_value=reach) as reaches,
		):
			return rk.keys_to_revoke("bench-0080"), reaches

	def test_a_member_in_good_standing_is_not_listed(self):
		keys, _ = self.run_with([row()])
		self.assertEqual(keys, [])

	def test_each_reason_lists_the_key(self):
		for r in (row(disabled=1), row(removed=1), row(enabled=0), row(key_name=None)):
			keys, _ = self.run_with([r])
			self.assertEqual(keys, [ED], r)

	def test_a_member_whose_role_no_longer_covers_the_bench_is_listed(self):
		keys, _ = self.run_with([row(), row(key=RSA, key_name="k2")], reach=False)
		self.assertEqual(keys, sorted([ED, RSA]))

	def test_role_checked_once_per_user(self):
		_, reaches = self.run_with([row(), row(key=RSA, key_name="k2")])
		reaches.assert_called_once_with("islam@x.com", "team1", "bench-0080")

	def test_a_key_that_is_not_a_key_is_never_sent(self):
		keys, _ = self.run_with([row(key="nonsense'; id", disabled=1)])
		self.assertEqual(keys, [])


class TestReaches(FrappeTestCase):
	"""reaches() mirrors role_guard for a user that is not the session user."""

	def run_with(
		self, user_type="Website User", team=None, member=True, any_role=True, mine=(), roles=(), listed=False
	):
		team = (
			team if team is not None else frappe._dict(user="owner@x.com", enabled=1, relaxed_permissions=0)
		)

		def get_value(doctype, name, fields=None, as_dict=False):
			return user_type if doctype == "User" else team

		def exists(doctype, filters=None):
			return {"Team Member": member, "Press Role": any_role, "Press Role Resource": listed}[doctype]

		def get_all(doctype, filters=None, fields=None, pluck=None):
			return list(mine) if doctype == "Press Role User" else list(roles)

		with (
			patch("frappe.db.get_value", side_effect=get_value),
			patch("frappe.db.exists", side_effect=exists),
			patch("frappe.get_all", side_effect=get_all),
		):
			return rk.reaches("islam@x.com", "team1", "bench-0080")

	def test_system_user_reaches(self):
		self.assertTrue(self.run_with(user_type="System User", member=False))

	def test_disabled_team_reaches_nobody(self):
		self.assertFalse(
			self.run_with(team=frappe._dict(user="islam@x.com", enabled=0, relaxed_permissions=0))
		)

	def test_owner_reaches(self):
		self.assertTrue(self.run_with(team=frappe._dict(user="islam@x.com", enabled=1), member=False))

	def test_left_the_team(self):
		self.assertFalse(self.run_with(member=False))

	def test_team_without_roles_shows_everything(self):
		self.assertTrue(self.run_with(any_role=False))

	def test_no_role_refused_unless_relaxed(self):
		self.assertFalse(self.run_with())
		relaxed = frappe._dict(user="owner@x.com", enabled=1, relaxed_permissions=1)
		self.assertTrue(self.run_with(team=relaxed))

	def test_admin_or_all_benches_role(self):
		for flags in (
			{"admin_access": 1, "all_release_groups": 0},
			{"admin_access": 0, "all_release_groups": 1},
		):
			self.assertTrue(self.run_with(mine=["r1"], roles=[NS(name="r1", **flags)]), flags)

	def test_listed_bench_only(self):
		limited = [NS(name="r1", admin_access=0, all_release_groups=0)]
		self.assertTrue(self.run_with(mine=["r1"], roles=limited, listed=True))
		self.assertFalse(self.run_with(mine=["r1"], roles=limited, listed=False))

	def test_role_of_another_team_does_not_count(self):
		self.assertFalse(self.run_with(mine=["other-team-role"], roles=[]))


class TestWriteCommand(FrappeTestCase):
	def test_one_single_quoted_script_carrying_the_keys(self):
		cmd = rk.write_command(f"{ED}\n")
		self.assertTrue(cmd.startswith("bash -c '") and cmd.endswith("'"))
		self.assertEqual(cmd.count("'"), 2)
		b64 = re.search(r"echo (\S*) \| base64 -d", cmd).group(1)
		self.assertEqual(base64.b64decode(b64).decode(), f"{ED}\n")

	def test_config_line_added_once_checked_then_reloaded(self):
		cmd = rk.write_command("")
		self.assertIn('if ! grep -q "^RevokedKeys "', cmd)
		self.assertLess(cmd.index("sshd -t"), cmd.index("kill -HUP"))
		self.assertIn("sshd_config.before-revoked-keys", cmd.split("else")[1])
		self.assertLess(
			cmd.index("> /home/frappe/frappe-bench/config/ssh/revoked_keys.new"), cmd.index("grep")
		)


class TestSyncBench(FrappeTestCase):
	def run_with(self, cached, returncode=0):
		bench = MagicMock()
		bench.docker_execute.return_value = {"returncode": returncode, "output": "x"}
		with (
			patch.object(rk, "keys_to_revoke", return_value=[ED]),
			patch("frappe.get_doc", return_value=bench),
			patch.object(frappe.cache, "get_value", return_value=cached),
			patch.object(frappe.cache, "set_value") as set_value,
		):
			try:
				sent = rk.sync_bench("bench-0080-000001-press-f1", "bench-0080")
			except frappe.ValidationError:
				sent = "failed"
		return sent, bench, set_value

	def test_sent_when_changed_and_remembered(self):
		sent, bench, set_value = self.run_with(cached=None)
		self.assertTrue(sent)
		bench.docker_execute.assert_called_once()
		set_value.assert_called_once()

	def test_not_sent_again_when_unchanged(self):
		import hashlib

		digest = hashlib.sha256(f"{ED}\n".encode()).hexdigest()
		sent, bench, _ = self.run_with(cached=digest)
		self.assertFalse(sent)
		bench.docker_execute.assert_not_called()

	def test_a_failed_write_is_not_remembered(self):
		sent, _, set_value = self.run_with(cached=None, returncode=3)
		self.assertEqual(sent, "failed")
		set_value.assert_not_called()

	def test_one_failing_bench_does_not_stop_the_others(self):
		benches = [frappe._dict(name="b1", group="g1"), frappe._dict(name="b2", group="g2")]
		with (
			patch("frappe.get_all", return_value=benches),
			patch.object(rk, "sync_bench", side_effect=[Exception("agent down"), True]) as sync,
			patch.object(rk, "log_error") as log,
		):
			rk.sync_development_benches()
		self.assertEqual(sync.call_count, 2)
		log.assert_called_once()
