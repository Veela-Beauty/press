# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import frappe
import requests
from frappe.model.document import Document

if TYPE_CHECKING:
	from frappe.types import DF


GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_REVOKE_URL_FMT = "https://api.github.com/applications/{client_id}/grant"
# Refresh tokens from a minute before actual expiry to avoid edge races
REFRESH_LEAD_SECONDS = 60


class UserGitHubAuth(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		access_token: DF.Password | None
		connected_on: DF.Datetime | None
		expires_at: DF.Datetime | None
		github_username: DF.Data | None
		is_revoked: DF.Check
		last_used_on: DF.Datetime | None
		refresh_expires_at: DF.Datetime | None
		refresh_token: DF.Password | None
		revoked_on: DF.Datetime | None
		scopes: DF.Data | None
		user: DF.Link
	# end: auto-generated types

	def validate(self):
		if self.is_revoked and not self.revoked_on:
			self.revoked_on = frappe.utils.now_datetime()

	@staticmethod
	def _get_client_credentials() -> tuple[str, str]:
		client_id = frappe.db.get_single_value("Press Settings", "github_app_client_id")
		client_secret = frappe.db.get_single_value(
			"Press Settings", "github_app_client_secret"
		)
		if not client_id or not client_secret:
			frappe.throw(
				"GitHub App credentials not configured in Press Settings",
				frappe.ValidationError,
			)
		return client_id, client_secret

	def needs_refresh(self) -> bool:
		"""Return True if access_token is expired or within the refresh lead window."""
		if not self.expires_at:
			return True
		expires = frappe.utils.get_datetime(self.expires_at)
		threshold = frappe.utils.now_datetime() + timedelta(seconds=REFRESH_LEAD_SECONDS)
		return expires <= threshold

	def is_refresh_valid(self) -> bool:
		"""True if the refresh_token itself is still live."""
		if not self.refresh_token or not self.refresh_expires_at:
			return False
		if self.is_revoked:
			return False
		return frappe.utils.get_datetime(self.refresh_expires_at) > frappe.utils.now_datetime()

	def refresh_access_token(self) -> bool:
		"""Exchange the refresh_token for a fresh access_token. Returns True on success."""
		if not self.is_refresh_valid():
			return False

		client_id, client_secret = self._get_client_credentials()
		refresh = self.get_password("refresh_token", raise_exception=False)
		if not refresh:
			return False

		try:
			response = requests.post(
				GITHUB_TOKEN_URL,
				data={
					"client_id": client_id,
					"client_secret": client_secret,
					"grant_type": "refresh_token",
					"refresh_token": refresh,
				},
				headers={"Accept": "application/json"},
				timeout=10,
			)
		except requests.RequestException as exc:
			frappe.log_error(
				title="GitHub token refresh failed",
				message=f"User: {self.user}\n{exc}",
			)
			return False

		data = response.json() if response.ok else {}
		if response.status_code != 200 or "access_token" not in data:
			# Tokens revoked on GitHub side or refresh token expired
			if response.status_code == 401 or data.get("error") in {
				"bad_refresh_token",
				"invalid_grant",
			}:
				self.mark_revoked(reason="GitHub refused the refresh token")
			else:
				frappe.log_error(
					title="GitHub token refresh non-200",
					message=f"User: {self.user}\nStatus: {response.status_code}\nBody: {response.text[:500]}",
				)
			return False

		self.access_token = data["access_token"]
		self.expires_at = frappe.utils.now_datetime() + timedelta(
			seconds=int(data.get("expires_in", 28800))
		)
		if "refresh_token" in data:
			self.refresh_token = data["refresh_token"]
			self.refresh_expires_at = frappe.utils.now_datetime() + timedelta(
				seconds=int(data.get("refresh_token_expires_in", 15897600))
			)
		if "scope" in data:
			self.scopes = data["scope"]
		self.save(ignore_permissions=True)
		frappe.db.commit()
		return True

	def mark_used(self):
		"""Stamp last_used_on without blowing up on concurrent writes."""
		frappe.db.set_value(
			"User GitHub Auth", self.name, "last_used_on", frappe.utils.now(), update_modified=False
		)

	def mark_revoked(self, reason: str = "User requested disconnect"):
		self.is_revoked = 1
		self.revoked_on = frappe.utils.now_datetime()
		self.access_token = None
		self.refresh_token = None
		self.add_comment(text=f"Revoked: {reason}")
		self.save(ignore_permissions=True)
		frappe.db.commit()

	def revoke_on_github(self) -> bool:
		"""Call GitHub to revoke the App grant for this user."""
		client_id, client_secret = self._get_client_credentials()
		access = self.get_password("access_token", raise_exception=False)
		if not access:
			return False
		try:
			response = requests.delete(
				GITHUB_REVOKE_URL_FMT.format(client_id=client_id),
				auth=(client_id, client_secret),
				json={"access_token": access},
				headers={"Accept": "application/vnd.github.v3+json"},
				timeout=10,
			)
			return response.status_code in (204, 404)
		except requests.RequestException as exc:
			frappe.log_error(
				title="GitHub grant revoke failed",
				message=f"User: {self.user}\n{exc}",
			)
			return False

	def get_fresh_access_token(self) -> str | None:
		"""Public helper — returns a currently-valid access token, refreshing if needed."""
		if self.is_revoked:
			return None
		if self.needs_refresh():
			if not self.refresh_access_token():
				return None
			self.reload()
		return self.get_password("access_token", raise_exception=False)


def get_or_create_for_user(
	user: str,
	github_username: str,
	access_token: str,
	refresh_token: str | None,
	expires_in: int,
	refresh_token_expires_in: int | None,
	scopes: str,
) -> "UserGitHubAuth":
	"""Called from the OAuth callback to persist tokens for a user."""
	now = frappe.utils.now_datetime()
	existing = frappe.db.exists("User GitHub Auth", {"user": user})
	if existing:
		doc: UserGitHubAuth = frappe.get_doc("User GitHub Auth", existing)
	else:
		doc = frappe.new_doc("User GitHub Auth")
		doc.user = user
		doc.connected_on = now

	doc.github_username = github_username
	doc.access_token = access_token
	doc.refresh_token = refresh_token
	doc.expires_at = now + timedelta(seconds=expires_in)
	if refresh_token and refresh_token_expires_in:
		doc.refresh_expires_at = now + timedelta(seconds=refresh_token_expires_in)
	doc.scopes = scopes or ""
	doc.is_revoked = 0
	doc.revoked_on = None
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return doc


def get_for_user(user: str) -> "UserGitHubAuth | None":
	name = frappe.db.exists("User GitHub Auth", {"user": user, "is_revoked": 0})
	if not name:
		return None
	return frappe.get_doc("User GitHub Auth", name)
