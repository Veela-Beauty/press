# -*- coding: utf-8 -*-
# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

"""Tests for confidential admin PIN change (confirm-link) + reset (OTP)."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from press.api import security


class TestAdminPinChange(FrappeTestCase):
	def setUp(self):
		s = frappe.get_doc("Press Settings")
		s.admin_login_pin = "1111"
		s.pending_admin_login_pin = ""
		s.pin_change_token = ""
		s.pin_change_token_expiry = None
		s.pin_reset_otp = ""
		s.pin_reset_otp_expiry = None
		s.confidential_alert_email = "eng.elgogary@gmail.com"
		s.save(ignore_permissions=True)

	def _pin(self):
		return frappe.get_doc("Press Settings").get_password(
			"admin_login_pin", raise_exception=False
		)

	def test_change_requires_confirmation_pin_not_yet_active(self):
		with patch.object(security, "_require_admin"), patch.object(security, "_send"):
			security.request_admin_pin_change("2222")
		# active PIN unchanged until confirmed
		self.assertEqual(self._pin(), "1111")
		token = frappe.get_doc("Press Settings").pin_change_token
		self.assertTrue(token)

	def test_confirm_activates_pending_pin(self):
		with patch.object(security, "_require_admin"), patch.object(security, "_send"):
			security.request_admin_pin_change("2222")
		token = frappe.get_doc("Press Settings").pin_change_token
		security.confirm_admin_pin_change(token)
		self.assertEqual(self._pin(), "2222")
		# token cleared (single-use)
		self.assertFalse(frappe.get_doc("Press Settings").pin_change_token)

	def test_confirm_bad_token_throws(self):
		with patch.object(security, "_require_admin"), patch.object(security, "_send"):
			security.request_admin_pin_change("2222")
		with self.assertRaises(frappe.ValidationError):
			security.confirm_admin_pin_change("wrong-token")
		self.assertEqual(self._pin(), "1111")  # unchanged

	def test_confirm_expired_token_throws(self):
		from frappe.utils import add_to_date, now_datetime

		with patch.object(security, "_require_admin"), patch.object(security, "_send"):
			security.request_admin_pin_change("2222")
		s = frappe.get_doc("Press Settings")
		token = s.pin_change_token
		s.pin_change_token_expiry = add_to_date(now_datetime(), minutes=-1)
		s.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			security.confirm_admin_pin_change(token)

	def test_short_pin_rejected(self):
		with patch.object(security, "_require_admin"):
			with self.assertRaises(frappe.ValidationError):
				security.request_admin_pin_change("12")


class TestAdminPinReset(FrappeTestCase):
	def setUp(self):
		s = frappe.get_doc("Press Settings")
		s.admin_login_pin = "1111"
		s.pin_reset_otp = ""
		s.pin_reset_otp_expiry = None
		s.confidential_alert_email = "eng.elgogary@gmail.com"
		s.save(ignore_permissions=True)

	def _pin(self):
		return frappe.get_doc("Press Settings").get_password(
			"admin_login_pin", raise_exception=False
		)

	def test_reset_otp_then_set_new_pin(self):
		captured = {}

		def fake_send(recipient, subject, message):
			# pull the OTP out of the stored field (message has it too)
			captured["sent"] = True

		with patch.object(security, "_require_admin"), patch.object(
			security, "_send", side_effect=fake_send
		):
			security.request_admin_pin_reset()
			otp = frappe.get_doc("Press Settings").get_password(
				"pin_reset_otp", raise_exception=False
			) or frappe.get_doc("Press Settings").pin_reset_otp
			security.confirm_admin_pin_reset(otp, "3333")
		self.assertEqual(self._pin(), "3333")
		self.assertTrue(captured.get("sent"))

	def test_reset_wrong_otp_throws(self):
		with patch.object(security, "_require_admin"), patch.object(security, "_send"):
			security.request_admin_pin_reset()
			with self.assertRaises(frappe.ValidationError):
				security.confirm_admin_pin_reset("000000", "3333")
		self.assertEqual(self._pin(), "1111")
