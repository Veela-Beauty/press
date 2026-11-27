# Copyright (c) 2026, Accurate Systems. MIT License. See license.txt
"""What every social sign-in does once the provider has proved the e-mail (Google, GitHub): the same account rules
for both. Moved from press/api/google.py callback (2026-11-27) with two fixes from review: the 2FA check now runs
before every path (the product sign-up path used to skip it), and the account is signed in under the user name
AutoDeploy stores, not the provider's spelling of the e-mail."""

from __future__ import annotations

import frappe
from frappe import _

from press.utils.telemetry import capture


def finish_oauth_login(email, first_name, last_name, product_trial, provider):
	team = frappe.db.get_value("Team", {"user": email}, ["name", "enabled", "user"], as_dict=True)

	if team and not team.enabled:
		frappe.throw(_("Account {0} has been deactivated").format(email))
		return

	if team and frappe.db.get_value("User 2FA", {"user": team.user, "enabled": 1}):
		frappe.respond_as_web_page(
			_("Two-Factor Authentication Required"),
			_(
				"{0} OAuth login doesn't support 2FA. Please login using your email and verification code / password."
			).format(provider),
			primary_action="/dashboard/login",
			primary_label=_("Login with Email"),
		)
		return

	# an existing account outside the SaaS product sign-up flow: sign in
	if team and not product_trial:
		frappe.local.login_manager.login_as(team.user)
		frappe.local.response.type = "redirect"
		frappe.local.response.location = "/dashboard"
		return

	account_request = frappe.get_doc(
		doctype="Account Request",
		email=email,
		first_name=first_name,
		last_name=last_name,
		role="Press Admin",
		oauth_signup=True,
		product_trial=product_trial.name if product_trial else None,
	)
	account_request.insert(ignore_permissions=True)
	frappe.db.commit()

	if product_trial:
		# dummy event so that the stat in funnel won't break
		capture("otp_verified", "fc_product_trial", account_request.name)

	frappe.local.response.type = "redirect"
	if team and product_trial:
		frappe.local.login_manager.login_as(team.user)
		frappe.local.response.location = f"/dashboard/create-site/{product_trial.name}/setup"
	else:
		frappe.local.response.location = account_request.get_verification_url()
