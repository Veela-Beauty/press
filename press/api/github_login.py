# Copyright (c) 2026, Accurate Systems. MIT License. See license.txt
"""Sign in to AutoDeploy with GitHub: the login page's GitHub button (LoginSignup.vue). GitHub proves the e-mail;
the account steps are Google's (press/api/oauth_finish.py). Reached through press.api.github.login and
press.api.github.login_callback (one-line wrappers there).

Keys in site_config "github_login": {"client_id", "client_secret", "redirect_uri"}; the GitHub OAuth App's callback URL
is <site>/api/method/press.api.github.login_callback."""

from __future__ import annotations

from urllib.parse import urlencode

import frappe
import requests
from frappe import _

from press.api.oauth_finish import finish_oauth_login
from press.utils import log_error

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
API_URL = "https://api.github.com"
CALLBACK_PATH = "/api/method/press.api.github.login_callback"
STATE_SECONDS = 5 * 60
TIMEOUT = 15


def settings() -> dict:
	conf = frappe.conf.get("github_login") or {}
	if not conf.get("client_id") or not conf.get("client_secret"):
		frappe.throw(_("GitHub sign-in is not set up yet. Please sign in with your email."))
	return conf


def redirect_uri(conf: dict) -> str:
	return conf.get("redirect_uri") or frappe.utils.get_url(CALLBACK_PATH)


def login(product=None):
	"""Send the browser to GitHub with a one-time state that only this site can match on the way back."""
	conf = settings()
	state = frappe.generate_hash(length=32)
	frappe.cache().set_value(f"github_login:{state}", {"product": product}, expires_in_sec=STATE_SECONDS)
	query = urlencode(
		{
			"client_id": conf["client_id"],
			"redirect_uri": redirect_uri(conf),
			"scope": "read:user user:email",
			"state": state,
			"allow_signup": "true",
		}
	)
	frappe.local.response.type = "redirect"
	frappe.local.response.location = f"{AUTHORIZE_URL}?{query}"


def login_callback(code=None, state=None, error=None):
	key = f"github_login:{state}"
	payload = frappe.cache().get_value(key) if state else None
	if not payload:
		frappe.local.response["http_status_code"] = 401
		return _("This sign-in did not start here or took longer than 5 minutes. Please try again.")
	frappe.cache().delete_value(key)

	product = payload.get("product")
	product_trial = frappe.db.get_value("Product Trial", product, ["name"], as_dict=1) if product else None

	if error or not code:  # Cancel on GitHub's page
		return back_to_login(product_trial)

	try:
		token = exchange_code(settings(), code)
		email = primary_verified_email(token)
		first_name, last_name = names(token)
	except Exception as e:
		log_error("GitHub Login failed", data=e)
		return back_to_login(product_trial)

	if not email:
		frappe.respond_as_web_page(
			_("No verified e-mail on GitHub"),
			_(
				"Your GitHub account has no verified primary e-mail. Verify it on GitHub, or sign in with your e-mail."
			),
			primary_action="/dashboard/login",
			primary_label=_("Login with Email"),
		)
		return None

	finish_oauth_login(email, first_name, last_name, product_trial, "GitHub")
	return None


def back_to_login(product_trial):
	frappe.local.response.type = "redirect"
	frappe.local.response.location = (
		f"/dashboard/login?product={product_trial.name}" if product_trial else "/dashboard/login"
	)


def exchange_code(conf: dict, code: str) -> str:
	response = requests.post(
		TOKEN_URL,
		data={
			"client_id": conf["client_id"],
			"client_secret": conf["client_secret"],
			"code": code,
			"redirect_uri": redirect_uri(conf),
		},
		headers={"Accept": "application/json"},
		timeout=TIMEOUT,
	)
	response.raise_for_status()
	data = response.json()
	if not data.get("access_token"):
		raise ValueError(data.get("error_description") or data.get("error") or "GitHub gave no access token")
	return data["access_token"]


def github_get(token: str, path: str):
	response = requests.get(
		f"{API_URL}{path}",
		headers={
			"Authorization": f"Bearer {token}",
			"Accept": "application/vnd.github+json",
			"X-GitHub-Api-Version": "2022-11-28",
		},
		timeout=TIMEOUT,
	)
	response.raise_for_status()
	return response.json()


def primary_verified_email(token: str) -> str | None:
	"""Only GitHub's primary AND verified address: an unverified one could belong to someone else's account here."""
	for row in github_get(token, "/user/emails"):
		if row.get("primary") and row.get("verified") and row.get("email"):
			return row["email"].strip().lower()
	return None


def names(token: str) -> tuple[str, str]:
	user = github_get(token, "/user")
	full = (user.get("name") or user.get("login") or "").strip()
	first, _sep, last = full.partition(" ")
	return first, last.strip()
