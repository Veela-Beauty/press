# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt
"""Confirm it's you and Edit tools (PRS-SP-22). Mock-only: the cache, the session, the token reads and every write are
patched (for the press-ctrl runner's MOCK_ONLY list)."""

from __future__ import annotations

import json
import unittest
from contextlib import ExitStack
from unittest.mock import patch

import frappe

from press.mcp_server import token_confirm, token_edit

OWNER = "owner@example.com"


class FakeCache:
	def __init__(self):
		self.data = {}

	def get_value(self, key):
		return self.data.get(key)

	def set_value(self, key, value, expires_in_sec=None):
		self.data[key] = value

	def delete_value(self, key):
		self.data.pop(key, None)

	def make_key(self, key):
		return key

	def ttl(self, key):
		return 600 if key in self.data else -2


class ConfirmCase(unittest.TestCase):
	def setUp(self):
		self.cache = FakeCache()
		self.stack = ExitStack()
		self.stack.enter_context(patch.object(frappe, "cache", self.cache))
		session = frappe._dict(
			user=OWNER, sid="browser-a", data=frappe._dict(creation="2026-11-28 08:00:00", user_type="Website User")
		)
		self.stack.enter_context(patch.object(frappe, "session", session))

	def tearDown(self):
		self.stack.close()


class TestConfirm(ConfirmCase):
	def test_unknown_way_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			token_confirm.confirm("sms", code="123456")

	def test_password_confirms_and_opens_the_window(self):
		with patch.object(token_confirm.auth, "_check_password") as check:
			out = token_confirm.confirm("password", password="right")
		check.assert_called_once_with(OWNER, "right")
		self.assertEqual(out["how"], "password")
		self.assertEqual(token_confirm.confirmed_how(), "password")

	def test_email_code_uses_the_issue_token_code(self):
		with patch.object(token_confirm.auth, "_verify_email_otp") as verify:
			token_confirm.confirm("email", code=" 123456 ")
		verify.assert_called_once_with(OWNER, "123456")
		self.assertEqual(token_confirm.confirmed_how(), "email code")

	def test_without_a_confirm_sensitive_actions_are_refused(self):
		with self.assertRaises(frappe.PermissionError):
			token_confirm.confirmed_how()

	def test_five_wrong_tries_lock_confirming(self):
		with patch.object(token_confirm.auth, "_check_password", side_effect=frappe.ValidationError("no")):
			for _ in range(token_confirm.MAX_FAILURES):
				with self.assertRaises(frappe.ValidationError):
					token_confirm.confirm("password", password="wrong")
		with (
			patch.object(token_confirm.auth, "_check_password") as check,
			self.assertRaises(frappe.ValidationError) as ctx,
		):
			token_confirm.confirm("password", password="right")
		check.assert_not_called()
		self.assertIn("10 minutes", str(ctx.exception))

	def test_an_app_linked_during_this_login_does_not_count(self):
		"""Linking needs no password, so an app linked in this session proves no more than the session."""
		row = frappe._dict(enabled=1, creation="2026-11-28 09:00:00")  # after the 08:00 login
		with (
			patch.object(frappe.db, "get_value", return_value=row),
			patch.object(token_confirm, "_app_code_ok", return_value=True) as ok,
			self.assertRaises(frappe.ValidationError),
		):
			token_confirm.confirm("app", code="123456")
		ok.assert_not_called()
		self.assertIsNone(self.cache.get_value(token_confirm._key("fail")), "not a wrong try")

	def test_an_app_linked_before_this_login_confirms(self):
		row = frappe._dict(enabled=1, creation="2026-11-01 09:00:00")
		with (
			patch.object(frappe.db, "get_value", return_value=row),
			patch.object(token_confirm, "_app_code_ok", return_value=True),
		):
			token_confirm.confirm("app", code="123456")
		self.assertEqual(token_confirm.confirmed_how(), "authenticator code")

	def test_a_wrong_app_code_counts_as_a_wrong_try(self):
		row = frappe._dict(enabled=1, creation="2026-11-01 09:00:00")
		with (
			patch.object(frappe.db, "get_value", return_value=row),
			patch.object(token_confirm, "_app_code_ok", return_value=False),
			self.assertRaises(frappe.ValidationError),
		):
			token_confirm.confirm("app", code="000000")
		self.assertEqual(self.cache.get_value(token_confirm._key("fail")), 1)


class TestEditTools(ConfirmCase):
	def _token(self, **over):
		return frappe._dict(
			{
				"name": "MCPT-1",
				"user": OWNER,
				"label": "agent",
				"scope": json.dumps(["site_status", "list_sites"]),
				"revoked": 0,
				"expires_at": frappe.utils.add_days(frappe.utils.now_datetime(), 10),
				"risky_tools_enabled": 0,
				**over,
			}
		)

	def _update(self, scope, token=None, confirmed=True, system=False):
		token = token or self._token()
		with ExitStack() as s:
			s.enter_context(patch.object(frappe.db, "get_value", return_value=token))
			setv = s.enter_context(patch.object(frappe.db, "set_value"))
			s.enter_context(patch.object(frappe.db, "commit"))
			log = s.enter_context(patch.object(token_edit, "log_token_action"))
			s.enter_context(patch.object(token_edit, "_user_is_system", return_value=system))
			how = s.enter_context(
				patch.object(
					token_confirm,
					"confirmed_how",
					return_value="password" if confirmed else None,
					side_effect=None if confirmed else frappe.PermissionError("confirm first"),
				)
			)
			try:
				out = token_edit.update_token_tools("MCPT-1", scope)
			except (frappe.PermissionError, frappe.ValidationError) as e:
				out = e
		return out, setv, log, how

	def test_only_the_tokens_own_user(self):
		out, setv, _, _ = self._update(["site_status"], token=self._token(user="someone@example.com"))
		self.assertIsInstance(out, frappe.PermissionError)
		setv.assert_not_called()

	def test_a_revoked_token_is_refused(self):
		out, setv, _, _ = self._update(["site_status"], token=self._token(revoked=1))
		self.assertIsInstance(out, frappe.ValidationError)
		setv.assert_not_called()

	def test_unknown_and_empty_lists_are_refused(self):
		for scope in (["no_such_tool"], []):
			out, setv, _, _ = self._update(scope)
			self.assertIsInstance(out, frappe.ValidationError)
			setv.assert_not_called()

	def test_removing_only_needs_no_confirm_and_is_recorded(self):
		out, setv, log, how = self._update(["site_status"])
		how.assert_not_called()
		self.assertEqual(out["removed"], ["list_sites"])
		setv.assert_called_once()
		self.assertEqual(log.call_args.args[0], "Edit Tools")
		self.assertEqual(log.call_args.args[3], "no confirm (only removed)")

	def test_adding_without_a_confirm_writes_nothing(self):
		out, setv, log, _ = self._update(["site_status", "list_sites", "site_backup"], confirmed=False)
		self.assertIsInstance(out, frappe.PermissionError)
		setv.assert_not_called()
		log.assert_not_called()

	def test_adding_a_high_risk_tool_turns_risky_tools_on_pending_for_a_non_system_user(self):
		out, setv, log, _ = self._update(["site_status", "list_sites", "site_archive"])
		values = setv.call_args.args[2]
		self.assertEqual((values["risky_tools_enabled"], values["approval_status"]), (1, "pending"))
		self.assertEqual(out["added"], ["site_archive"])
		self.assertIn("Site — Archive", log.call_args.args[2])

	def test_a_system_user_gets_risky_tools_approved(self):
		_, setv, _, _ = self._update(["site_status", "list_sites", "site_archive"], system=True)
		self.assertEqual(setv.call_args.args[2]["approval_status"], "approved")

	def test_no_change_writes_nothing(self):
		out, setv, log, _ = self._update(["list_sites", "site_status"])
		self.assertEqual((out["added"], out["removed"]), ([], []))
		setv.assert_not_called()
		log.assert_not_called()

	def test_an_every_tool_token_loses_only_what_is_unticked(self):
		from press.mcp_server.tools import TOOLS

		all_but_one = [t for t in TOOLS if t != "site_run_sql"]
		out, _, _, how = self._update(all_but_one, token=self._token(scope="[]"))
		self.assertEqual((out["added"], out["removed"]), ([], ["site_run_sql"]))
		how.assert_not_called()


class TestHistory(ConfirmCase):
	def test_someone_else_cannot_read_it(self):
		with (
			patch.object(frappe.db, "get_value", return_value="someone@example.com"),
			self.assertRaises(frappe.PermissionError),
		):
			token_edit.token_history("MCPT-1")

	def test_rows_say_when_who_what_how(self):
		row = frappe._dict(
			actor=OWNER,
			action_type="Edit Tools",
			reason="added Site — Archive",
			context_json=json.dumps({"how": "authenticator code"}),
			creation="2026-11-28 10:41:00",
		)
		with (
			patch.object(frappe.db, "get_value", return_value=OWNER),
			patch.object(frappe, "get_all", return_value=[row]) as get_all,
			patch.object(token_edit, "get_fullname", return_value="Eslam"),
		):
			out = token_edit.token_history("MCPT-1")
		self.assertEqual(get_all.call_args.kwargs["filters"], {"target_token": "MCPT-1"})
		self.assertEqual(
			out[0],
			{
				"when": "2026-11-28 10:41:00",
				"who": "Eslam",
				"what": "added Site — Archive",
				"how": "authenticator code",
			},
		)


class TestReviewFixes(ConfirmCase):
	"""Review of 28 Nov: reissue owner-only and confirmed, issue honours the lock, fail closed, per-session unlock."""

	def _reissue(self, token, confirmed=True):
		from press.mcp_server import auth

		how = (
			patch.object(token_confirm, "confirmed_how", return_value="password")
			if confirmed
			else patch.object(token_confirm, "confirmed_how", side_effect=frappe.PermissionError("confirm first"))
		)
		with (
			patch.object(auth.frappe, "get_doc", return_value=token),
			patch.object(frappe.db, "set_value") as setv,
			how,
		):
			try:
				auth.reissue_token("MCPT-1")
			except (frappe.PermissionError, frappe.ValidationError) as e:
				return e, setv
		return None, setv

	def test_a_system_user_cannot_reissue_someone_elses_token(self):
		frappe.session.data.user_type = "System User"
		err, setv = self._reissue(frappe._dict(user="someone@example.com", revoked=0))
		self.assertIsInstance(err, frappe.PermissionError)
		setv.assert_not_called()

	def test_a_revoked_token_cannot_be_reissued(self):
		err, setv = self._reissue(frappe._dict(user=OWNER, revoked=1))
		self.assertIsInstance(err, frappe.ValidationError)
		setv.assert_not_called()

	def test_reissue_needs_a_recent_confirm(self):
		err, setv = self._reissue(frappe._dict(user=OWNER, revoked=0), confirmed=False)
		self.assertIsInstance(err, frappe.PermissionError)
		setv.assert_not_called()

	def test_issuing_does_not_unlock_while_confirming_is_locked(self):
		self.cache.set_value(token_confirm._key("lock"), 1)
		token_confirm.mark_confirmed("password")
		with self.assertRaises(frappe.PermissionError):
			token_confirm.confirmed_how()

	def test_wrong_tries_counted_elsewhere_lock_confirming(self):
		for _ in range(token_confirm.MAX_FAILURES - 1):
			self.assertFalse(token_confirm.count_failure())
		self.assertTrue(token_confirm.count_failure())
		self.assertEqual(self.cache.get_value(token_confirm._key("lock")), 1)

	def test_without_a_recorded_login_time_an_app_does_not_count(self):
		frappe.session.data.creation = None
		with patch.object(frappe.db, "get_value", return_value=frappe._dict(enabled=1, creation="2020-01-01 00:00:00")):
			self.assertEqual(token_confirm._app_state(OWNER), "new")

	def test_a_confirm_belongs_to_one_browser_session(self):
		frappe.session.sid = "browser-a"
		token_confirm.mark_confirmed("password")
		frappe.session.sid = "browser-b"
		with self.assertRaises(frappe.PermissionError):
			token_confirm.confirmed_how()

	def test_a_retired_tool_in_the_old_list_does_not_block_a_save(self):
		token = frappe._dict(
			name="MCPT-1",
			user=OWNER,
			label="agent",
			scope=json.dumps(["site_status", "a_retired_tool"]),
			revoked=0,
			expires_at=frappe.utils.add_days(frappe.utils.now_datetime(), 10),
			risky_tools_enabled=0,
		)
		with (
			patch.object(frappe.db, "get_value", return_value=token),
			patch.object(frappe.db, "set_value") as setv,
			patch.object(frappe.db, "commit"),
			patch.object(token_edit, "log_token_action"),
		):
			out = token_edit.update_token_tools("MCPT-1", ["site_status", "a_retired_tool"])
		self.assertEqual(out["scope"], ["site_status"])
		self.assertEqual((out["added"], out["removed"]), ([], []))
		setv.assert_not_called()
