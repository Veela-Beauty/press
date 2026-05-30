# -*- coding: utf-8 -*-
# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

"""Confidential-site admin PIN management: change (email confirm-link) + reset (email OTP).

The active PIN lives in Press Settings.admin_login_pin (verified by
Site.login_as_admin). Changing it is two-step: request_admin_pin_change stores the
new value as PENDING + a token and emails a dashboard confirm link; the PIN only
goes live when confirm_admin_pin_change(token) runs. A forgotten PIN is reset via
an OTP emailed to Press Settings.confidential_alert_email.

All request endpoints are gated to Platform Admins (admin_access) or System
Managers via require_team_role_flag. The confirm endpoints validate a
single-use, time-limited secret instead of a role (the secret IS the proof).
"""

import frappe
from frappe.utils import now_datetime, add_to_date, get_datetime

TOKEN_TTL_MIN = 60
OTP_TTL_MIN = 10


def _require_admin():
	from press.press.doctype.team.press_role_bridge import require_team_role_flag
	from press.utils import get_current_team

	require_team_role_flag(get_current_team(), "admin_access")


def _settings():
	return frappe.get_doc("Press Settings")


def _alert_email():
	return frappe.db.get_single_value("Press Settings", "confidential_alert_email")


@frappe.whitelist()
def request_admin_pin_change(new_pin):
	"""Store new_pin as pending + email a confirm link. PIN is NOT active yet."""
	_require_admin()
	if not new_pin or len(str(new_pin)) < 4:
		frappe.throw("PIN must be at least 4 characters.")
	token = frappe.generate_hash(length=40)
	s = _settings()
	s.pending_admin_login_pin = new_pin
	s.pin_change_token = token
	s.pin_change_token_expiry = add_to_date(now_datetime(), minutes=TOKEN_TTL_MIN)
	s.save(ignore_permissions=True)

	recipient = _alert_email()
	if recipient:
		url = frappe.utils.get_url(f"/dashboard/confirm-pin/{token}")
		_send(
			recipient,
			"[Press] Confirm the confidential-site admin PIN change",
			(
				f"A change to the confidential-site admin PIN was requested by "
				f"{frappe.session.user}.<br><br>"
				f"The new PIN only takes effect after you confirm:<br>"
				f'<a href="{url}">{url}</a><br><br>'
				f"This link expires in {TOKEN_TTL_MIN} minutes. If you did not request "
				f"this, ignore this email and the PIN stays unchanged."
			),
		)
	return {"sent_to": recipient}


@frappe.whitelist(allow_guest=True)
def confirm_admin_pin_change(token):
	"""Activate the pending PIN if the token is valid + unexpired. Single-use."""
	s = _settings()
	stored = s.pin_change_token
	if not token or not stored or token != stored:
		frappe.throw("Invalid or already-used confirmation link.")
	if not s.pin_change_token_expiry or get_datetime(s.pin_change_token_expiry) < now_datetime():
		frappe.throw("This confirmation link has expired. Request the PIN change again.")
	pending = s.get_password("pending_admin_login_pin", raise_exception=False)
	if not pending:
		frappe.throw("No pending PIN to confirm.")
	s.admin_login_pin = pending
	s.pending_admin_login_pin = ""
	s.pin_change_token = ""
	s.pin_change_token_expiry = None
	s.save(ignore_permissions=True)
	return {"confirmed": True}


@frappe.whitelist()
def request_admin_pin_reset():
	"""Email a one-time code to the alert address for a forgotten-PIN reset."""
	_require_admin()
	import random

	otp = f"{random.randint(0, 999999):06d}"
	s = _settings()
	s.pin_reset_otp = otp
	s.pin_reset_otp_expiry = add_to_date(now_datetime(), minutes=OTP_TTL_MIN)
	s.save(ignore_permissions=True)
	recipient = _alert_email()
	if recipient:
		_send(
			recipient,
			"[Press] Confidential-site admin PIN reset code",
			(
				f"Your one-time code to reset the confidential-site admin PIN is "
				f"<b>{otp}</b>.<br>It expires in {OTP_TTL_MIN} minutes. "
				f"Requested by {frappe.session.user}."
			),
		)
	return {"sent_to": recipient}


@frappe.whitelist()
def confirm_admin_pin_reset(otp, new_pin):
	"""Set a new PIN if the emailed OTP is valid + unexpired."""
	_require_admin()
	if not new_pin or len(str(new_pin)) < 4:
		frappe.throw("PIN must be at least 4 characters.")
	s = _settings()
	stored = s.get_password("pin_reset_otp", raise_exception=False) or s.pin_reset_otp
	if not otp or not stored or str(otp) != str(stored):
		frappe.throw("Incorrect reset code.")
	if not s.pin_reset_otp_expiry or get_datetime(s.pin_reset_otp_expiry) < now_datetime():
		frappe.throw("This reset code has expired. Request a new one.")
	s.admin_login_pin = new_pin
	s.pin_reset_otp = ""
	s.pin_reset_otp_expiry = None
	# any pending change is now moot
	s.pending_admin_login_pin = ""
	s.pin_change_token = ""
	s.save(ignore_permissions=True)
	return {"reset": True}


def _send(recipient, subject, message):
	try:
		frappe.sendmail(recipients=[recipient], subject=subject, message=message, now=True)
	except Exception:
		frappe.log_error("Admin PIN email failed", frappe.get_traceback())
